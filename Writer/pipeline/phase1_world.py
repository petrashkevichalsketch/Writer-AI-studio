"""Стадии Фазы 1: world_core → world_rules → history →
institutions → geography → economy → society → culture →
conflicts → secrets."""

import json

import db
import llm
import prompt_loader
import validator

from config import ERA_KB_MAX_CHARS
from .json_utils import parse_json
from .registry import StageSpec, register


# Правило справочника мира/эпохи: добавляется к системным промптам
# мировых стадий, только если пользователь заполнил справку (era_kb).
_ERA_KB_RULES = {
    "ru": (
        "\n\n━━━ СПРАВОЧНИК МИРА/ЭПОХИ (era_kb) ━━━\n"
        "Во входных данных есть input.project.era_kb — справочник "
        "мира/эпохи, составленный пользователем из источников. Факты "
        "из него приоритетнее твоих догадок и общих знаний; не "
        "противоречь ему. Реальные лица и структуры из справки (князья "
        "и их дружины, воеводы, торговые дома, учреждения) входят в "
        "мировые слои: институции, хронику, экономику — как есть, "
        "по справке. Сюжет и вымышленных персонажей здесь не "
        "создавай — их построят отдельные стадии, справка дойдёт до "
        "них сама. Если справочник расходится с общеизвестной "
        "хроникой, для деталей места следуй справочнику и не "
        "выдумывай третьего варианта."
    ),
    "en": (
        "\n\n━━━ WORLD/ERA KNOWLEDGE BASE (era_kb) ━━━\n"
        "The input contains input.project.era_kb — a world/era "
        "reference compiled by the user from sources. Facts from it "
        "take priority over your guesses and general knowledge; do "
        "not contradict it. Real people and structures from the "
        "reference (princes and their retinues, voivodes, trading "
        "houses, institutions) enter the world layers — institutions, "
        "the chronicle, the economy — as they are, per the reference. "
        "Do not create plot or fictional characters here — separate "
        "stages will build them, and the reference will reach them "
        "on its own. If the reference conflicts with well-known "
        "chronology, follow the reference for local details and do "
        "not invent a third variant."
    ),
}


def _system_prompt(name: str) -> str:
    # Мировые промпты не содержат правила «ёлочек»/запятых (в отличие
    # от story-стадий) — добавляем программно, чтобы модель не роняла
    # ответ одной кавычкой внутри значения.
    prompt = prompt_loader.get_prompt(name) + prompt_loader.json_syntax_rules()
    if db.get_era_kb():
        lang = prompt_loader.current_language()
        prompt += _ERA_KB_RULES.get(lang, _ERA_KB_RULES["ru"])
    return prompt


def _call(system: str, user_payload: dict, max_tokens: int,
          prev_errors: list[str] | None = None,
          user_answers: list[dict] | None = None,
          temperature: float = 0.7) -> dict:
    if prev_errors:
        user_payload = dict(user_payload)
        user_payload["previous_attempt_errors"] = prev_errors
        user_payload["instruction"] = (
            "The previous attempt failed validation. Fix exactly these "
            "problems without changing anything else."
            if prompt_loader.current_language() == "en" else
            "Предыдущая попытка не прошла валидацию. Исправь именно эти проблемы, "
            "не меняя остальное."
        )
    if user_answers:
        user_payload = dict(user_payload)
        user_payload["user_answers"] = user_answers
    text = llm.chat(
        [
            {"role": "system", "content": system},
            {"role": "user",
             "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ],
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return parse_json(text)


def _project_block(project: dict) -> dict:
    # era_kb — справка пользователя о мире/эпохе: инъектируется в
    # payload всех мировых стадий целиком (без поиска и эмбеддингов).
    # Сюжетные стадии Фазы 2 и главы её НЕ получают — там работает
    # уже построенная библия.
    era_kb = (db.get_era_kb() or "")[:ERA_KB_MAX_CHARS]
    return {
        "theme":         project["theme"],
        "genre":         project["genre"],
        "setting":       project["setting"],
        "start_setting": project.get("start_setting") or "",
        "conflict":      project["conflict"],
        "tone":          project.get("tone") or "",
        "era_kb":        era_kb,
        # Режим RPG и язык книги: жанровые мировые промпты строят
        # двухслойный мир (реальность + игра/Система) и сами выбирают
        # язык значений. Обычные промпты эти поля игнорируют.
        "rpg_mode":      project.get("rpg_mode") or "none",
        "language":      project.get("language") or "ru",
    }


def _b(bible: dict, *keys: str) -> dict:
    """Собрать срез bible по указанным ключам."""
    return {k: bible.get(k) for k in keys if bible.get(k) is not None}


# ────────────────────────────────────────────────────────────────
# WORLD_CORE
# ────────────────────────────────────────────────────────────────

def world_core_fn(ctx: dict) -> dict:
    payload = {
        "task":  "world_core",
        "input": {"project": _project_block(ctx["project"])},
    }
    return _call(_system_prompt("world_core"), payload,
                 max_tokens=3000,
                 prev_errors=ctx.get("prev_errors"),
                 user_answers=ctx.get("user_answers"))


def world_core_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_world_core(payload, ctx["project"])


register(StageSpec(
    name="world_core",
    fn=world_core_fn,
    validator=world_core_validator,
    max_calls=3, retry=3,
))


# ────────────────────────────────────────────────────────────────
# WORLD_RULES
# ────────────────────────────────────────────────────────────────

def world_rules_fn(ctx: dict) -> dict:
    payload = {
        "task": "world_rules",
        "input": {
            "project":    _project_block(ctx["project"]),
            "world_core": ctx["bible"].get("world_core") or {},
        },
    }
    return _call(_system_prompt("world_rules"), payload,
                 max_tokens=4500, prev_errors=ctx.get("prev_errors"))


def world_rules_validator(ctx: dict, payload: dict) -> list[str]:
    core = ctx["bible"].get("world_core") or {}
    return validator.validate_world_rules(payload, core)


register(StageSpec(
    name="world_rules",
    fn=world_rules_fn,
    validator=world_rules_validator,
    max_calls=3, retry=3,
    requires=["world_core"],
))


# ────────────────────────────────────────────────────────────────
# HISTORY
# ────────────────────────────────────────────────────────────────

def history_fn(ctx: dict) -> dict:
    payload = {
        "task": "history",
        "input": {
            "project":     _project_block(ctx["project"]),
            "world_core":  ctx["bible"].get("world_core") or {},
            "world_rules": ctx["bible"].get("world_rules") or {},
        },
    }
    return _call(_system_prompt("history"), payload,
                 max_tokens=10000, prev_errors=ctx.get("prev_errors"))


def history_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_history(payload)


register(StageSpec(
    name="history",
    fn=history_fn,
    validator=history_validator,
    max_calls=3, retry=3,
    requires=["world_core", "world_rules"],
))


# ────────────────────────────────────────────────────────────────
# INSTITUTIONS
# ────────────────────────────────────────────────────────────────

def institutions_fn(ctx: dict) -> dict:
    payload = {
        "task": "institutions",
        "input": {
            "project":     _project_block(ctx["project"]),
            "world_core":  ctx["bible"].get("world_core") or {},
            "world_rules": ctx["bible"].get("world_rules") or {},
            "history":     ctx["bible"].get("history") or {},
        },
    }
    return _call(_system_prompt("institutions"), payload,
                 max_tokens=6000, prev_errors=ctx.get("prev_errors"))


def institutions_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_institutions(payload, ctx["bible"])


register(StageSpec(
    name="institutions",
    fn=institutions_fn,
    validator=institutions_validator,
    max_calls=3, retry=3,
    requires=["world_core", "world_rules", "history"],
))


# ────────────────────────────────────────────────────────────────
# GEOGRAPHY
# ────────────────────────────────────────────────────────────────

def geography_fn(ctx: dict) -> dict:
    payload = {
        "task": "geography",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   ctx["bible"].get("world_core") or {},
            "world_rules":  ctx["bible"].get("world_rules") or {},
            "history":      ctx["bible"].get("history") or {},
            "institutions": ctx["bible"].get("institutions") or {},
        },
    }
    return _call(_system_prompt("geography"), payload,
                 max_tokens=5000, prev_errors=ctx.get("prev_errors"))


def geography_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_geography(payload, ctx["bible"])


register(StageSpec(
    name="geography",
    fn=geography_fn,
    validator=geography_validator,
    max_calls=3, retry=3,
    requires=["institutions"],
))


# ────────────────────────────────────────────────────────────────
# ECONOMY
# ────────────────────────────────────────────────────────────────

def economy_fn(ctx: dict) -> dict:
    payload = {
        "task": "economy",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   ctx["bible"].get("world_core") or {},
            "world_rules":  ctx["bible"].get("world_rules") or {},
            "history":      ctx["bible"].get("history") or {},
            "institutions": ctx["bible"].get("institutions") or {},
        },
    }
    return _call(_system_prompt("economy"), payload,
                 max_tokens=4000, prev_errors=ctx.get("prev_errors"))


def economy_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_economy(payload, ctx["bible"])


register(StageSpec(
    name="economy",
    fn=economy_fn,
    validator=economy_validator,
    max_calls=2, retry=3,
    requires=["institutions"],
))


# ────────────────────────────────────────────────────────────────
# SOCIETY
# ────────────────────────────────────────────────────────────────

def society_fn(ctx: dict) -> dict:
    payload = {
        "task": "society",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   ctx["bible"].get("world_core") or {},
            "world_rules":  ctx["bible"].get("world_rules") or {},
            "institutions": ctx["bible"].get("institutions") or {},
            "economy":      ctx["bible"].get("economy") or {},
        },
    }
    return _call(_system_prompt("society"), payload,
                 max_tokens=4500, prev_errors=ctx.get("prev_errors"))


def society_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_society(payload, ctx["bible"])


register(StageSpec(
    name="society",
    fn=society_fn,
    validator=society_validator,
    max_calls=3, retry=3,
    requires=["institutions", "economy"],
))


# ────────────────────────────────────────────────────────────────
# CULTURE
# ────────────────────────────────────────────────────────────────

def culture_fn(ctx: dict) -> dict:
    payload = {
        "task": "culture",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   ctx["bible"].get("world_core") or {},
            "history":      ctx["bible"].get("history") or {},
            "institutions": ctx["bible"].get("institutions") or {},
            "economy":      ctx["bible"].get("economy") or {},
            "society":      ctx["bible"].get("society") or {},
        },
    }
    return _call(_system_prompt("culture"), payload,
                 max_tokens=4500, prev_errors=ctx.get("prev_errors"))


def culture_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_culture(payload, ctx["bible"])


register(StageSpec(
    name="culture",
    fn=culture_fn,
    validator=culture_validator,
    max_calls=3, retry=3,
    requires=["society"],
))


# ────────────────────────────────────────────────────────────────
# CONFLICTS
# ────────────────────────────────────────────────────────────────

def conflicts_fn(ctx: dict) -> dict:
    payload = {
        "task": "conflicts",
        "input": {
            "project":      _project_block(ctx["project"]),
            "world_core":   ctx["bible"].get("world_core") or {},
            "history":      ctx["bible"].get("history") or {},
            "institutions": ctx["bible"].get("institutions") or {},
            "geography":    ctx["bible"].get("geography") or {},
            "economy":      ctx["bible"].get("economy") or {},
            "society":      ctx["bible"].get("society") or {},
            "culture":      ctx["bible"].get("culture") or {},
        },
    }
    return _call(_system_prompt("conflicts"), payload,
                 max_tokens=4500, prev_errors=ctx.get("prev_errors"))


def conflicts_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_conflicts(payload, ctx["bible"])


register(StageSpec(
    name="conflicts",
    fn=conflicts_fn,
    validator=conflicts_validator,
    max_calls=3, retry=3,
    requires=["institutions", "economy", "society", "culture"],
))


# ────────────────────────────────────────────────────────────────
# SECRETS
# ────────────────────────────────────────────────────────────────

def secrets_fn(ctx: dict) -> dict:
    project = ctx["project"]
    # Реальная граница глав (формат книги): «1..20» из промпта модель
    # принимает на веру, поэтому даём лимит явно и, на всякий случай,
    # зажимаем earliest_chapter после разбора ответа.
    from config import BOOK_FORMATS, DEFAULT_BOOK_FORMAT
    fmt = (BOOK_FORMATS.get(project.get("book_format") or "")
           or BOOK_FORMATS[DEFAULT_BOOK_FORMAT])
    chapter_limit = int(fmt["chapters_max"])

    payload = {
        "task": "secrets",
        "input": {
            "project":       _project_block(project),
            "chapter_limit": chapter_limit,
            "world_core":    ctx["bible"].get("world_core") or {},
            "world_rules":   ctx["bible"].get("world_rules") or {},
            "history":       ctx["bible"].get("history") or {},
            "institutions":  ctx["bible"].get("institutions") or {},
            "conflicts":     ctx["bible"].get("conflicts") or {},
        },
    }
    data = _call(_system_prompt("secrets"), payload,
                 max_tokens=4500, prev_errors=ctx.get("prev_errors"))
    validator.sanitize_secrets(data, chapter_limit)
    return data


def secrets_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_secrets(payload, ctx["bible"])


register(StageSpec(
    name="secrets",
    fn=secrets_fn,
    validator=secrets_validator,
    max_calls=3, retry=3,
    requires=["institutions", "conflicts"],
))

# ────────────────────────────────────────────────────────────────
# LORE_GRAPH (программно)
# ────────────────────────────────────────────────────────────────

def lore_graph_fn(ctx: dict) -> dict:
    import lore_graph as lg
    return lg.build(ctx["bible"])


def lore_graph_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_lore_graph(payload, ctx["bible"])


register(StageSpec(
    name="lore_graph",
    fn=lore_graph_fn,
    validator=lore_graph_validator,
    max_calls=1, retry=1,
    requires=["world_core", "history", "institutions",
              "geography", "conflicts", "secrets"],
))


# ────────────────────────────────────────────────────────────────
# RELEVANCE_MAP (программно)
# ────────────────────────────────────────────────────────────────

def relevance_map_fn(ctx: dict) -> dict:
    import relevance as rl
    graph = ctx["bible"].get("lore_graph") or {}
    return rl.compute(ctx["bible"], graph)


def relevance_map_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_relevance_map(payload, ctx["bible"])


register(StageSpec(
    name="relevance_map",
    fn=relevance_map_fn,
    validator=relevance_map_validator,
    max_calls=1, retry=1,
    requires=["lore_graph"],
))


# ────────────────────────────────────────────────────────────────
# CONSISTENCY_AUDIT (AI-судья)
# ────────────────────────────────────────────────────────────────

def consistency_audit_fn(ctx: dict) -> dict:
    bible = ctx["bible"]
    # Отдаём судье всё, кроме программных слоёв — те не текст мира.
    world_view = {
        k: v for k, v in bible.items()
        if v is not None and k not in ("lore_graph", "relevance_map")
    }
    payload = {
        "task": "consistency_audit",
        "input": {
            "project":     _project_block(ctx["project"]),
            "world_bible": world_view,
        },
    }
    result = _call(_system_prompt("consistency_audit"), payload,
                   max_tokens=3500, prev_errors=ctx.get("prev_errors"),
                   temperature=0.35)  # аудит должен быть консервативным

    # Пересчитываем вердикт программно — не доверяем модели в арифметике.
    n = len(result.get("problems") or [])
    result["overall_verdict"] = "pass" if n <= 2 else ("warn" if n <= 5 else "fail")
    result["problem_count"] = n
    return result


def consistency_audit_validator(ctx: dict, payload: dict) -> list[str]:
    return validator.validate_consistency_audit(payload, ctx["bible"])


register(StageSpec(
    name="consistency_audit",
    fn=consistency_audit_fn,
    validator=consistency_audit_validator,
    max_calls=2, retry=3,
    requires=["secrets"],
))
