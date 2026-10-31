"""Мост между Writer AI Studio и внешними LLM для стадий планирования.

Собирает промпт стадии в текст (для копирования в Sonnet/GPT) и принимает
ответ в виде JSON с валидацией и сохранением в БД.

Дополнительно: run_strong_stage() — кнопка 🤖 «написать сильной моделью»:
промпт стадии уходит напрямую в облачную модель (профиль strong из
настроек), ответ валидируется и сохраняется как вариант 'strong' — рядом
с вариантом локальной модели, без перезаписи активного слоя.
"""

import asyncio
import json
import threading
from typing import AsyncIterator

import db
import llm
import prompt_loader
import validator
from translations import translate, trf as _t


SUPPORTED_STAGES = ("characters", "relations", "story_structure", "chapter_outline")

# У каждой стадии — свой валидатор. Раньше все стадии, кроме
# story_structure, проверялись валидатором плана глав, из-за чего
# вставка внешних characters/relations всегда падала.
_STAGE_VALIDATORS = {
    "characters":      validator.validate_characters,
    "relations":       validator.validate_relations,
    "story_structure": validator.validate_story_structure,
    "chapter_outline": validator.validate_chapter_outline,
}

# Monkeypatch _call не потокобезопасен: параллельные запросы могли
# подменить его друг под другом. Сериализуем сборку промптов.
_prompt_lock = threading.Lock()


def _capture_call(storage: dict):
    """Заглушка вместо _call: сохраняет system+user, не вызывает LLM."""
    def fake_call(system, user_payload, max_tokens, prev_errors=None):
        if prev_errors:
            user_payload = dict(user_payload)
            user_payload["previous_attempt_errors"] = prev_errors
            user_payload["instruction"] = (
                "The previous attempt failed validation. Fix exactly these "
                "problems without changing anything else."
                if prompt_loader.current_language() == "en" else
                "Предыдущая попытка не прошла валидацию. Исправь именно эти "
                "проблемы, не меняя остальное."
            )
        storage["system"] = system
        storage["user_payload"] = user_payload
        return {}
    return fake_call


def build_prompt(stage: str) -> dict:
    """Возвращает {system, user, combined} для указанной стадии."""
    if stage not in SUPPORTED_STAGES:
        raise ValueError(_t("Стадия {stage} не поддерживается.", stage=stage))

    import pipeline.phase2_story as p2

    storage = {}
    with _prompt_lock:
        original_call = p2._call
        p2._call = _capture_call(storage)
        try:
            project = db.get_project()
            bible = db.get_full_bible()
            ctx = {
                "stage": stage,
                "project": project,
                "bible": bible,
                "prev_errors": [],
            }
            if stage == "characters":
                p2.characters_fn(ctx)
            elif stage == "relations":
                p2.relations_fn(ctx)
            elif stage == "story_structure":
                p2.story_structure_fn(ctx)
            elif stage == "chapter_outline":
                # allow_chunking=False: мост собирает промпт ОДНОГО вызова
                # (сильной модели это по силам; чанки ломают capture).
                p2.chapter_outline_fn(ctx, allow_chunking=False)
        finally:
            p2._call = original_call

    if "system" not in storage:
        raise ValueError(
            _t("Не удалось собрать промпт для {stage} — "
               "возможно, отсутствуют предыдущие стадии.", stage=stage)
        )

    system = storage["system"]
    user = json.dumps(storage["user_payload"], ensure_ascii=False, indent=2)
    combined = (
        "=== SYSTEM ===\n" + system.rstrip() + "\n\n"
        "=== USER ===\n" + user + "\n"
    )
    return {
        "stage":        stage,
        "system":       system,
        "user":         user,
        "combined":     combined,
        "system_chars": len(system),
        "user_chars":   len(user),
    }


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def import_payload(stage: str, raw_text: str) -> dict:
    """Парсит JSON из ответа, валидирует, сохраняет. Возвращает {ok, errors}."""
    if stage not in SUPPORTED_STAGES:
        return {"ok": False,
                "errors": [_t("Стадия {stage} не поддерживается.", stage=stage)]}

    text = _strip_fences(raw_text)
    i = text.find("{")
    j = text.rfind("}")
    if i < 0 or j < 0:
        return {"ok": False, "errors": [_t("В тексте не найден JSON-объект.")]}

    try:
        data = json.loads(text[i:j+1])
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [_t("Ошибка парсинга JSON: {e}", e=e)]}

    bible = db.get_full_bible()
    errors = _STAGE_VALIDATORS[stage](data, bible)

    if errors:
        return {"ok": False, "errors": errors}

    db.save_bible_stage(stage, data, validated=True)
    db.set_stage(stage, "done")
    # Вставленный JSON — самостоятельный вариант «ручная вставка»;
    # он же становится активным, т.к. записан в world_bible.
    try:
        db.save_stage_variant(stage, "manual", data, errors=[],
                              is_active=True)
    except Exception:
        pass
    return {"ok": True, "errors": []}


# ────────────────────────────────────────────────────────────────
# 🤖 Написать сильной моделью: стрим, варианты, сравнение
# ────────────────────────────────────────────────────────────────

def _next_or_none(it):
    try:
        return next(it)
    except StopIteration:
        return None


def _strong_messages(system: str, base_payload: dict,
                     prev_errors: list[str]) -> list[dict]:
    """Сообщения для сильной модели: на ретрае — список ошибок валидации."""
    payload = base_payload
    if prev_errors:
        payload = dict(base_payload)
        payload["previous_attempt_errors"] = prev_errors
        payload["instruction"] = (
            "The previous attempt failed validation. Fix exactly these "
            "problems without changing anything else."
            if prompt_loader.current_language() == "en" else
            "Предыдущая попытка не прошла валидацию. Исправь именно эти "
            "проблемы, не меняя остальное."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user",
         "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


async def run_strong_stage(stage: str) -> AsyncIterator[dict]:
    """SSE-генератор: промпт стадии → сильная модель (профиль 'strong') →
    валидация → вариант 'strong' в БД. Активный слой не трогает."""
    if stage not in SUPPORTED_STAGES:
        yield {"type": "error", "stage": stage,
               "message": _t("Стадия {stage} не поддерживается.", stage=stage)}
        return

    if not llm.strong_configured():
        yield {"type": "error", "stage": stage,
               "message": _t("Профиль сильной модели не настроен "
                             "(Настройки → Сильная модель).")}
        return

    try:
        prompt = build_prompt(stage)
    except ValueError as e:
        yield {"type": "error", "stage": stage, "message": str(e)}
        return

    system = prompt["system"]
    try:
        base_payload = json.loads(prompt["user"])
    except json.JSONDecodeError:
        yield {"type": "error", "stage": stage,
               "message": _t("Не удалось восстановить payload промпта.")}
        return

    yield {"type": "strong_started", "stage": stage,
           "model": llm.strong_model_label()}

    validator_fn = _STAGE_VALIDATORS[stage]
    bible = db.get_full_bible()
    max_attempts = 2
    errors: list[str] = []
    loop = asyncio.get_running_loop()

    for attempt in range(1, max_attempts + 1):
        yield {"type": "attempt", "stage": stage,
               "attempt": attempt, "max": max_attempts}

        text_parts: list[str] = []
        try:
            stream = llm.chat(
                _strong_messages(system, base_payload, errors),
                stream=True,
                temperature=0.7,
                max_tokens=llm.strong_max_tokens(),
                profile="strong",
            )
            it = iter(stream)
            while True:
                item = await loop.run_in_executor(None, _next_or_none, it)
                if item is None:
                    break
                kind, text = item
                if kind == "reasoning":
                    yield {"type": "thinking", "stage": stage, "text": text}
                else:
                    text_parts.append(text)
                    yield {"type": "chunk", "stage": stage, "text": text}
        except Exception as e:
            yield {"type": "exception", "stage": stage,
                   "attempt": attempt, "message": str(e)}
            if attempt < max_attempts:
                await asyncio.sleep(1)
                continue
            yield {"type": "stage_failed", "stage": stage,
                   "errors": [str(e)]}
            return

        raw = "".join(text_parts).strip()

        from pipeline.json_utils import parse_json, JSONParseError
        try:
            data = parse_json(raw)
        except JSONParseError as e:
            errors = [_t("JSON не распознан: {e}", e=e)]
            yield {"type": "validation_failed", "stage": stage,
                   "attempt": attempt, "errors": errors}
            continue

        raw_errors = validator_fn(data, bible) if validator_fn else []
        # Для показа — на языке UI; для ретрая модели — исходные строки.
        shown = [translate(x) if isinstance(x, str) else x
                 for x in raw_errors]
        errors = [x for x in shown if not str(x).startswith("WARN:")]
        warnings = [str(x)[len("WARN:"):].strip()
                    for x in shown if str(x).startswith("WARN:")]
        if warnings:
            yield {"type": "warning", "stage": stage,
                   "attempt": attempt, "warnings": warnings}
        if errors:
            yield {"type": "validation_failed", "stage": stage,
                   "attempt": attempt, "errors": errors}
            continue

        # Успех: вариант 'strong' сохраняется рядом с активным слоем.
        try:
            variant_id = db.save_stage_variant(stage, "strong", data,
                                               errors=None, is_active=False)
        except Exception as e:
            yield {"type": "error", "stage": stage, "message": str(e)}
            return
        yield {"type": "strong_done", "stage": stage,
               "variant_id": variant_id,
               "preview": json.dumps(data, ensure_ascii=False)[:500]}
        return

    yield {"type": "stage_failed", "stage": stage, "errors": errors}


def activate_variant(stage: str, variant_id: int) -> dict:
    """Применить вариант: повторная валидация против ТЕКУЩЕЙ библии
    (ids могли поменяться после сохранения варианта) и запись слоя."""
    if stage not in SUPPORTED_STAGES:
        return {"ok": False,
                "errors": [_t("Стадия {stage} не поддерживается.", stage=stage)]}

    content = db.get_stage_variant_content(variant_id)
    if content is None:
        return {"ok": False, "errors": [_t("Вариант не найден.")]}

    bible = db.get_full_bible()
    errors = _STAGE_VALIDATORS[stage](content, bible)
    if errors:
        return {"ok": False,
                "errors": [translate(x) if isinstance(x, str) else x
                           for x in errors]}

    db.save_bible_stage(stage, content, validated=True)
    db.set_stage(stage, "done")
    db.mark_variant_active(stage, variant_id)
    return {"ok": True}


# ── Структурное сравнение вариантов ────────────────────────────

def _row(key: str, params: dict, a, b) -> dict:
    return {"key": key, "params": params, "a": a, "b": b,
            "changed": a != b}


def _diff_outline(a: dict, b: dict) -> list[dict]:
    """Дифф плана глав: количество, POV/локация/акт/тенсион/объём и биты
    каждой главы. Ключи строк переводит UI."""
    rows: list[dict] = []
    ca = {c.get("num"): c for c in (a.get("chapters") or [])
          if isinstance(c, dict)}
    cb = {c.get("num"): c for c in (b.get("chapters") or [])
          if isinstance(c, dict)}
    rows.append(_row("chapters_count", {}, len(ca), len(cb)))

    for num in sorted(set(ca) | set(cb)):
        x, y = ca.get(num) or {}, cb.get(num) or {}
        changed = []
        for field in ("pov", "location", "act", "tension_target",
                      "word_target", "title", "time_of_day", "mood"):
            if x.get(field) != y.get(field):
                changed.append(field)
                rows.append(_row("chapter_field", {"num": num,
                                                   "field": field},
                                 x.get(field), y.get(field)))
        bx = x.get("beats") or []
        by = y.get("beats") or []
        sx = sum(s.get("word_target") or 0 for s in bx if isinstance(s, dict))
        sy = sum(s.get("word_target") or 0 for s in by if isinstance(s, dict))
        if len(bx) != len(by):
            rows.append(_row("chapter_beats", {"num": num},
                             f"{len(bx)}", f"{len(by)}"))
        if sx != sy:
            rows.append(_row("chapter_scenes_sum", {"num": num}, sx, sy))
        ex = set(x.get("events") or [])
        ey = set(y.get("events") or [])
        if ex != ey:
            rows.append(_row("chapter_events", {"num": num},
                             sorted(ex), sorted(ey)))
        px = set(x.get("secrets_touched") or [])
        py = set(y.get("secrets_touched") or [])
        if px != py:
            rows.append(_row("chapter_secrets", {"num": num},
                             sorted(px), sorted(py)))
        if not changed and bx == by and ex == ey and px == py:
            rows.append(_row("chapter_same", {"num": num}, None, None))
    return rows


def _diff_generic(a: dict, b: dict) -> list[dict]:
    """Дифф остальных стадий: ключи верхнего уровня, счётчики списков,
    скаляры. Списки объектов сравниваем по количеству и наборам id."""
    rows: list[dict] = []
    for key in sorted(set(a or {}) | set(b or {})):
        va, vb = (a or {}).get(key), (b or {}).get(key)
        if isinstance(va, list) or isinstance(vb, list):
            la, lb = (va if isinstance(va, list) else []) or [], \
                     (vb if isinstance(vb, list) else []) or []
            if len(la) != len(lb):
                rows.append(_row("list_count", {"key": key},
                                 len(la), len(lb)))
            ia = {x.get("id") for x in la
                  if isinstance(x, dict) and x.get("id")}
            ib = {x.get("id") for x in lb
                  if isinstance(x, dict) and x.get("id")}
            if ia and ib and ia != ib:
                only_a, only_b = sorted(ia - ib), sorted(ib - ia)
                if only_a:
                    rows.append(_row("ids_removed", {"key": key},
                                     only_a, None))
                if only_b:
                    rows.append(_row("ids_added", {"key": key},
                                     None, only_b))
        elif isinstance(va, dict) or isinstance(vb, dict):
            da = va if isinstance(va, dict) else {}
            dbb = vb if isinstance(vb, dict) else {}
            if len(da) != len(dbb):
                rows.append(_row("keys_count", {"key": key},
                                 len(da), len(dbb)))
        elif va != vb:
            rows.append(_row("field", {"key": key}, va, vb))
    return rows


def compare_variant(stage: str, variant_id: int) -> dict:
    """Активный слой (world_bible) против выбранного варианта:
    структурный дифф + свежая валидация варианта против текущей библии
    (ids могли измениться с момента сохранения)."""
    meta = db.get_stage_variant(variant_id)
    if not meta or meta["stage"] != stage:
        return {"ok": False, "errors": [_t("Вариант не найден.")]}

    content = db.get_stage_variant_content(variant_id)
    active = db.get_bible_stage(stage)
    if active is None:
        return {"ok": False,
                "errors": [_t("Слой '{stage}' пуст.", stage=stage)]}

    if stage == "chapter_outline":
        rows = _diff_outline(active, content)
    else:
        rows = _diff_generic(active, content)

    # Свежая валидация варианта против текущей библии.
    validator_fn = _STAGE_VALIDATORS.get(stage)
    errors_now: list[str] = []
    if validator_fn and content is not None:
        errors_now = [translate(x) if isinstance(x, str) else x
                      for x in validator_fn(content, db.get_full_bible())]

    return {
        "ok": True,
        "stage": stage,
        "variant": {"id": meta["id"], "variant": meta["variant"],
                    "created_at": meta["created_at"]},
        "rows": rows,
        "valid_now": not errors_now,
        "errors_now": errors_now,
    }