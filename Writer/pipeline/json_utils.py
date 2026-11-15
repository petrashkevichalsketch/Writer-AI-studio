"""Парсинг JSON из ответа LLM: снимаем markdown, вырезаем лишний текст,
пробуем несколько стратегий для битого JSON — вплоть до посимвольного
ремонта (пропущенные запятые, неэкранированные кавычки внутри значений,
обрыв ответа без закрывающих скобок)."""

import json
import re
from typing import Any

from translations import trf as _t


class JSONParseError(ValueError):
    pass


_TRAILING_COMMA = re.compile(r",\s*([}\]])")

# после закрывающей кавычки значения — ключ, объект или конец значения
_CLOSER_NEXT = (":", "}", "]", "{", "[")


def _extract_block(s: str) -> tuple[str, bool]:
    """Первый {..} или [..] с учётом баланса скобок и строк;
    (текст, закрыт ли блок).

    Оборванный ответ не режется по последней внутренней скобке (старое
    поведение молча теряло хвост) — его закроет ремонт.
    """
    i_obj = s.find("{")
    i_arr = s.find("[")
    if i_obj < 0 and i_arr < 0:
        raise JSONParseError(_t("JSON не найден: {text}", text=repr(s[:200])))
    if i_obj >= 0 and (i_arr < 0 or i_obj < i_arr):
        start = i_obj
    else:
        start = i_arr

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return s[start:i + 1], True
    return s[start:], False


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _repair_json(s: str, inner_comma: bool = False) -> tuple[str, bool]:
    """Посимвольный ремонт битого JSON из LLM.

    Чинит: пропущенные запятые между значениями, неэкранированные
    кавычки внутри строк («сказал "привет"»), сырые переводы строк в
    значениях, недостающие закрывающие скобки.

    Возвращает (текст, оборван_ли_ответ). Обрыв — строка или значение
    не закрылись к концу текста: часть данных потеряна навсегда,
    «заклеенный» объект неполон; обычный ремонт таких случаев не
    маскирует, а parse_json даст внятную ошибку.

    inner_comma=True — агрессивный режим: кавычка перед «,» считается
    внутренней, если после запятой не идёт «ключ»: — нужно для прозы
    вида «сказал "привет", и ушёл». Обычный режим считает её закрытием
    значения (стандартная развилка после значения).
    """
    out: list[str] = []
    stack: list[str] = []
    in_str = False
    esc = False
    after_colon = False   # ждём значение — запятая перед ним не нужна
    after_open = True     # начало документа = «только что открыли структуру»
    after_comma = False
    n = len(s)
    i = 0
    while i < n:
        ch = s[i]
        if in_str:
            if esc:
                out.append(ch)
                esc = False
            elif ch == "\\":
                out.append(ch)
                esc = True
            elif ch == '"':
                # закрытие строки или внутренняя кавычка? смотрим вперёд
                j = i + 1
                while j < n and s[j] in " \t\r\n":
                    j += 1
                nxt = s[j] if j < n else ""
                if nxt in _CLOSER_NEXT or j >= n or nxt == '"':
                    closer = True
                elif nxt == ",":
                    if inner_comma:
                        # «, "ключ":» — всё же закрытие; «, и дальше проза» —
                        # внутренняя кавычка
                        k = j + 1
                        while k < n and s[k] in " \t\r\n":
                            k += 1
                        m = re.match(r'"[^"\n]{1,80}"\s*:', s[k:])
                        closer = bool(m)
                    else:
                        closer = True
                else:
                    closer = False
                if closer:
                    out.append('"')
                    in_str = False
                else:
                    out.append('\\"')
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                pass
            else:
                out.append(ch)
            i += 1
            continue
        # ── вне строки ──
        if ch == '"':
            if not (after_colon or after_open or after_comma):
                out.append(",")  # пропущенная запятая перед новым значением
            out.append('"')
            in_str = True
            esc = False
            after_colon = after_open = after_comma = False
        elif ch in "{[":
            if not (after_colon or after_open or after_comma):
                out.append(",")
            out.append(ch)
            stack.append("}" if ch == "{" else "]")
            after_colon = after_comma = False
            after_open = True
        elif ch == ":":
            out.append(ch)
            after_colon = True
        elif ch == ",":
            out.append(ch)
            after_comma = True
        elif ch in "}]":
            # mismatched-скобки чиним по собственному стеку
            if stack:
                out.append(stack.pop())
            after_colon = after_open = after_comma = False
        elif ch.isspace():
            out.append(ch)
        else:
            # скаляр (число, true/false/null и т.п.)
            out.append(ch)
            after_colon = after_open = after_comma = False
        i += 1

    # ── обрыв ответа ──
    truncated = in_str or after_colon
    if in_str:
        out.append('"')
    if after_colon:
        out.append("null")
    while stack:
        out.append(stack.pop())
    return _TRAILING_COMMA.sub(r"\1", "".join(out)), truncated


def parse_json(text: str) -> Any:
    if not text:
        raise JSONParseError(_t("Пустой ответ модели."))

    s = _strip_fences(text)
    chunk, _closed = _extract_block(s)

    candidates: list[tuple[str, bool]] = [
        (chunk, False),
        (_TRAILING_COMMA.sub(r"\1", chunk), False),   # убрать trailing comma
        _repair_json(chunk),                          # обычный ремонт
        _repair_json(chunk, inner_comma=True),        # кавычки в прозе
    ]

    last_err: Exception | None = None
    truncated_result: Any = None
    for c, was_truncated in candidates:
        # обычный, потом strict=False (разрешает control-символы в строках)
        for kwargs in ({}, {"strict": False}):
            try:
                parsed = json.loads(c, **kwargs)
            except json.JSONDecodeError as e:
                last_err = e
            except Exception as e:
                last_err = e
            else:
                if not was_truncated:
                    return parsed
                if truncated_result is None:
                    truncated_result = parsed

    if truncated_result is not None:
        # Ответ обрезан и «заклеен»: объект парсится, но часть данных
        # потеряна навсегда. Отдача в валидатор дала бы каскад
        # «поле X пусто» вместо понятной причины — объясняем прямо.
        raise JSONParseError(_t(
            "JSON оборван: ответ модели не влез в max_tokens, данные "
            "неполны. Начало: {chunk}", chunk=repr(chunk[:150])))

    raise JSONParseError(
        _t("JSON не парсится: {err}. Начало: {chunk}",
           err=last_err, chunk=repr(chunk[:200]))
    )
