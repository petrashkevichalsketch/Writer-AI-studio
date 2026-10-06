"""Стадии Фазы 2: characters, relations, story_structure, chapter_outline."""

import json
from pathlib import Path

import llm
import validator

from .json_utils import parse_json
from .registry import StageSpec, register

PROMPTS = Path(__file__).parent.parent / "prompts"


def _system_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


def _call(system: str, user_payload: dict, max_tokens: int,
          prev_errors: list[str] | None = None) -> dict:
    if prev_errors:
        user_payload = dict(user_payload)
        user_payload["previous_attempt_errors"] = prev_errors
        user_payload["instruction"] = (
            "Предыдущая попытка не прошла валидацию. Исправь именно эти проблемы, "
            "не меняя остальное."
        )
    text = llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user",
             "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ],
        stream=False,
        temperature=0.85,
        max_tokens=max_tokens,
    )
    return parse_json(text)


def _project_block(project: dict) -> dict:
    return {
        "theme":    project["theme"],
        "genre":    project["genre"],
        "setting":  project["setting"],
        "conflict": project["conflict"],
        "tone":     project.get("tone") or "",
        "protagonist_rule": (
            "Главный герой — всегда мужчина-одиночка. Он может вступать "
            "в романтические и сексуальные отношения с женщинами, но НЕ "
            "принадлежит и не присоединяется ни к каким кланам, фракциям, "
            "повстанцам, корпорациям, культам, союзам и организациям. "
            "Все фракции и институции в мире существуют как контекст и "
            "угрозы, но не как его «свои». Даже если герой временно "
            "сотрудничает с кем-то — это не членство, а вынужденный "
            "тактический союз, который он стремится разорвать."
        ),
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
    project = ctx["project"]
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

def chapter_outline_fn(ctx: dict) -> dict:
    import config
    b = ctx["bible"]
    project = ctx["project"]
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
    return _call(_system_prompt("chapter_outline"), payload,
                 max_tokens=13000, prev_errors=ctx.get("prev_errors"))


def chapter_outline_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_chapter_outline(payload, ctx["bible"])


register(StageSpec(
    name="chapter_outline",
    fn=chapter_outline_fn,
    validator=chapter_outline_validator,
    max_calls=3, retry=3,
    requires=["story_structure"],
))
