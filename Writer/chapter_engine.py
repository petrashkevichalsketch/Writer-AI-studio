"""Генерация главы с SSE-стримом. Возвращает async-генератор событий."""

import asyncio
import json
import queue
import re
import threading
from difflib import SequenceMatcher
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

# Один одновременный запуск на главу: генерация, по-сценная генерация и
# редактура делят общий лок. Второй параллельный запрос гонял бы модель
# поверх первого — на локальной модели это переполнение видеопамяти.
_chapter_busy: set[int] = set()


def _busy_message(num: int) -> str:
    return _t("Для главы {n} уже выполняется генерация или редактура — "
              "дождитесь её завершения.", n=num)


def _system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_writer")


def _questions_system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_questions")


def _editor_system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_editor")


def _book_lang() -> str:
    """Язык КНИГИ (не UI): промпты продолжения и заголовки глав."""
    return (db.get_project() or {}).get("language", "ru")


def _default_title(num: int) -> str:
    return f"Chapter {num}" if _book_lang() == "en" else f"Глава {num}"


def _is_default_title(title: str | None, num: int) -> bool:
    """Title отсутствует или равен дефолту «Глава N»/«Chapter N»
    (проверяются оба языка — книга могла сменить язык)."""
    t = (title or "").strip()
    if not t:
        return True
    return t in (f"Глава {num}", f"Chapter {num}")


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


def _chapter_profile() -> str:
    """Какой профиль LLM пишет главы: 'main' или 'strong' (Настройки,
    переключатель на странице главы). Неизвестное значение — 'main'."""
    p = (db.get_setting("chapter_profile") or "main").strip()
    return p if p in ("main", "strong") else "main"


def _model_label(profile: str) -> str:
    """Имя модели выбранного профиля — для показа в UI."""
    s = db.get_settings()
    if profile == "strong":
        return s.get("strong_llm_model_name") or "strong"
    return s.get("llm_model_name") or "local"


async def generate_chapter(num: int,
                           qa_answers: list[dict] | None = None
                           ) -> AsyncIterator[dict]:
    """Async-генератор SSE-событий для генерации одной главы (одним вызовом).

    Общий лок с по-сценной генерацией и редактурой: повторный запуск
    (второе окно, перезагрузка страницы) получает ошибку, а не второй
    параллельный запрос к модели."""
    if num in _chapter_busy:
        yield {"type": "error", "message": _busy_message(num)}
        return
    _chapter_busy.add(num)
    try:
        async for ev in _generate_chapter_impl(num, qa_answers=qa_answers):
            yield ev
    finally:
        _chapter_busy.discard(num)


async def _generate_chapter_impl(num: int,
                                 qa_answers: list[dict] | None = None
                                 ) -> AsyncIterator[dict]:
    project = db.get_project()
    if not project:
        yield {"type": "error", "message": _t("Проект не создан.")}
        return

    bible = db.get_full_bible()
    word_target = _chapter_words()
    max_tokens = _chapter_max_tokens()
    profile = _chapter_profile()

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
        "profile": profile,
        "model":   _model_label(profile),
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
            profile=profile,
        )
        # llm.chat(stream=True) возвращает синхронный итератор пар
        # (kind, text): 'reasoning' — мысли модели, 'content' — проза.
        # Обернём в executor, чтобы не блокировать event loop.
        loop = asyncio.get_running_loop()
        it = iter(stream)
        while True:
            item = await loop.run_in_executor(None, _next_or_none, it)
            if item is None:
                break
            kind, text = item
            if kind == "reasoning":
                # мысли идут в UI, но не в текст главы и не в автосейв
                yield {"type": "thinking", "text": text}
                continue
            full_text_parts.append(text)
            yield {"type": "chunk", "text": text}
            if len(text) and sum(map(len, full_text_parts)) - saved_chars \
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
                profile=profile,
            )
            cit = iter(cont_stream)
            while True:
                item = await loop.run_in_executor(None, _next_or_none, cit)
                if item is None:
                    break
                kind, text = item
                if kind == "reasoning":
                    yield {"type": "thinking", "text": text}
                    continue
                full_text_parts.append(text)
                yield {"type": "chunk", "text": text}
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
    текст больше не соответствует патчу, на котором основан канон.

    Название берётся из плана: главы, вставленные через «Вставить текст»,
    не должны навсегда оставаться с дефолтным «Глава N» (экспорт печатал
    дубль «Глава 5. Глава 5»). Реальное название не перезатирается."""
    wc = len(text.split())
    planned = db.get_outline_title(num) or _default_title(num)
    with db.conn() as c:
        row = c.execute("SELECT title FROM chapters WHERE num = ?",
                        (num,)).fetchone()
        if row is None:
            c.execute(
                """INSERT INTO chapters
                       (num, title, pov_char, plan_json, text,
                        status, word_count, created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, ?, 'draft', ?, ?, ?)""",
                (num, planned, text, wc, db.now(), db.now()),
            )
        else:
            new_title = (planned if _is_default_title(row["title"], num)
                         else row["title"])
            c.execute(
                """UPDATE chapters
                      SET text = ?, word_count = ?, updated_at = ?,
                          title = ?,
                          status = CASE WHEN status = 'accepted'
                                        THEN 'draft' ELSE status END
                    WHERE num = ?""",
                (text, wc, db.now(), new_title, num),
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
                                 temperature=0.7, max_tokens=5000,
                                 profile=_chapter_profile()),
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


# ────────────────────────────────────────────────────────────────
# Корректор: стилистическая вычитка написанной главы
# ────────────────────────────────────────────────────────────────

# Разделитель сцен задан промптом chapter_writer: строка «***».
# \r учитан: вставленный вручную текст приходит с Windows-переводами строк.
_SCENE_SEP_RE = re.compile(r"(?m)^[ \t]*\*\*\*[ \t\r]*$")

# Граница «Шаг 2 / Step 2» в ответе корректора — за ней редактура.
_STEP2_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:#{1,6}[ \t]*)?\**[ \t]*(?:Шаг|Step)[ \t]*2\b[^\n]*",
    re.IGNORECASE,
)

# На короткой сцене длинный бюджет не нужен и даже вреден: модель
# начинает «раздувать» ответ до лимита.
_SCENE_MAX_TOKENS_CAP = 8000


def _pump_llm(q: queue.Queue, messages: list[dict], profile: str,
              max_tokens: int, stop: threading.Event,
              temperature: float = 0.4) -> None:
    """Читает стрим LLM в отдельном потоке, кладёт пары (kind, chunk).

    stop выставляется при отмене (клиент отключился): чтение
    останавливается на ближайшем чанке, соединение с моделью
    закрывается и видеопамять освобождается — запрос не висит
    призраком поверх следующего запуска."""
    try:
        stream = llm.chat(messages, stream=True, temperature=temperature,
                          max_tokens=max_tokens, profile=profile)
        for kind, chunk in stream:
            if stop.is_set():
                break
            q.put((kind, chunk))
    except Exception as e:  # noqa: BLE001 — уйдёт в SSE событием ошибки
        q.put(("error", e))
    finally:
        q.put(None)


def split_scenes(text: str) -> list[str]:
    """Разбить главу на сцены по строке-разделителю «***».
    Нет разделителей — глава возвращается одной сценой."""
    scenes = [s.strip() for s in _SCENE_SEP_RE.split(text or "")]
    return [s for s in scenes if s]


def extract_edited_scene(answer: str) -> str | None:
    """Достать из ответа корректора блок «Шаг 2» — отредактированный текст.
    Нет границы или после неё пусто — None."""
    # весь ответ в ```…``` — снимаем обёртку ДО поиска границы
    s = _strip_outer_fence((answer or "").strip())
    m = _STEP2_RE.search(s)
    if not m:
        return None
    part2 = s[m.end():].strip()
    part2 = re.sub(r"^[ \t]*[:.—-][ \t]*", "", part2).strip()
    return part2 or None


def _editor_scene_addendum() -> str:
    """Дополнение к системному промпту для по-сценного режима."""
    if prompt_loader.current_language() == "en":
        return ("\n\nScene mode: the user message starts with CONTEXT — "
                "previously edited scenes of this chapter. Do NOT edit them; "
                "they are shown only for style and voice consistency and to "
                "catch cross-scene repetitions. Edit ONLY the scene in the "
                "'TEXT FOR EDITING' block and give notes only for it.")
    return ("\n\nРежим по-сценной редактуры: в user-сообщении сначала идёт "
            "КОНТЕКСТ — уже отредактированные сцены этой главы. Их НЕ "
            "редактируй; они показаны для согласованности стиля, голосов "
            "персонажей и сквозных повторов. Редактируй ТОЛЬКО сцену из "
            "блока «ТЕКСТ ДЛЯ РЕДАКТИРОВАНИЯ», замечания давай только "
            "по ней.")


def _editor_scene_user(idx: int, total: int, scene_text: str,
                       context: list[tuple[int, str]]) -> str:
    """User-сообщение для одной сцены: контекст предыдущих сцен + сцена."""
    parts: list[str] = []
    if context:
        if prompt_loader.current_language() == "en":
            parts.append("=== CONTEXT: previously edited scenes of this "
                         "chapter (do not edit — style reference only) ===")
        else:
            parts.append("=== КОНТЕКСТ: уже отредактированные сцены главы "
                         "(не редактируй — только для согласованности "
                         "стиля) ===")
        for j, txt in context:
            parts.append(f"--- Сцена {j} ---\n{txt}")
    if prompt_loader.current_language() == "en":
        parts.append(f"=== TEXT FOR EDITING (scene {idx} of {total}) ===")
    else:
        parts.append(f"=== ТЕКСТ ДЛЯ РЕДАКТИРОВАНИЯ "
                     f"(сцена {idx} из {total}) ===")
    parts.append(scene_text)
    return "\n\n".join(parts)


async def editor_review(num: int) -> AsyncIterator[dict]:
    """Async-генератор SSE-событий стилистической проверки главы.

    Общий лок с генерацией (см. _chapter_busy): повторный запуск
    (второе окно, перезагрузка страницы) получает ошибку, а не второй
    параллельный запрос к модели."""
    if num in _chapter_busy:
        yield {"type": "error", "message": _busy_message(num)}
        return
    _chapter_busy.add(num)
    try:
        async for ev in _editor_review_scenes(num):
            yield ev
    finally:
        # снимается и при отмене (GeneratorExit) — обрыв клиента
        # освобождает главу для следующего запуска
        _chapter_busy.discard(num)


async def _editor_review_scenes(num: int) -> AsyncIterator[dict]:
    """Сценный проход корректора (см. editor_review)."""
    project = db.get_project()
    if not project:
        yield {"type": "error", "message": _t("Проект не создан.")}
        return

    ch = db.get_chapter(num)
    text = (ch or {}).get("text") or ""
    if not text.strip():
        yield {"type": "error",
               "message": _t("Глава пуста — сначала сгенерируйте или "
                             "вставьте текст.")}
        return

    profile = _chapter_profile()
    scenes = split_scenes(text) or [text.strip()]
    total = len(scenes)

    yield {
        "type":   "meta",
        "num":    num,
        "words":  len(text.split()),
        "chars":  len(text),
        "scenes": total,
        "profile": profile,
        "model":  _model_label(profile),
    }

    system = _editor_system_prompt()
    if total > 1:
        system += _editor_scene_addendum()

    max_tokens = min(_chapter_max_tokens(), _SCENE_MAX_TOKENS_CAP)
    edited_scenes: list[str | None] = []
    total_chars = 0
    loop = asyncio.get_running_loop()

    for i, scene in enumerate(scenes, 1):
        yield {"type": "scene", "num": i, "total": total}

        context = [(j, edited_scenes[j - 1])
                   for j in range(1, i) if edited_scenes[j - 1]]
        messages = [
            {"role": "system", "content": system},
            {"role": "user",
             "content": _editor_scene_user(i, total, scene, context)},
        ]

        # Стрим читает помпо-поток; async-сторона забирает чанки из
        # очереди с таймаутом — отмена доходит до потока через stop.
        q: queue.Queue = queue.Queue()
        stop = threading.Event()
        threading.Thread(
            target=_pump_llm,
            args=(q, messages, profile, max_tokens, stop),
            daemon=True,
        ).start()

        parts: list[str] = []
        try:
            while True:
                try:
                    item = await loop.run_in_executor(
                        None, lambda: q.get(timeout=0.3))
                except queue.Empty:
                    continue
                if item is None:
                    break
                kind, val = item
                if kind == "error":
                    raise val
                if kind == "reasoning":
                    yield {"type": "thinking", "text": val}
                    continue
                parts.append(val)
                yield {"type": "chunk", "text": val}
        except Exception as e:
            yield {"type": "error",
                   "message": _t("Ошибка корректора: {e}", e=e)}
            return
        finally:
            stop.set()

        answer = "".join(parts).strip()
        if not answer:
            yield {"type": "error",
                   "message": _t("Модель вернула пустой ответ.")}
            return

        total_chars += len(answer)
        edited = extract_edited_scene(answer)
        edited_scenes.append(edited)

        if edited is None:
            yield {"type": "warning",
                   "message": _t("Редактуру сцены {i} не удалось распознать — "
                                 "в итоговый текст пойдёт исходная сцена.",
                                 i=i)}
        yield {"type": "scene_done", "num": i, "total": total,
               "edited_ok": edited is not None,
               "original_scene": scene if edited is None else None}

    yield {"type": "done", "num": num, "chars": total_chars, "scenes": total}


# ────────────────────────────────────────────────────────────────
# По-сценная генерация главы (кнопка «По сценам»)
# ────────────────────────────────────────────────────────────────

def _scene_system_prompt() -> str:
    return prompt_loader.get_prompt("chapter_writer_scene")


async def _drain_llm(q: queue.Queue, loop, stop: threading.Event):
    """Забирает пары (kind, chunk) из очереди помпы до конца стрима.

    Отмена доходит до помпы через stop (finally): обрыв клиента
    закрывает соединение с моделью и освобождает видеопамять."""
    try:
        while True:
            try:
                item = await loop.run_in_executor(
                    None, lambda: q.get(timeout=0.3))
            except queue.Empty:
                continue
            if item is None:
                return
            kind, val = item
            if kind == "error":
                raise val
            yield kind, val
    finally:
        stop.set()


def _normalize_beat(beat, i: int) -> dict:
    """Бит плана к единому виду (строки старого формата — в dict)."""
    if isinstance(beat, dict):
        b = dict(beat)
        b.setdefault("scene", i)
        return b
    return {"scene": i, "task": str(beat)}


def _scene_word_target(beat: dict, chapter_words: int, total: int) -> int:
    """Целевой объём сцены: из бита, иначе поровну от главы."""
    raw = beat.get("word_target")
    if raw:
        try:
            return max(100, int(raw))
        except (TypeError, ValueError):
            pass
    return max(200, chapter_words // max(1, total))


# Ответ-отказ: модель комментирует задание (перечисляет поля промпта,
# просит прислать JSON, отказывается писать) вместо прозы сцены.
# Наблюдаемые случаи: «Поле `write_scene` указывает…», «в вашем сообщении
# отсутствует JSON…». Ловим характерные маркеры; литературная проза их
# не содержит.
_REFUSAL_RE = re.compile(
    r"`(?:write_scene|written_scenes|scene_target_words|action_chain|result)`"
    r"|отсутствует JSON|не могу выполнить|не вижу в (?:вашем|твоём) запросе"
    r"|предоставьте (?:новый план|полный JSON)|уточните номер сцены"
    r"|I cannot (?:fulfill|complete|proceed)"
    r"|I can't (?:fulfill|complete|proceed)"
    r"|as an AI\b|send (?:the |us )?(?:full |complete )?JSON",
    re.IGNORECASE,
)


def _looks_like_refusal(text: str) -> bool:
    return bool(_REFUSAL_RE.search(text or ""))


def _retry_note() -> str:
    """Прямое указание модели после ответа-отказа (язык — язык книги)."""
    if _book_lang() == "en":
        return ("Your previous reply was a service comment, not fiction. "
                "Everything you need is already in this conversation: the "
                "scene plan and the chapter context. Do not discuss the "
                "task, do not ask for JSON, do not list what has been "
                "written. Reply with ONLY the plain text of the scene — "
                "the first character must begin the prose.")
    return ("Твой предыдущий ответ — служебный комментарий, а не "
            "художественный текст. Всё нужное уже есть в этой переписке: "
            "план сцены, контекст главы. Не обсуждай задание, не проси "
            "прислать JSON и не перечисляй написанное. Ответь ТОЛЬКО "
            "чистым текстом сцены — первый символ ответа начинает прозу.")


# Деградация «копия сцены»: слабые/квантованные модели на длинном
# противоречивом контексте (бит уже показан в written_scenes) начинают
# дословно повторять последнюю написанную сцену. Наблюдалось: сцена 3
# совпала со сценой 2 байт в байт. Ловим программно по сходству.
_DUP_RATIO = 0.6


def _find_duplicate(text: str, prev: list[str]) -> int | None:
    """Номер первой из prev-сцен, с которой text совпадает больше чем
    на _DUP_RATIO; None — если дубликата нет."""
    if not text or not prev:
        return None
    head = text[:3000]
    best, idx = 0.0, None
    for j, s in enumerate(prev, 1):
        r = SequenceMatcher(None, head, s[:3000]).ratio()
        if r > best:
            best, idx = r, j
    return idx if best >= _DUP_RATIO else None


def _dup_note(i: int, j: int) -> str:
    """Прямое указание после копии сцены (язык — язык книги)."""
    if _book_lang() == "en":
        return (f"Your previous reply repeated the text of the "
                f"already-written scene {j}. That is wrong. Scene {i} is "
                f"still NOT written: its beat waits in the data above "
                f"(scene_plan). Write a NEW episode for that beat: new "
                f"actions, new dialogue, new details. Under no "
                f"circumstances repeat the previous scene's text.")
    return (f"Твой предыдущий ответ повторял текст уже написанной сцены "
            f"{j} — так нельзя. Сцена {i} ещё НЕ написана: её бит ждёт в "
            f"данных выше (scene_plan). Напиши НОВЫЙ эпизод по этому "
            f"биту: новые действия, новые диалоги, новые детали. Ни при "
            f"каком условии не повторяй текст предыдущей сцены.")


def _strip_scene_seps(t: str) -> str:
    """Убрать «***» из текста сцены и схлопнуть лишние пустые строки."""
    t = _SCENE_SEP_RE.sub("", t or "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


async def generate_chapter_scenes(num: int,
                                  qa_answers: list[dict] | None = None,
                                  mode: str = "continue",
                                  ) -> AsyncIterator[dict]:
    """По-сценная генерация: один вызов LLM на бит плана, сцены склеиваются
    строкой «***». Единица сохранения — завершённая сцена: прогресс
    возобновления считается по числу сцен в черновике, частичный текст
    сцены в БД не попадает.

    mode: 'continue' — дописать недостающие сцены, 'restart' — с первой."""
    if num in _chapter_busy:
        yield {"type": "error", "message": _busy_message(num)}
        return
    _chapter_busy.add(num)
    try:
        async for ev in _generate_scenes_impl(num, qa_answers, mode):
            yield ev
    finally:
        _chapter_busy.discard(num)


async def _generate_scenes_impl(num: int, qa_answers: list[dict] | None,
                                mode: str) -> AsyncIterator[dict]:
    project = db.get_project()
    if not project:
        yield {"type": "error", "message": _t("Проект не создан.")}
        return

    bible = db.get_full_bible()
    word_target = _chapter_words()
    profile = _chapter_profile()

    try:
        ctx = build_context(project, bible, num,
                            word_target=word_target,
                            qa_answers=qa_answers)
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    beats_raw = ctx["chapter"].get("beats") or []
    if not beats_raw:
        yield {"type": "error",
               "message": _t("В плане главы нет сцен (beats) — по-сценный "
                             "режим требует план outline v2.")}
        return
    beats = [_normalize_beat(b, i) for i, b in enumerate(beats_raw, 1)]
    total = len(beats)

    existing = (db.get_chapter(num) or {}).get("text") or ""
    done_scenes = [] if mode == "restart" else split_scenes(existing)
    if len(done_scenes) >= total:
        yield {"type": "error",
               "message": _t("Все {n} сцен главы уже написаны — "
                             "выберите «написать заново».", n=total)}
        return
    start = len(done_scenes) + 1

    qa_json_str = (json.dumps(qa_answers, ensure_ascii=False)
                   if qa_answers else None)

    yield {
        "type":  "meta",
        "num":   num,
        "title": ctx["chapter"].get("title"),
        "plan":  ctx["chapter"],
        "mode":  mode,
        "total": total,
        "done":  len(done_scenes),
        "chars": [c.get("name") for c in ctx.get("characters") or []],
        "profile": profile,
        "model":   _model_label(profile),
    }

    system = _scene_system_prompt()
    scenes_text = list(done_scenes)
    loop = asyncio.get_running_loop()

    async def run_stream(msgs: list[dict], sink: list[str], temp: float,
                         mt: int):
        """Один отменяемый запрос: чанки копятся в sink и уходят в UI."""
        q: queue.Queue = queue.Queue()
        stop = threading.Event()
        threading.Thread(
            target=_pump_llm,
            args=(q, msgs, profile, mt, stop, temp),
            daemon=True,
        ).start()
        async for kind, val in _drain_llm(q, loop, stop):
            if kind == "reasoning":
                yield {"type": "thinking", "text": val}
                continue
            sink.append(val)
            yield {"type": "chunk", "text": val}

    for i in range(start, total + 1):
        beat = beats[i - 1]
        scene_target = _scene_word_target(beat, word_target, total)
        # Резерв вывода пропорционален сцене: фиксированные 8000 токенов
        # на сцену в 600 слов съедали контекст сервера — промпт с полными
        # written_scenes переставал влезать в n_ctx (HTTP 400).
        scene_max_tokens = min(_chapter_max_tokens(), _SCENE_MAX_TOKENS_CAP,
                               max(6000, scene_target * 5))
        yield {"type": "scene", "num": i, "total": total,
               "word_target": scene_target}

        # Модель видит ТОЛЬКО свою сцену: чужие биты и полные тексты
        # написанных сцен не передаются — на них модели путались
        # (облачные отказывались, локальные копировали чужое). Для
        # стилистики — короткий хвост предыдущей сцены.
        chapter_meta = {k: v for k, v in ctx["chapter"].items()
                        if k != "beats"}
        user_payload = {
            "task": "chapter_scene_writer",
            "input": {**ctx, "chapter": chapter_meta},
            "scene_plan": beat,
            "scene_target_words": scene_target,
            "chapter_position": {"index": i, "total": total,
                                 "is_last": i == total},
            "previous_scene_tail": (scenes_text[-1][-1200:]
                                    if scenes_text else None),
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user",
             "content": json.dumps(user_payload, ensure_ascii=False,
                                   indent=2)},
        ]

        # Сцена 1 задаёт голос главы — свежесть важнее однообразия;
        # дальше температура ниже: меньше дрейфа стиля между сценами.
        temperature = 0.8 if i == 1 else 0.7

        parts: list[str] = []
        try:
            async for ev in run_stream(messages, parts, temperature, scene_max_tokens):
                yield ev
        except Exception as e:
            # Частичный текст сцены не сохраняем: единица возобновления —
            # завершённая сцена, повторный запуск начнёт её заново.
            yield {"type": "error",
                   "message": _t("Ошибка генерации сцены {i}: {e}", i=i, e=e)}
            return

        scene_text = "".join(parts).strip()

        # Отказ: модель ответила комментарием вместо прозы. Один повтор
        # с прямым указанием; при повторном отказе — стоп без сохранения,
        # иначе мусор попадает в главу и каскадом в written_scenes.
        if scene_text and _looks_like_refusal(scene_text):
            yield {"type": "warning",
                   "message": _t("Модель ответила комментарием вместо "
                                 "прозы — повторяю сцену {i}…", i=i)}
            retry_messages = messages + [
                {"role": "assistant", "content": scene_text},
                {"role": "user", "content": _retry_note()},
            ]
            retry_parts: list[str] = []
            try:
                async for ev in run_stream(retry_messages, retry_parts,
                                           temperature, scene_max_tokens):
                    yield ev
            except Exception as e:
                yield {"type": "error",
                       "message": _t("Ошибка генерации сцены {i}: {e}",
                                     i=i, e=e)}
                return
            scene_text = "".join(retry_parts).strip()
            if not scene_text or _looks_like_refusal(scene_text):
                yield {"type": "error",
                       "message": _t("Модель дважды ответила комментарием "
                                     "вместо прозы сцены {i} — сцена не "
                                     "сохранена, написанные ранее сцены "
                                     "целы.", i=i)}
                return

        scene_text = _strip_scene_seps(scene_text)

        # Деградация «копия сцены»: модель повторила уже написанное.
        # Один повтор с прямым указанием бита; при повторе — стоп без
        # сохранения, иначе дубли каскадом попадают в written_scenes.
        dup_of = _find_duplicate(scene_text, scenes_text)
        if dup_of is not None:
            yield {"type": "warning",
                   "message": _t("Сцена {i} повторяет уже написанную "
                                 "сцену {j} — повторяю с указанием "
                                 "бита…", i=i, j=dup_of)}
            retry_messages = messages + [
                {"role": "assistant", "content": scene_text},
                {"role": "user", "content": _dup_note(i, dup_of)},
            ]
            retry_parts: list[str] = []
            try:
                async for ev in run_stream(retry_messages, retry_parts,
                                           temperature, scene_max_tokens):
                    yield ev
            except Exception as e:
                yield {"type": "error",
                       "message": _t("Ошибка генерации сцены {i}: {e}",
                                     i=i, e=e)}
                return
            scene_text = _strip_scene_seps("".join(retry_parts))
            if not scene_text or _find_duplicate(scene_text,
                                                 scenes_text) is not None:
                yield {"type": "error",
                       "message": _t("Модель дважды прислала копию уже "
                                     "написанной сцены вместо сцены {i} — "
                                     "сцена не сохранена, написанные "
                                     "ранее сцены целы.", i=i)}
                return

        words = len(scene_text.split())

        # Короткая сцена (MoE-модели склонны обрывать) — ОДИН запрос
        # продолжения. В отличие от глав-level, он несёт ПОЛНЫЙ контекст
        # (план + написанное) и текст сцены целиком: голое «продолжи»
        # без JSON модель читает как сломанный запрос и отвечает
        # комментарием вместо прозы.
        if scene_text and words < int(scene_target * _CONTINUATION_THRESHOLD):
            yield {"type": "continuing", "have": words,
                   "target": scene_target}
            cont_payload = dict(user_payload)
            cont_payload["scene_text_so_far"] = scene_text
            cont_payload["continue_scene"] = True
            cont_messages = [
                {"role": "system", "content": system},
                {"role": "user",
                 "content": json.dumps(cont_payload, ensure_ascii=False,
                                       indent=2)},
            ]
            cont_parts: list[str] = []
            try:
                async for ev in run_stream(cont_messages, cont_parts,
                                           temperature, scene_max_tokens):
                    yield ev
            except Exception as e:
                yield {"type": "warning",
                       "message": _t("Продолжение сцены не удалось: {e}",
                                     e=e)}
                cont_parts = []
            cont_text = "".join(cont_parts)
            if cont_text.strip() and _looks_like_refusal(cont_text):
                yield {"type": "warning",
                       "message": _t("Продолжение сцены вернуло комментарий "
                                     "вместо прозы — продолжение "
                                     "отброшено.")}
            elif cont_text.strip():
                scene_text = scene_text + cont_text

        scene_text = _strip_scene_seps(scene_text)
        if not scene_text:
            yield {"type": "error",
                   "message": _t("Модель вернула пустой ответ для сцены {i}.",
                                 i=i)}
            return

        scenes_text.append(scene_text)
        joined = "\n\n***\n\n".join(scenes_text)
        _save_chapter_text(num, ctx["chapter"], joined,
                           len(joined.split()), qa_json=qa_json_str)
        yield {"type": "scene_done", "num": i, "total": total,
               "words": len(scene_text.split()),
               "chapter_words": len(joined.split())}

    joined = "\n\n***\n\n".join(scenes_text)
    yield {
        "type":       "done",
        "num":        num,
        "word_count": len(joined.split()),
        "chars":      len(joined),
        "scenes":     total,
    }
