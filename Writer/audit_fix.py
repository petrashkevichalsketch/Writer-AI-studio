"""Исправление одной проблемы аудита через правку одного слоя мира.

Принцип: минимальное вмешательство. Модель получает одну проблему и
один слой, возвращает новую версию слоя. Downstream-стадии сбрасываются,
потому что построены на устаревшем фундаменте.
"""

import json
from pathlib import Path

import db
import llm
import validator
import pipeline.phase1_world as p1
from pipeline.json_utils import parse_json
from config import ALL_STAGES

PROMPTS = Path(__file__).parent / "prompts"

NON_FIXABLE_LAYERS = {
    "lore_graph", "relevance_map", "consistency_audit",
}

LAYER_VALIDATORS = {
    "world_core":      lambda p, b, pr: validator.validate_world_core(p, pr),
    "world_rules":     lambda p, b, pr: validator.validate_world_rules(p, b.get("world_core") or {}),
    "history":         lambda p, b, pr: validator.validate_history(p),
    "institutions":    lambda p, b, pr: validator.validate_institutions(p, b),
    "geography":       lambda p, b, pr: validator.validate_geography(p, b),
    "economy":         lambda p, b, pr: validator.validate_economy(p, b),
    "society":         lambda p, b, pr: validator.validate_society(p, b),
    "culture":         lambda p, b, pr: validator.validate_culture(p, b),
    "conflicts":       lambda p, b, pr: validator.validate_conflicts(p, b),
    "secrets":         lambda p, b, pr: validator.validate_secrets(p, b),
    "characters":      lambda p, b, pr: validator.validate_characters(p, b),
    "relations":       lambda p, b, pr: validator.validate_relations(p, b),
    "story_structure": lambda p, b, pr: validator.validate_story_structure(p, b),
    "chapter_outline": lambda p, b, pr: validator.validate_chapter_outline(p, b),
}


def _system_prompt() -> str:
    return (PROMPTS / "audit_fix.txt").read_text(encoding="utf-8")


def _downstream_stages(layer: str) -> list[str]:
    if layer not in ALL_STAGES:
        return []
    idx = ALL_STAGES.index(layer)
    return ALL_STAGES[idx + 1:]


def fix_problem(problem_index: int) -> dict:
    bible = db.get_full_bible()
    audit = bible.get("consistency_audit") or {}
    problems = audit.get("problems") or []

    if not (0 <= problem_index < len(problems)):
        return {"ok": False, "errors": ["Проблема с таким индексом не найдена."]}

    problem = problems[problem_index]
    layer = problem.get("layer")

    if layer in NON_FIXABLE_LAYERS:
        return {"ok": False,
                "errors": [f"Слой '{layer}' нельзя править через LLM."]}

    if layer not in LAYER_VALIDATORS:
        return {"ok": False,
                "errors": [f"Для слоя '{layer}' нет валидатора."]}

    current_layer = bible.get(layer)
    if not current_layer:
        return {"ok": False,
                "errors": [f"Слой '{layer}' пуст — нечего править."]}

    other_layers = {
        k: v for k, v in bible.items()
        if k not in (layer, "lore_graph", "relevance_map") and v is not None
    }

    user_payload = {
        "task": "audit_fix",
        "input": {
            "layer_name": layer,
            "problem": {
                "severity":    problem.get("severity"),
                "description": problem.get("description"),
                "suggestion":  problem.get("suggestion"),
            },
            "current_layer": current_layer,
            "other_layers":  other_layers,
        },
    }

    try:
        raw = llm.chat(
            [
                {"role": "system", "content": _system_prompt()},
                {"role": "user",
                 "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
            ],
            stream=False,
            temperature=0.4,
            max_tokens=8000,
        )
        new_layer = parse_json(raw)
    except Exception as e:
        return {"ok": False, "errors": [f"Ошибка LLM: {e}"]}

    if isinstance(new_layer, dict) and new_layer.get("_fix_error"):
        return {"ok": False,
                "errors": [f"Модель не смогла исправить: {new_layer['_fix_error']}"]}

    validator_fn = LAYER_VALIDATORS[layer]
    try:
        errors = validator_fn(new_layer, bible, db.get_project())
    except Exception as e:
        return {"ok": False, "errors": [f"Ошибка валидатора: {e}"]}

    real_errors = [x for x in errors if not x.startswith("WARN:")]
    if real_errors:
        return {"ok": False, "errors": real_errors}

    # Снапшот ПЕРЕД применением
    snapshot_id = db.save_world_snapshot(
        reason=f"Перед фиксом {layer} (проблема #{problem_index})"
    )

    # Применяем новый слой
    db.save_bible_stage(layer, new_layer, validated=True)

    # Каскадный сброс downstream
    downstream = _downstream_stages(layer)
    if downstream:
        db.reset_stages(downstream)

    # Снимаем approve
    db.set_setting("world_approved", "0")

    # Ре-аудит
    new_bible = db.get_full_bible()
    audit_ctx = {
        "stage":        "consistency_audit",
        "attempt":      1,
        "project":      db.get_project(),
        "bible":        new_bible,
        "prev_errors":  [],
        "user_answers": [],
    }
    try:
        new_audit = p1.consistency_audit_fn(audit_ctx)
        db.save_bible_stage("consistency_audit", new_audit, validated=True)
        db.set_stage("consistency_audit", "done")
    except Exception as e:
        return {
            "ok":             True,
            "updated_layer":  layer,
            "reset_stages":   downstream,
            "snapshot_id":    snapshot_id,
            "warning":        f"Фикс применён, но ре-аудит упал: {e}",
        }

    return {
        "ok":                 True,
        "updated_layer":      layer,
        "reset_stages":       downstream,
        "snapshot_id":        snapshot_id,
        "old_verdict":        audit.get("overall_verdict"),
        "old_problem_count":  len(problems),
        "new_verdict":        new_audit.get("overall_verdict"),
        "new_problem_count":  len(new_audit.get("problems") or []),
    }

# ────────────────────────────────────────────────────────────────
# Ручная правка и предложение модели (без применения)
# ────────────────────────────────────────────────────────────────

def _validate_layer(layer: str, content, bible: dict) -> list[str]:
    """Возвращает список реальных ошибок (без WARN)."""
    fn = LAYER_VALIDATORS.get(layer)
    if not fn:
        return [f"Нет валидатора для слоя '{layer}'."]
    try:
        raw = fn(content, bible, db.get_project())
    except Exception as e:
        return [f"Ошибка валидатора: {e}"]
    return [x for x in (raw or []) if not x.startswith("WARN:")]


def _warnings_layer(layer: str, content, bible: dict) -> list[str]:
    fn = LAYER_VALIDATORS.get(layer)
    if not fn:
        return []
    try:
        raw = fn(content, bible, db.get_project())
    except Exception:
        return []
    return [x[len("WARN:"):].strip() for x in (raw or [])
            if isinstance(x, str) and x.startswith("WARN:")]


def suggest_fix(problem_index: int) -> dict:
    """Возвращает предложение модели для слоя. НЕ записывает в БД."""
    bible = db.get_full_bible()
    audit = bible.get("consistency_audit") or {}
    problems = audit.get("problems") or []

    if not (0 <= problem_index < len(problems)):
        return {"ok": False, "errors": ["Проблема не найдена."]}

    problem = problems[problem_index]
    layer = problem.get("layer")

    if layer in NON_FIXABLE_LAYERS:
        return {"ok": False, "errors": [f"Слой '{layer}' нельзя править через LLM."]}
    if layer not in LAYER_VALIDATORS:
        return {"ok": False, "errors": [f"Для слоя '{layer}' нет валидатора."]}

    current_layer = bible.get(layer)
    if not current_layer:
        return {"ok": False, "errors": [f"Слой '{layer}' пуст."]}

    other_layers = {
        k: v for k, v in bible.items()
        if k not in (layer, "lore_graph", "relevance_map") and v is not None
    }

    user_payload = {
        "task": "audit_fix",
        "input": {
            "layer_name": layer,
            "problem": {
                "severity":    problem.get("severity"),
                "description": problem.get("description"),
                "suggestion":  problem.get("suggestion"),
            },
            "current_layer": current_layer,
            "other_layers":  other_layers,
        },
    }

    try:
        raw = llm.chat(
            [
                {"role": "system", "content": _system_prompt()},
                {"role": "user",
                 "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
            ],
            stream=False,
            temperature=0.4,
            max_tokens=8000,
        )
        new_layer = parse_json(raw)
    except Exception as e:
        return {"ok": False, "errors": [f"Ошибка LLM: {e}"]}

    if isinstance(new_layer, dict) and new_layer.get("_fix_error"):
        return {"ok": False,
                "errors": [f"Модель не смогла: {new_layer['_fix_error']}"]}

    # Валидируем, но НЕ записываем
    errors = _validate_layer(layer, new_layer, bible)
    if errors:
        return {"ok": False,
                "errors": ["Предложение модели не проходит валидацию:"] + errors}

    return {"ok": True, "content": new_layer}


def save_manual_edit(layer: str, content, reset_downstream: bool = False) -> dict:
    """Сохраняет слой, отредактированный вручную.

    reset_downstream=False (по умолчанию) — downstream не трогаем.
    reset_downstream=True — сбрасываем все стадии после слоя в ALL_STAGES.
    """
    if layer in NON_FIXABLE_LAYERS:
        return {"ok": False, "errors": [f"Слой '{layer}' нельзя править вручную."]}
    if layer not in LAYER_VALIDATORS:
        return {"ok": False, "errors": [f"Для слоя '{layer}' нет валидатора."]}

    bible = db.get_full_bible()
    errors = _validate_layer(layer, content, bible)
    if errors:
        return {"ok": False, "errors": errors}

    warnings = _warnings_layer(layer, content, bible)

    snapshot_id = db.save_world_snapshot(
        reason=f"Ручная правка {layer} (downstream={'reset' if reset_downstream else 'keep'})"
    )

    db.save_bible_stage(layer, content, validated=True)
    db.set_setting("world_approved", "0")

    reset_stages: list[str] = []
    if reset_downstream:
        reset_stages = _downstream_stages(layer)
        if reset_stages:
            db.reset_stages(reset_stages)

    # Пересчёт аудита, если он уже был построен и мы не сбросили его
    audit_before = (db.get_full_bible().get("consistency_audit") or {})
    audit_updated = False
    if audit_before and "consistency_audit" not in reset_stages:
        new_bible = db.get_full_bible()
        audit_ctx = {
            "stage":        "consistency_audit",
            "attempt":      1,
            "project":      db.get_project(),
            "bible":        new_bible,
            "prev_errors":  [],
            "user_answers": [],
        }
        try:
            new_audit = p1.consistency_audit_fn(audit_ctx)
            db.save_bible_stage("consistency_audit", new_audit, validated=True)
            db.set_stage("consistency_audit", "done")
            audit_updated = True
        except Exception:
            pass  # не роняем правку из-за аудита

    return {
        "ok":             True,
        "updated_layer":  layer,
        "snapshot_id":    snapshot_id,
        "reset_stages":   reset_stages,
        "warnings":       warnings,
        "audit_updated":  audit_updated,
    }