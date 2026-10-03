"""Парсинг JSON из ответа LLM: снимаем markdown, вырезаем лишний текст,
пробуем несколько стратегий для битого JSON."""

import json
import re
from typing import Any


class JSONParseError(ValueError):
    pass


_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _extract_block(s: str) -> str:
    i_obj = s.find("{")
    i_arr = s.find("[")
    if i_obj < 0 and i_arr < 0:
        raise JSONParseError(f"JSON не найден: {s[:200]!r}")
    if i_obj >= 0 and (i_arr < 0 or i_obj < i_arr):
        end = s.rfind("}")
        if end <= i_obj:
            raise JSONParseError("Не закрыта фигурная скобка.")
        return s[i_obj:end + 1]
    end = s.rfind("]")
    if end <= i_arr:
        raise JSONParseError("Не закрыта квадратная скобка.")
    return s[i_arr:end + 1]


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


def parse_json(text: str) -> Any:
    if not text:
        raise JSONParseError("Пустой ответ модели.")

    s = _strip_fences(text)
    chunk = _extract_block(s)

    candidates = [
        chunk,
        _TRAILING_COMMA.sub(r"\1", chunk),   # убрать trailing comma
    ]

    last_err: Exception | None = None
    for c in candidates:
        # обычный, потом strict=False (разрешает control-символы в строках)
        for kwargs in ({}, {"strict": False}):
            try:
                return json.loads(c, **kwargs)
            except json.JSONDecodeError as e:
                last_err = e
            except Exception as e:
                last_err = e

    raise JSONParseError(
        f"JSON не парсится: {last_err}. Начало: {chunk[:200]!r}"
    )