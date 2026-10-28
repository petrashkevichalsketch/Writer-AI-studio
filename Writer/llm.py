"""OpenAI-совместимый адаптер к локальной LLM (Unsloth и др.)."""

import json
import re
from typing import Iterator, Optional
from urllib.parse import urlparse

import httpx

import db
from translations import translate as _t


class LLMError(RuntimeError):
    pass


# Инлайновые размышления: часть моделей (Qwen и др. без reasoning-parser)
# кладёт мысли прямо в content тегами <think>…</think>.
_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_inline_think(text: str) -> str:
    """Вырезать парные <think>…</think> из полного ответа."""
    return _THINK_RE.sub("", text or "").strip()


def _partial_suffix_len(buf: str, tag: str) -> int:
    """Хвост buf, который может быть началом tag (тег порезан границей чанка)."""
    for n in range(min(len(buf), len(tag) - 1), 0, -1):
        if tag.startswith(buf[-n:]):
            return n
    return 0


class _ThinkSplitter:
    """Режет content-стрим на пары ('reasoning'|'content', text).

    Тег, разрезанный границей чанков, держится в буфере до уверенности.
    """

    def __init__(self) -> None:
        self.in_think = False
        self._buf = ""

    def feed(self, text: str) -> Iterator[tuple[str, str]]:
        self._buf += text
        while self._buf:
            tag = _THINK_CLOSE if self.in_think else _THINK_OPEN
            kind = "reasoning" if self.in_think else "content"
            idx = self._buf.find(tag)
            if idx < 0:
                keep = _partial_suffix_len(self._buf, tag)
                emit = len(self._buf) - keep
                if emit:
                    yield (kind, self._buf[:emit])
                    self._buf = self._buf[emit:]
                return
            if idx:
                yield (kind, self._buf[:idx])
            self._buf = self._buf[idx + len(tag):]
            self.in_think = not self.in_think

    def flush(self) -> Iterator[tuple[str, str]]:
        """Конец стрима: остаток буфера — текст текущего режима
        (незакрытый <think> значит, что модель оборвалась на мыслях)."""
        if self._buf:
            yield ("reasoning" if self.in_think else "content", self._buf)
            self._buf = ""


# chat_template_kwargs — расширение локальных серверов (vLLM, TabbyAPI).
# Облачные OpenAI-совместимые API отвечают 400 на неизвестный параметр,
# поэтому шлём его только на localhost.
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _is_local(base_url: str) -> bool:
    try:
        host = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    return host.lower() in _LOCAL_HOSTS


def _cfg():
    s = db.get_settings()
    return (
        s.get("llm_base_url", "").rstrip("/"),
        s.get("llm_api_token", ""),
        s.get("llm_model_name", ""),
        s.get("enable_thinking", "false") == "true",
    )


def _headers(token: str) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_models() -> tuple[list[str], str]:
    """Список моделей. Возвращает (models, error) — error пуст, если всё ок."""
    base, token, _, _ = _cfg()
    if not base:
        return [], _t("base_url не настроен")
    try:
        r = httpx.get(f"{base}/models", headers=_headers(token), timeout=10)
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])], ""
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def chat(messages: list[dict],
         model: Optional[str] = None,
         stream: bool = False,
         temperature: float = 0.8,
         max_tokens: Optional[int] = None,
         **extra) -> str | Iterator[tuple[str, str]]:
    base, token, default_model, thinking = _cfg()
    if not base:
        raise LLMError(_t("LLM base_url не настроен (Settings)."))
    mdl = model or default_model
    if not mdl:
        raise LLMError(_t("LLM model_name не настроен (Settings)."))

    payload = {
        "model": mdl,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if not thinking and _is_local(base):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    payload.update(extra)

    if not stream:
        r = httpx.post(f"{base}/chat/completions",
                       headers=_headers(token), json=payload, timeout=600)
        if r.status_code >= 400:
            raise LLMError(f"{r.status_code}: {r.text[:500]}")
        msg = r.json()["choices"][0]["message"]
        content = _strip_inline_think(msg.get("content") or "")
        if not content:
            content = (msg.get("reasoning_content")
                       or msg.get("reasoning")
                       or "").strip()
        return content

    def _gen() -> Iterator[tuple[str, str]]:
        """Пары (kind, text): 'reasoning' — размышления модели,
        'content' — текст ответа. Размышления берутся из поля
        reasoning_content/reasoning и из инлайновых <think>…</think>."""
        splitter = _ThinkSplitter()
        with httpx.stream("POST", f"{base}/chat/completions",
                          headers=_headers(token), json=payload, timeout=600) as r:
            if r.status_code >= 400:
                body = r.read().decode("utf-8", "ignore")
                raise LLMError(f"{r.status_code}: {body[:500]}")
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                rd = delta.get("reasoning_content") or delta.get("reasoning")
                if rd:
                    yield ("reasoning", rd)
                if delta.get("content"):
                    yield from splitter.feed(delta["content"])
            yield from splitter.flush()

    return _gen()
