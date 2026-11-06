"""Инструмент «Аннотация»: досье книги из БД, аннотации и промпты обложки.

Принцип — как во всём приложении: LLM ничего не помнит, весь контекст
собирается программно. Но в отличие от глав, модель получает НЕ тексты
глав (они огромны), а компактное досье: проект, ядро мира, персонажей,
структуру Save the Cat, план глав и пересказы (summary), которые движок
уже извлёк после каждой главы.

kind='annotation' — 4 варианта аннотации разными подходами;
kind='cover'      — 3 универсальных текстовых промпта для обложки;
kind='refine'     — итеративная правка выбранного варианта по инструкции
                    пользователя (диалог с историей).
"""

import asyncio
import json
from typing import AsyncIterator, Optional

import db
import llm
import prompt_loader
from translations import trf as _t


# ────────────────────────────────────────────────────────────────
# Досье книги: всё, кроме текстов глав
# ────────────────────────────────────────────────────────────────

def _trim(s, n: int = 300) -> str:
    s = str(s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def build_context() -> dict:
    """Компактное досье проекта для аннотации. Текстов глав здесь нет
    и быть не может — только метаданные, план и пересказы."""
    project = db.get_project() or {}
    bible = db.get_full_bible()

    core = bible.get("world_core") or {}
    structure = bible.get("story_structure") or {}
    outline = (bible.get("chapter_outline") or {}).get("chapters") or []
    chars = (bible.get("characters") or {}).get("characters") or []
    secrets = (bible.get("secrets") or {}).get("secrets") or []

    chapters = db.list_chapters()
    # summary не входит в list_chapters (для UI глав он не нужен),
    # здесь — отдельным запросом.
    with db.conn() as c:
        sum_rows = c.execute(
            """SELECT num, title, summary FROM chapters
                WHERE summary IS NOT NULL AND summary != ''
                ORDER BY num"""
        ).fetchall()
    summaries = [
        {"num": r["num"], "title": r["title"] or "", "summary": r["summary"]}
        for r in sum_rows
    ]
    words_total = sum(ch.get("word_count") or 0 for ch in chapters)
    generated = sum(1 for ch in chapters if (ch.get("word_count") or 0) > 0)

    return {
        "book": {
            "title":        _trim(project.get("theme"), 200),
            "genre":        project.get("genre") or "",
            "setting":      _trim(project.get("setting"), 300),
            "conflict":     _trim(project.get("conflict"), 300),
            "tone":         _trim(project.get("tone"), 200),
            "language":     project.get("language") or "ru",
            "book_format":  project.get("book_format") or "novel",
            "chapters_planned": len(outline) or len(chapters),
            "chapters_written": generated,
            "words_total":  words_total,
        },
        "world_core": {
            "concept":       _trim((core.get("central_concept") or {}).get("one_line"), 400),
            "paradox":       _trim(core.get("central_paradox"), 400),
            "core_question": _trim(core.get("core_question"), 300),
            "tone_tags":     (core.get("tone_tags") or [])[:6],
        },
        "characters": [
            {
                "name":         _trim(c.get("name"), 80),
                "role":         _trim(c.get("role_in_conflict"), 200),
                "side":         _trim(c.get("side"), 60),
                "stake":        _trim(c.get("personal_stake"), 250),
                "contradiction": _trim(c.get("contradiction"), 250),
            }
            for c in chars[:8]
        ],
        "story_beats": [
            {
                "name":        _trim(b.get("name"), 80),
                "chapter":     b.get("chapter"),
                "description": _trim(b.get("description"), 260),
            }
            for b in (structure.get("story_beats") or [])
            if isinstance(b, dict)
        ],
        "outline": [
            {
                "num":      c.get("num"),
                "title":    _trim(c.get("title"), 120),
                "pov":      _trim(c.get("pov"), 80),
                "act":      c.get("act"),
                "tension":  c.get("tension_target"),
            }
            for c in outline
            if isinstance(c, dict)
        ],
        "summaries": [
            {**s, "summary": _trim(s["summary"], 900)} for s in summaries
        ],
        "secrets": [
            {"id": s.get("id"), "truth": _trim(s.get("truth"), 250)}
            for s in secrets[:10]
        ],
    }


def _context_payload(ctx: dict) -> str:
    """Досье как JSON для user-сообщения (идиома приложения — языково-нейтральный
    payload, инструкции на языке промпта)."""
    payload = dict(ctx)
    if payload.get("secrets"):
        payload["closed_information"] = payload.pop("secrets")
    return json.dumps(payload, ensure_ascii=False, indent=1)


# ────────────────────────────────────────────────────────────────
# Генерация: SSE-поток (как run_strong_stage)
# ────────────────────────────────────────────────────────────────

PROMPT_NAMES = {"annotation": "annotation", "cover": "cover_prompt"}


def _max_tokens(profile: str) -> int:
    if profile == "strong":
        return llm.strong_max_tokens()
    # Аннотации и промпты — не главы; 6000 хватает с запасом
    # даже «думающим» моделям.
    try:
        return max(4000, int(db.get_setting("chapter_max_tokens") or 0) or 6000)
    except (TypeError, ValueError):
        return 6000


def _refine_system(target: str) -> str:
    """Системный промпт правки: тот же файл + инструкция доработки."""
    base = prompt_loader.get_prompt(PROMPT_NAMES[target])
    if prompt_loader.current_language() == "en":
        add = ("\n\nREFINEMENT MODE: You will receive the current version "
               "and the user's edit request. Return ONE improved version "
               "of the same kind of text. No headers, no '## ' lines, no "
               "remarks — only the final text. Keep what works, change "
               "what the user asked for.")
    else:
        add = ("\n\nРЕЖИМ ПРАВКИ: ты получишь текущую версию и просьбу "
               "пользователя. Верни ОДНУ доработанную версию того же типа "
               "текста. Без заголовков, без строк «## », без пояснений — "
               "только финальный текст. Что работает — сохрани, что "
               "попросили — измени.")
    return base + add


def _messages_for(kind: str, target: str, instruction: Optional[str],
                  history: Optional[list[dict]]) -> list[dict]:
    """Сообщения для LLM. kind='annotation'|'cover' — генерация вариантов;
    kind='refine' — правка: досье + история диалога + новая просьба.
    target ('annotation'|'cover') выбирает системный промпт для правки."""
    user = _context_payload(build_context())

    if kind == "refine":
        msgs = [{"role": "system", "content": _refine_system(target)},
                {"role": "user", "content": user}]
        for h in history or []:
            role = h.get("role")
            if role in ("user", "assistant") and h.get("content"):
                msgs.append({"role": role, "content": str(h["content"])[:12000]})
        msgs.append({"role": "user", "content": instruction or ""})
        return msgs

    system = prompt_loader.get_prompt(PROMPT_NAMES[kind])
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


async def generate(kind: str, profile: str = "main",
                   target: str = "annotation",
                   instruction: Optional[str] = None,
                   history: Optional[list[dict]] = None) -> AsyncIterator[dict]:
    """SSE-генератор: досье → LLM → события started/thinking/chunk/done."""
    if kind not in ("annotation", "cover", "refine"):
        yield {"type": "error", "message": _t("Неизвестный тип генерации.")}
        return
    if target not in ("annotation", "cover"):
        target = "annotation"
    if not db.get_project():
        yield {"type": "error", "message": _t("Проект не создан.")}
        return
    if profile not in ("main", "strong"):
        profile = "main"
    if profile == "strong" and not llm.strong_configured():
        yield {"type": "error",
               "message": _t("Профиль сильной модели не настроен "
                             "(Настройки → Сильная модель).")}
        return

    model_label = (llm.strong_model_label() if profile == "strong"
                   else db.get_setting("llm_model_name") or "")
    yield {"type": "started", "kind": kind, "profile": profile,
           "model": model_label}

    try:
        msgs = _messages_for(kind, target, instruction, history)
    except Exception as e:
        yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
        return

    loop = asyncio.get_running_loop()

    def _next_or_none(it):
        try:
            return next(it)
        except StopIteration:
            return None

    parts: list[str] = []
    try:
        stream = llm.chat(msgs, stream=True, temperature=0.85,
                          max_tokens=_max_tokens(profile), profile=profile)
        it = iter(stream)
        while True:
            item = await loop.run_in_executor(None, _next_or_none, it)
            if item is None:
                break
            chip_kind, text = item
            if chip_kind == "reasoning":
                yield {"type": "thinking", "text": text}
            else:
                parts.append(text)
                yield {"type": "chunk", "text": text}
    except llm.LLMError as e:
        yield {"type": "error", "message": str(e)}
        return
    except Exception as e:
        yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
        return

    raw = "".join(parts).strip()
    if not raw:
        yield {"type": "error",
               "message": _t("Пустой ответ от LLM.")}
        return
    yield {"type": "done", "raw": raw}


# ────────────────────────────────────────────────────────────────
# Сохранение в book_meta
# ────────────────────────────────────────────────────────────────

def save_result(annotation: Optional[str] = None,
                cover_prompt: Optional[str] = None,
                profile: str = "main") -> dict:
    saved = {"annotation": False, "cover_prompt": False}
    if annotation is not None and annotation.strip():
        db.save_book_meta("annotation", {
            "text": annotation.strip(),
            "profile": profile,
        })
        saved["annotation"] = True
    if cover_prompt is not None and cover_prompt.strip():
        db.save_book_meta("cover_prompt", {
            "text": cover_prompt.strip(),
            "profile": profile,
        })
        saved["cover_prompt"] = True
    if not any(saved.values()):
        return {"ok": False, "error": _t("Нечего сохранять.")}
    return {"ok": True, "saved": saved}


def load_saved() -> dict:
    return {
        "annotation": db.get_book_meta("annotation"),
        "cover_prompt": db.get_book_meta("cover_prompt"),
    }
