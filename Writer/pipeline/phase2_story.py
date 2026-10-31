"""Стадии Фазы 2: characters, relations, story_structure, chapter_outline."""

import json
import threading
from typing import Any

import llm
import prompt_loader
import validator

from . import progress as prog
from .json_utils import parse_json
from .registry import StageSpec, register

# Какая стадия сейчас вызывает _call в этом потоке: включает стрим
# с отчётом в progress-store (для «голографического экрана» в UI).
# Нити — потому что стадии исполняются в executor-потоке.
_STAGE_LOCAL = threading.local()


def _system_prompt(name: str) -> str:
    return prompt_loader.get_prompt(name)


def _inject_prev_errors(user_payload: dict,
                        prev_errors: list[str] | None) -> dict:
    if not prev_errors:
        return user_payload
    user_payload = dict(user_payload)
    user_payload["previous_attempt_errors"] = prev_errors
    user_payload["instruction"] = (
        "The previous attempt failed validation. Fix exactly these "
        "problems without changing anything else."
        if prompt_loader.current_language() == "en" else
        "Предыдущая попытка не прошла валидацию. Исправь именно эти проблемы, "
        "не меняя остальное."
    )
    return user_payload


def _call(system: str, user_payload: dict, max_tokens: int,
          prev_errors: list[str] | None = None) -> dict:
    user_payload = _inject_prev_errors(user_payload, prev_errors)
    messages = [
        {"role": "system", "content": system},
        {"role": "user",
         "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]

    stage = getattr(_STAGE_LOCAL, "stage", None)
    if stage:
        # Стрим с отчётом в progress-store: runner раз в ~0.5 с отдаёт
        # символы и хвост размышлений в UI («голографический экран»).
        parts: list[str] = []
        chars = 0
        stream = llm.chat(messages, stream=True,
                          temperature=0.7, max_tokens=max_tokens)
        for kind, text in stream:
            if kind == "reasoning":
                prog.update(stage, thinking_delta=len(text),
                            tail_delta=text)
                continue
            parts.append(text)
            chars += len(text)
            prog.update(stage, chars=chars)
        return parse_json("".join(parts))

    text = llm.chat(messages, stream=False,
                    temperature=0.7, max_tokens=max_tokens)
    return parse_json(text)


def _project_block(project: dict) -> dict:
    return {
        "theme":    project["theme"],
        "genre":    project["genre"],
        "setting":  project["setting"],
        "conflict": project["conflict"],
        "tone":     project.get("tone") or "",

    }


# ────────────────────────────────────────────────────────────────
# CHARACTERS
# ────────────────────────────────────────────────────────────────

def characters_fn(ctx: dict) -> dict:
    b = ctx["bible"]
    payload = {
        "task": "characters",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   b.get("world_core") or {},
            "world_rules":  b.get("world_rules") or {},
            "institutions": b.get("institutions") or {},
            "society":      b.get("society") or {},
            "conflicts":    b.get("conflicts") or {},
            "secrets":      b.get("secrets") or {},
        },
    }
    return _call(_system_prompt("characters"), payload,
                 max_tokens=8000, prev_errors=ctx.get("prev_errors"))


def characters_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_characters(payload, ctx["bible"])


register(StageSpec(
    name="characters",
    fn=characters_fn,
    validator=characters_validator,
    max_calls=3, retry=3,
    requires=["conflicts", "secrets"],
))


# ────────────────────────────────────────────────────────────────
# RELATIONS
# ────────────────────────────────────────────────────────────────

def relations_fn(ctx: dict) -> dict:
    b = ctx["bible"]
    payload = {
        "task": "relations",
        "input": {
            "characters": b.get("characters") or {},
            "conflicts":  b.get("conflicts") or {},
            "secrets":    b.get("secrets") or {},
        },
    }
    return _call(_system_prompt("relations"), payload,
                 max_tokens=6000, prev_errors=ctx.get("prev_errors"))


def relations_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_relations(payload, ctx["bible"])


register(StageSpec(
    name="relations",
    fn=relations_fn,
    validator=relations_validator,
    max_calls=3, retry=3,
    requires=["characters"],
))


# ────────────────────────────────────────────────────────────────
# STORY_STRUCTURE
# ────────────────────────────────────────────────────────────────

def story_structure_fn(ctx: dict) -> dict:
    import config
    b = ctx["bible"]
    project = ctx["project"] or {}
    fmt_key = project.get("book_format") or config.DEFAULT_BOOK_FORMAT
    fmt = config.BOOK_FORMATS.get(fmt_key, config.BOOK_FORMATS[config.DEFAULT_BOOK_FORMAT])

    payload = {
        "task": "story_structure",
        "input": {
            "project":     _project_block(project),
            "world_core":  b.get("world_core") or {},
            "characters":  b.get("characters") or {},
            "relations":   b.get("relations") or {},
            "conflicts":   b.get("conflicts") or {},
            "secrets":     b.get("secrets") or {},
            "book_spec": {
                "format":               fmt_key,
                "format_label":         fmt["label"],
                "total_length_estimate": fmt["chars_default"],
                "chars_min":            fmt["chars_min"],
                "chars_max":            fmt["chars_max"],
                "chapters_min":         fmt["chapters_min"],
                "chapters_max":         fmt["chapters_max"],
                "chapters_default":     fmt["chapters_default"],
                "chapter_word_target":  fmt["words_per_chapter"],
                "required_story_beats": [
                    "opening_image", "theme_stated", "setup", "catalyst",
                    "debate", "break_into_two", "b_story", "fun_and_games",
                    "midpoint", "bad_guys_close_in", "all_is_lost",
                    "dark_night", "break_into_three", "finale", "final_image",
                ],
            },
        },
    }
    return _call(_system_prompt("story_structure"), payload,
                 max_tokens=10000, prev_errors=ctx.get("prev_errors"))


def story_structure_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_story_structure(payload, ctx["bible"])


register(StageSpec(
    name="story_structure",
    fn=story_structure_fn,
    validator=story_structure_validator,
    max_calls=3, retry=3,
    requires=["characters", "relations"],
))


# ────────────────────────────────────────────────────────────────
# CHAPTER_OUTLINE
# ────────────────────────────────────────────────────────────────

def chapter_outline_fn(ctx: dict, allow_chunking: bool = True) -> dict:
    import config
    b = ctx["bible"]
    project = ctx["project"] or {}
    stage = ctx.get("stage") or "chapter_outline"
    prog.start(stage)
    _STAGE_LOCAL.stage = stage
    try:
        return _chapter_outline_body(ctx, allow_chunking, stage)
    finally:
        _STAGE_LOCAL.stage = None
        prog.finish(stage)


def _chapter_outline_body(ctx: dict, allow_chunking: bool,
                          stage: str) -> dict:
    import config
    b = ctx["bible"]
    project = ctx["project"] or {}
    fmt_key = project.get("book_format") or config.DEFAULT_BOOK_FORMAT
    fmt = config.BOOK_FORMATS.get(fmt_key, config.BOOK_FORMATS[config.DEFAULT_BOOK_FORMAT])

    # Явные списки доступных id — чтобы модель не выдумывала CH6
    chars = (b.get("characters") or {}).get("characters") or []
    char_ids = [c.get("id") for c in chars if isinstance(c, dict) and c.get("id")]
    loc_ids = [
        l.get("id") for l in (b.get("geography") or {}).get("locations", [])
        if isinstance(l, dict) and l.get("id")
    ]
    secret_ids = [
        s.get("id") for s in (b.get("secrets") or {}).get("secrets", [])
        if isinstance(s, dict) and s.get("id")
    ]

    # Также передаём компактную карту "pov_thread_id → character_id",
    # чтобы модель не путала POV1 с CH1.
    pov_map = {}
    for th in (b.get("story_structure") or {}).get("pov_threads", []) or []:
        if isinstance(th, dict):
            pov_map[th.get("id")] = th.get("character")

    payload = {
        "task": "chapter_outline",
        "input": {
            "story_structure": b.get("story_structure") or {},
            "characters":      b.get("characters") or {},
            "geography":       b.get("geography") or {},
            "history":         b.get("history") or {},
            "secrets":         b.get("secrets") or {},
            "allowed_ids": {
                "characters": char_ids,
                "locations":  loc_ids,
                "secrets":    secret_ids,
                "pov_map":    pov_map,
                "rule": "Поле pov принимает ТОЛЬКО значения из allowed_ids.characters. "
                        "POV1, POV2 — это НЕ персонажи, это идентификаторы нитей. "
                        "В allowed_ids.pov_map указано, какая нить какому персонажу "
                        "соответствует.",
            },
            "book_spec": {
                "format":              fmt_key,
                "format_label":        fmt["label"],
                "chapters_min":        fmt["chapters_min"],
                "chapters_max":        fmt["chapters_max"],
                "chapter_word_target": fmt["words_per_chapter"],
                "total_length_estimate": fmt["chars_default"],
            },
        },
    }
    # ── Пакетная генерация: роман (≥10 глав) локальная модель
    #    одним вызовом не вытягивает (обрыв по max_tokens и арифметика
    #    word_target). Делим на пакеты по несколько глав.
    total_n = (b.get("story_structure") or {}).get("total_chapters")
    batch = _outline_batch_size(fmt) if allow_chunking else 0
    if batch >= 2 and isinstance(total_n, int) and total_n > batch:
        return _chapter_outline_chunked(
            _system_prompt("chapter_outline"), payload, ctx,
            total_n, batch, stage)

    prog.update(stage, phase_key="single",
                total_chapters=total_n if isinstance(total_n, int) else 0)
    return _call(_system_prompt("chapter_outline"), payload,
                 max_tokens=13000, prev_errors=ctx.get("prev_errors"))


def _outline_batch_size(fmt: dict) -> int:
    """0 — одним вызовом; N≥2 — пакетами по N глав.
    Настройка outline_batch_size: пусто — авто, 0 — одним вызовом,
    3..10 — фиксированный размер пакета. Авто: романам (≥10 глав
    по умолчанию) — пакетами по 5, малым форматам — одним вызовом."""
    import db
    raw = (db.get_setting("outline_batch_size") or "").strip()
    if raw:
        try:
            v = int(raw)
        except ValueError:
            return 0
        return v if v >= 2 else 0
    return 5 if fmt["chapters_default"] >= 10 else 0


def _compact_chapter(c: dict) -> dict:
    """Компактная сводка уже сгенерированной главы — для преемственности."""
    return {
        "num":            c.get("num"),
        "title":          c.get("title"),
        "pov":            c.get("pov"),
        "act":            c.get("act"),
        "purpose":        c.get("purpose"),
        "location":       c.get("location"),
        "tension_target": c.get("tension_target"),
    }


def _build_batch_payload(payload: dict, done: list[dict],
                         start: int, end: int, total_n: int) -> dict:
    """Payload пакета: тот же input + инструкция диапазона и сводка
    уже сгенерированных глав для преемственности."""
    import copy
    p = copy.deepcopy(payload)
    last = done[-1] if done else None
    p["input"]["batch"] = {
        "total_chapters": total_n,
        "generate_nums":  list(range(start, end + 1)),
        "already_generated_compact": [_compact_chapter(c) for c in done],
        "previous_chapter_beats": (last or {}).get("beats"),
        "instruction": (
            f"Сгенерируй ТОЛЬКО главы {start}..{end} из {total_n}. "
            "Ответ — JSON вида {\"chapters\":[...]}, содержащий только эти "
            "главы; поля глав и сцен — по схеме и правилам системного "
            "промпта. Соблюдай преемственность с уже сгенерированными "
            "главами (already_generated_compact, previous_chapter_beats) "
            "и не повторяй их события."
            if prompt_loader.current_language() == "ru" else
            f"Generate ONLY chapters {start}..{end} of {total_n}. "
            "Answer with JSON of the form {\"chapters\":[...]} containing "
            "only these chapters; chapter and scene fields follow the "
            "schema and rules of the system prompt. Keep continuity with "
            "the already generated chapters (already_generated_compact, "
            "previous_chapter_beats) and do not repeat their events."
        ),
    }
    return p


def _validate_batch(data: Any, start: int, end: int) -> list[str]:
    """Лёгкая структурная проверка пакета глав (без библии — id-проверки
    делает финальная валидация merged-плана)."""
    e: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("chapters"), list):
        return ["пакет: ожидался JSON-объект с массивом chapters."]
    chs = data["chapters"]
    nums = [c.get("num") for c in chs if isinstance(c, dict)]
    if nums != list(range(start, end + 1)):
        e.append(f"пакет: ожидались главы {start}..{end}, получены {nums}.")
    for c in chs:
        if not isinstance(c, dict):
            continue
        cid = c.get("num", "?")
        beats = c.get("beats")
        if not isinstance(beats, list) or len(beats) != 5:
            e.append(f"ch.{cid}: beats — ровно 5 сцен, получено "
                     f"{len(beats) if isinstance(beats, list) else '?'}.")
            continue
        scene_nums: list = []
        sum_wt = 0
        for i, b in enumerate(beats):
            if not isinstance(b, dict):
                e.append(f"ch.{cid}.beats[{i}]: должен быть объектом.")
                continue
            scene_nums.append(b.get("scene"))
            wt = b.get("word_target")
            if isinstance(wt, int) and wt > 0:
                sum_wt += wt
            ac = b.get("action_chain")
            if not isinstance(ac, list) or not (4 <= len(ac) <= 6):
                e.append(f"ch.{cid}.beats[{i}].action_chain: "
                         f"4–6 микрособытий.")
            res = b.get("result")
            if not isinstance(res, str) or not res.strip():
                e.append(f"ch.{cid}.beats[{i}].result: пусто.")
        if scene_nums != [1, 2, 3, 4, 5]:
            e.append(f"ch.{cid}: сцены должны идти 1..5 по порядку.")
        ch_wt = c.get("word_target")
        if (isinstance(ch_wt, int) and sum_wt > 0
                and abs(sum_wt - ch_wt) / ch_wt > 0.05):
            e.append(f"ch.{cid}: сумма word_target сцен ({sum_wt}) "
                     f"отклоняется от word_target главы ({ch_wt}) "
                     f"более чем на 5%.")
    return e


def _chapter_outline_chunked(system: str, payload: dict, ctx: dict,
                             total_n: int, batch: int, stage: str) -> dict:
    """План глав пакетами: батч → лёгкая проверка → ретрай пакета с
    ошибками → следующий батч → финальная полная валидация merged.
    Каждый батч стримится с отчётом в progress-store (фаза пакета,
    символы, хвост размышлений) — «голографический экран» в UI."""
    ranges = [(s, min(s + batch - 1, total_n))
              for s in range(1, total_n + 1, batch)]
    chapters: list[dict] = []
    est_per_chapter = 2800  # начальная оценка; уточняется по факту пакетов
    for i, (start, end) in enumerate(ranges, 1):
        n_ch = end - start + 1
        prog.update(stage, phase_key="batch",
                    phase_params={"i": i, "n": len(ranges),
                                  "a": start, "b": end},
                    batch_chapters=n_ch,
                    est_batch_chars=est_per_chapter * n_ch,
                    done_chapters=len(chapters),
                    total_chapters=total_n)
        batch_payload = _build_batch_payload(payload, chapters,
                                             start, end, total_n)
        # prev_errors стадии (ретрай раннера) уходят в первый пакет.
        stage_errors = ctx.get("prev_errors") if start == 1 else []
        data = None
        batch_errors: list[str] = []
        for attempt in (1, 2):
            try:
                data = _call(system, batch_payload, max_tokens=12000,
                             prev_errors=stage_errors or batch_errors)
            except Exception:
                if attempt == 2:
                    raise
                continue
            batch_errors = _validate_batch(data, start, end)
            if not batch_errors:
                break
        if data is None or batch_errors:
            raise RuntimeError(
                f"chapter_outline (пакет {start}..{end}): "
                + "; ".join(batch_errors or ["модель не вернула JSON"]))
        got = data.get("chapters") or []
        chapters.extend(got)
        # Уточняем оценку объёма по фактическому размеру пакета.
        snap = prog.snapshot(stage)
        if snap and n_ch and snap.get("chars"):
            est_per_chapter = max(1200, int(snap["chars"] / n_ch))
        prog.update(stage, done_chapters=len(chapters))

    prog.update(stage, phase_key="merging", phase_params={})
    merged = {"total_chapters": total_n, "chapters": chapters}
    errs = validator.validate_chapter_outline(merged, ctx["bible"])
    if errs:
        raise RuntimeError("chapter_outline (merge): " + "; ".join(errs[:6]))
    return merged


def chapter_outline_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_chapter_outline(payload, ctx["bible"])


register(StageSpec(
    name="chapter_outline",
    fn=chapter_outline_fn,
    validator=chapter_outline_validator,
    max_calls=3, retry=3,
    requires=["story_structure"],
))
