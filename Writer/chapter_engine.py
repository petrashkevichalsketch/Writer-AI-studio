"""Генерация главы с SSE-стримом. Возвращает async-генератор событий."""

import asyncio
import json
from typing import AsyncIterator

import config
import db
import llm
import prompt_loader
from context_builder import build_context
from translations import trf as _t

# Автосейв черновика каждые N знаков стрима — обрыв соединения
# не должен уничтожать десять минут генерации.
_AUTOSAVE_EVERY_CHARS = 1500

# Если модель выдала меньше этой доли целевого объёма — просим продолжить.
_CONTINUATION_THRESHOLD = 0.6


def _system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_writer")


def _questions_system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_questions")


def _book_lang() -> str:
    """Язык КНИГИ (не UI): промпты продолжения и заголовки глав."""
    return (db.get_project() or {}).get("language", "ru")


def _default_title(num: int) -> str:
    return f"Chapter {num}" if _book_lang() == "en" else f"Глава {num}"


def _chapter_words() -> int:
    """Целевой объём главы: override из настроек, а если пусто —
    слова на главу из формата книги проекта (рассказ/повесть/роман)."""
    raw = (db.get_setting("chapter_words") or "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    project = db.get_project() or {}
    fmt_key = project.get("book_format") or config.DEFAULT_BOOK_FORMAT
    fmt = (config.BOOK_FORMATS.get(fmt_key)
           or config.BOOK_FORMATS[config.DEFAULT_BOOK_FORMAT])
    return fmt["words_per_chapter"]


def _chapter_max_tokens() -> int:
    try:
        return max(2000, int(db.get_setting("chapter_max_tokens") or 12000))
    except (TypeError, ValueError):
        return 12000


async def generate_chapter(num: int,
                           qa_answers: list[dict] | None = None
                           ) -> AsyncIterator[dict]:
    """Async-генератор SSE-событий для генерации одной главы."""
    project = db.get_project()
    if not project:
        yield {"type": "error", "message": _t("Проект не создан.")}
        return

    bible = db.get_full_bible()
    word_target = _chapter_words()
    max_tokens = _chapter_max_tokens()

    try:
        ctx = build_context(project, bible, num,
                            word_target=word_target,
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

    qa_json_str = (json.dumps(qa_answers, ensure_ascii=False)
                   if qa_answers else None)

    def _save(text: str) -> None:
        _save_chapter_text(num, ctx["chapter"], text,
                           len(text.split()), qa_json=qa_json_str)

    full_text_parts: list[str] = []
    saved_chars = 0
    try:
        stream = llm.chat(
            messages,
            stream=True,
            temperature=0.8,
            max_tokens=max_tokens,
        )
        # llm.chat(stream=True) возвращает синхронный итератор.
        # Обернём в executor, чтобы не блокировать event loop.
        loop = asyncio.get_running_loop()
        it = iter(stream)
        while True:
            chunk = await loop.run_in_executor(None, _next_or_none, it)
            if chunk is None:
                break
            full_text_parts.append(chunk)
            yield {"type": "chunk", "text": chunk}
            if len(chunk) and sum(map(len, full_text_parts)) - saved_chars \
                    >= _AUTOSAVE_EVERY_CHARS:
                saved_chars = sum(map(len, full_text_parts))
                _save("".join(full_text_parts).strip())

    except Exception as e:
        partial = "".join(full_text_parts).strip()
        if partial:
            _save(partial)
            yield {
                "type": "warning",
                "message": _t("Соединение оборвалось — частичный текст "
                              "({n} слов) сохранён как черновик.",
                              n=len(partial.split())),
            }
            yield {"type": "error",
                   "message": _t("Ошибка генерации: {e}", e=e)}
        return

    full_text = "".join(full_text_parts).strip()
    word_count = len(full_text.split())

    # Короткая глава (MoE-модели склонны обрывать): ОДИН запрос продолжения.
    if word_count < int(word_target * _CONTINUATION_THRESHOLD):
        yield {"type": "continuing", "have": word_count, "target": word_target}
        try:
            cont_stream = llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user",
                     "content": (
                         (
                             "You were writing a chapter but stopped short "
                             "of the target. The last paragraphs of what "
                             "you wrote:\n\n"
                             + full_text[-1500:]
                             + f"\n\n{word_count} of {word_target} words "
                               "written. Continue exactly from where you "
                               "stopped — no repetitions, no recapping "
                               "what is already written, bring the chapter "
                               "to a logical finish."
                         )
                         if _book_lang() == "en" else
                         (
                             "Ты писал главу, но оборвал её раньше цели. "
                             "Последние абзацы написанного:\n\n"
                             + full_text[-1500:]
                             + f"\n\nНаписано {word_count} слов из {word_target}. "
                               "Продолжи ровно с места обрыва — без повторов, "
                               "без пересказа написанного, доведи главу до "
                               "логического завершения."
                         )
                     )},
                ],
                stream=True,
                temperature=0.8,
                max_tokens=max_tokens,
            )
            cit = iter(cont_stream)
            while True:
                chunk = await loop.run_in_executor(None, _next_or_none, cit)
                if chunk is None:
                    break
                full_text_parts.append(chunk)
                yield {"type": "chunk", "text": chunk}
        except Exception as e:
            yield {"type": "warning",
                   "message": _t("Продолжение не удалось: {e}", e=e)}

        full_text = "".join(full_text_parts).strip()
        word_count = len(full_text.split())

    # Сохраняем как draft
    _save(full_text)

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
                plan.get("title") or _default_title(num),
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
    Если строки в таблице chapters ещё нет — создаёт её.

    Ручная правка после применения патча возвращает главу в draft:
    текст больше не соответствует патчу, на котором основан канон."""
    wc = len(text.split())
    with db.conn() as c:
        cur = c.execute(
            """UPDATE chapters
                  SET text = ?, word_count = ?, updated_at = ?,
                      status = CASE WHEN status = 'accepted'
                                    THEN 'draft' ELSE status END
                WHERE num = ?""",
            (text, wc, db.now(), num),
        )
        if cur.rowcount == 0:
            c.execute(
                """INSERT INTO chapters
                       (num, title, pov_char, plan_json, text,
                        status, word_count, created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, ?, 'draft', ?, ?, ?)""",
                (num, _default_title(num), text, wc, db.now(), db.now()),
            )
    return wc

# ────────────────────────────────────────────────────────────────
# Промпт как текст (для внешних моделей)
# ────────────────────────────────────────────────────────────────

def build_prompt_text(num: int) -> dict:
    """Возвращает system-промпт и user-payload как готовый текст."""
    project = db.get_project()
    if not project:
        raise ValueError(_t("Проект не создан."))

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
        return {"ok": False, "error": _t("Проект не создан.")}

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

    loop = asyncio.get_running_loop()
    from pipeline.json_utils import parse_json, JSONParseError

    # Reasoning-модели тратят бюджет на рассуждения и обрываются до JSON:
    # даём запас токенов и одну строгую повторную попытку.
    retry_note = (
        "Your previous answer was not valid JSON (or got cut off before "
        "the JSON). Return ONLY the JSON object with the questions — no "
        "reasoning, no explanations, nothing before or after. The first "
        "character must be '{'."
        if prompt_loader.current_language() == "en" else
        "Предыдущий ответ не был валидным JSON (или оборвался до JSON). "
        "Верни ТОЛЬКО JSON-объект с вопросами — без рассуждений и "
        "пояснений, ничего до и после. Первый символ — «{»."
    )

    raw = ""
    try:
        for attempt in (1, 2):
            raw = await loop.run_in_executor(
                None,
                lambda: llm.chat(messages, stream=False,
                                 temperature=0.7, max_tokens=5000),
            )
            try:
                data = parse_json(raw)
                break
            except JSONParseError:
                if attempt == 2:
                    raise
                messages = [
                    messages[0],
                    {"role": "user", "content": retry_note},
                ]
    except JSONParseError as e:
        return {"ok": False, "error": _t("Не удалось распарсить JSON: {e}", e=e),
                "raw": raw[:500]}
    except Exception as e:
        return {"ok": False, "error": _t("Ошибка запроса к модели: {e}", e=e)}

    questions = data.get("questions") or []
    if not isinstance(questions, list) or not (3 <= len(questions) <= 5):
        return {"ok": False,
                "error": _t("Ожидалось 3–5 вопросов, получено {n}.",
                            n=len(questions)),
                "raw": data}

    return {"ok": True, "questions": questions}
