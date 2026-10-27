"""OpenAI-совместимый адаптер к локальной LLM (Unsloth и др.)."""

import json
from typing import Iterator, Optional
from urllib.parse import urlparse

import httpx

import db
from translations import translate as _t


class LLMError(RuntimeError):
    pass


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
         **extra) -> str | Iterator[str]:
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
        content = (msg.get("content") or "").strip()
        if not content:
            content = (msg.get("reasoning_content")
                       or msg.get("reasoning")
                       or "").strip()
        return content

    def _gen() -> Iterator[str]:
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
                if delta.get("content"):
                    yield delta["content"]

    return _gen()
