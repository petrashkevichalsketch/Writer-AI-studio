"""Генерация главы с SSE-стримом. Возвращает async-генератор событий."""

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

import db
import llm
from context_builder import build_context

PROMPTS = Path(__file__).parent / "prompts"


def _system_prompt() -> str:
    return (PROMPTS / "chapter_writer.txt").read_text(encoding="utf-8")


def _questions_system_prompt() -> str:
    return (PROMPTS / "chapter_questions.txt").read_text(encoding="utf-8")


def _chapter_words() -> int:
    try:
        return int(db.get_setting("chapter_words", "3000"))
    except Exception:
        return 3000


async def generate_chapter(num: int,
                           qa_answers: list[dict] | None = None
                           ) -> AsyncIterator[dict]:
    """Async-генератор SSE-событий для генерации одной главы."""
    project = db.get_project()
    if not project:
        yield {"type": "error", "message": "Проект не создан."}
        return

    bible = db.get_full_bible()

    try:
        ctx = build_context(project, bible, num,
                            word_target=_chapter_words(),
                            qa_answers=qa_answers)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    # Мета-событие: план главы, чтобы UI сразу отрисовал правую панель
    yield {
        "type":  "meta",
        "num":   num,
        "title": ctx["chapter"].get("title"),
        "plan":  ctx["chapter"],
        "chars": [c.get("name") for c in ctx.get("characters") or []],
    }

    # Промпт: system + user с полным контекстом
    system = _system_prompt()
    user_payload = {
        "task": "chapter_writer",
        "input": ctx,
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user",
         "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]

    full_text_parts: list[str] = []
    try:
        stream = llm.chat(
            messages,
            stream=True,
            temperature=0.9,
            max_tokens=8000,
        )
        # llm.chat(stream=True) возвращает синхронный итератор.
        # Обернём в executor, чтобы не блокировать event loop.
        loop = asyncio.get_event_loop()
        it = iter(stream)
        while True:
            chunk = await loop.run_in_executor(None, _next_or_none, it)
            if chunk is None:
                break
            full_text_parts.append(chunk)
            yield {"type": "chunk", "text": chunk}

    except Exception as e:
        yield {"type": "error", "message": f"Ошибка генерации: {e}"}
        return

    full_text = "".join(full_text_parts).strip()
    word_count = len(full_text.split())

    # Сохраняем как draft
    qa_json_str = (json.dumps(qa_answers, ensure_ascii=False)
                   if qa_answers else None)
    _save_chapter_text(num, ctx["chapter"], full_text, word_count,
                       qa_json=qa_json_str)

    yield {
        "type":       "done",
        "num":        num,
        "word_count": word_count,
        "chars":      len(full_text),
    }


def _next_or_none(it):
    try:
        return next(it)
    except StopIteration:
        return None


def _save_chapter_text(num: int, plan: dict, text: str, wc: int,
                       qa_json: str | None = None) -> None:
    plan_json = json.dumps(plan, ensure_ascii=False)
    with db.conn() as c:
        c.execute(
            """INSERT INTO chapters(num, title, pov_char, plan_json, text,
                                    status, word_count, created_at, updated_at,
                                    qa_json)
               VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
               ON CONFLICT(num) DO UPDATE SET
                   title      = excluded.title,
                   pov_char   = excluded.pov_char,
                   plan_json  = excluded.plan_json,
                   text       = excluded.text,
                   status     = 'draft',
                   word_count = excluded.word_count,
                   updated_at = excluded.updated_at,
                   qa_json    = COALESCE(excluded.qa_json, chapters.qa_json)""",
            (
                num,
                plan.get("title") or f"Глава {num}",
                plan.get("pov"),
                plan_json,
                text,
                wc,
                db.now(),
                db.now(),
                qa_json,
            ),
        )


def save_manual_text(num: int, text: str) -> int:
    """Сохранить отредактированный вручную или вставленный текст.
    Если строки в таблице chapters ещё нет — создаёт её."""
    wc = len(text.split())
    with db.conn() as c:
        cur = c.execute(
            """UPDATE chapters
                  SET text = ?, word_count = ?, updated_at = ?
                WHERE num = ?""",
            (text, wc, db.now(), num),
        )
        if cur.rowcount == 0:
            c.execute(
                """INSERT INTO chapters
                       (num, title, pov_char, plan_json, text,
                        status, word_count, created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, ?, 'draft', ?, ?, ?)""",
                (num, f"Глава {num}", text, wc, db.now(), db.now()),
            )
    return wc

# ────────────────────────────────────────────────────────────────
# Промпт как текст (для внешних моделей)
# ────────────────────────────────────────────────────────────────

def build_prompt_text(num: int) -> dict:
    """Возвращает system-промпт и user-payload как готовый текст."""
    project = db.get_project()
    if not project:
        raise ValueError("Проект не создан.")

    bible = db.get_full_bible()
    ctx_data = build_context(project, bible, num,
                             word_target=_chapter_words())

    system = _system_prompt()
    user_payload = {"task": "chapter_writer", "input": ctx_data}
    user = json.dumps(user_payload, ensure_ascii=False, indent=2)

    combined = (
        "=== SYSTEM ===\n" + system.rstrip() + "\n\n"
        "=== USER ===\n" + user + "\n"
    )
    return {
        "system":       system,
        "user":         user,
        "combined":     combined,
        "system_chars": len(system),
        "user_chars":   len(user),
    }


def _strip_outer_fence(s: str) -> str:
    """Если весь текст обёрнут в ``` … ``` — снимает обёртку.
    Внутренние ``` не трогает."""
    t = s.strip()
    if t.startswith("```") and t.endswith("```") and t.count("```") == 2:
        first_nl = t.find("\n")
        if first_nl > 0:
            inner = t[first_nl + 1:].rstrip()
            if inner.endswith("```"):
                inner = inner[:-3].rstrip()
            return inner
    return s


def paste_external_text(num: int, text: str) -> int:
    """Принять текст от внешней модели. Возвращает word_count."""
    text = _strip_outer_fence(text or "")
    return save_manual_text(num, text)

# ────────────────────────────────────────────────────────────────
# Уточняющие вопросы перед генерацией
# ────────────────────────────────────────────────────────────────

async def ask_questions(num: int) -> dict:
    """Задаёт модели вопрос: какие решения пользователю принять до
    написания главы. Возвращает {ok, questions} или {ok: False, error}."""
    project = db.get_project()
    if not project:
        return {"ok": False, "error": "Проект не создан."}

    bible = db.get_full_bible()
    try:
        ctx_data = build_context(project, bible, num,
                                 word_target=_chapter_words())
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    system = _questions_system_prompt()
    user_payload = {"task": "chapter_questions", "input": ctx_data}
    messages = [
        {"role": "system", "content": system},
        {"role": "user",
         "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(
            None,
            lambda: llm.chat(messages, stream=False,
                             temperature=0.7, max_tokens=2500),
        )
    except Exception as e:
        return {"ok": False, "error": f"Ошибка запроса к модели: {e}"}

    from pipeline.json_utils import parse_json
    try:
        data = parse_json(raw)
    except Exception as e:
        return {"ok": False, "error": f"Не удалось распарсить JSON: {e}",
                "raw": raw[:500]}

    questions = data.get("questions") or []
    if not isinstance(questions, list) or not (3 <= len(questions) <= 5):
        return {"ok": False,
                "error": f"Ожидалось 3–5 вопросов, получено {len(questions)}.",
                "raw": data}

    return {"ok": True, "questions": questions}