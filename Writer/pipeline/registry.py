"""Реестр стадий пайплайна. _ping — для отладки связи с LLM.
Стадии фазы 1 регистрируются в phase1_world."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class StageSpec:
    name: str
    fn: Callable[[dict], Any]
    validator: Optional[Callable[[dict, Any], list[str]]] = None
    max_calls: int = 3
    retry: int = 3
    requires: list[str] = field(default_factory=list)


REGISTRY: dict[str, StageSpec] = {}


def register(spec: StageSpec) -> None:
    REGISTRY[spec.name] = spec


def get(name: str) -> Optional[StageSpec]:
    return REGISTRY.get(name)


# ────────────────────────────────────────────────────────────────
# _ping — проверка связи с LLM
# ────────────────────────────────────────────────────────────────

def _ping_fn(ctx: dict) -> dict:
    import llm
    msg = [
        {"role": "system",
         "content": "Ты тестовый ассистент. Отвечай строго JSON, без markdown."},
        {"role": "user",
         "content": 'Верни JSON вида {"ok": true, "message": "<одно слово по-русски>"}'},
    ]
    text = llm.chat(msg, stream=False, temperature=0.2, max_tokens=64)
    return {"raw": text}


def _ping_validator(ctx: dict, payload: dict) -> list[str]:
    raw = (payload or {}).get("raw", "")
    return [] if raw and raw.strip() else ["Пустой ответ от LLM."]


register(StageSpec(
    name="_ping",
    fn=_ping_fn,
    validator=_ping_validator,
    max_calls=1,
    retry=1,
))