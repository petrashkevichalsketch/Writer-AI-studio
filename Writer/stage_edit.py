"""Ручная правка результата стадии прямо на /pipeline (кнопка ✏).

Механика — по образцу карточек персонажей на /characters: правка пишется
в сырой слой world_bible (источник истины для промптов и variants), без
касания статусов pipeline_state и производных таблиц.

Отличие от карточек — правило видимости: кнопка появляется ТОЛЬКО на
последней выполненной стадии (последняя по порядку ALL_STAGES со
статусом done) и исчезает, как только следующая стадия становится done.
Смысл: править можно только «хвост» — тогда изменённые данные не
противоречат уже сгенерированному лору, который на них опирается.
Если последняя выполненная стадия — программная (lore_graph,
relevance_map, consistency_audit), кнопки нет нигде: всё, что перед
ней, уже отражено в её результате.

При сохранении правка проходит ПОЛНУЮ валидацию стадии (строго): при
ошибках запись не выполняется, список ошибок возвращается в UI.
Сохранённая правка дополнительно попадает в stage_variants как вариант
«manual» — её можно сравнить и откатить через окно вариантов.
"""

from typing import Any, Optional

import db
import validator
from config import ALL_STAGES
from translations import translate, trf as _t

# Редактируемые стадии: все LLM-стадии Фаз 1 и 2. Программные
# (lore_graph, relevance_map, consistency_audit) исключены — они
# считаются из других стадий, ручная правка сломала бы пересчёт.
EDITABLE_STAGES = frozenset({
    "world_core", "world_rules", "history", "institutions", "geography",
    "economy", "society", "culture", "conflicts", "secrets",
    "characters", "relations", "story_structure", "chapter_outline",
})


def editable_stage() -> Optional[str]:
    """Стадия, доступная для правки сейчас: последняя выполненная.

    Идём по порядку ALL_STAGES и берём последнюю со статусом done.
    Если следующая стадия сгенерирована — «последней» становится она,
    то есть кнопка автоматически уходит с предыдущей (и для неё
    возвращает 409 — даже при устаревшем UI). Программная стадия или
    отсутствие выполненных — правка недоступна."""
    status = {r["stage_name"]: r["status"] for r in db.get_pipeline()}
    last_done = None
    for s in ALL_STAGES:
        if status.get(s) == "done":
            last_done = s
    return last_done if last_done in EDITABLE_STAGES else None


# ── Диспетчер валидаторов ───────────────────────────────────────
# Подписи валидаторов разные: world_core сверяется с проектом,
# world_rules — с ядром мира, history — самодостаточна, остальные —
# с полной библией. chapter_outline перед проверкой нормализуется.

def _validate_stage(stage: str, data: Any) -> list[str]:
    if stage == "world_core":
        return validator.validate_world_core(data, db.get_project() or {})
    if stage == "world_rules":
        return validator.validate_world_rules(
            data, db.get_bible_stage("world_core") or {})
    if stage == "history":
        return validator.validate_history(data)
    if stage == "chapter_outline":
        validator.sanitize_chapter_outline(data)
        return validator.validate_chapter_outline(data, db.get_full_bible())
    fn = _BIBLE_VALIDATORS.get(stage)
    if fn is None:
        return [_t("Стадия {stage} не поддерживается.", stage=stage)]
    return fn(data, db.get_full_bible())


_BIBLE_VALIDATORS = {
    "institutions":    validator.validate_institutions,
    "geography":       validator.validate_geography,
    "economy":         validator.validate_economy,
    "society":         validator.validate_society,
    "culture":         validator.validate_culture,
    "conflicts":       validator.validate_conflicts,
    "secrets":         validator.validate_secrets,
    "characters":      validator.validate_characters,
    "relations":       validator.validate_relations,
    "story_structure": validator.validate_story_structure,
}


def get_stage_content(stage: str) -> Optional[Any]:
    """Текущий результат стадии из world_bible (для заполнения формы)."""
    if stage not in EDITABLE_STAGES:
        return None
    return db.get_bible_stage(stage)


def save_stage_edit(stage: str, data: Any) -> dict:
    """Сохранить правку: строгая валидация → запись в world_bible
    (+ вариант 'manual' для сравнения/отката).
    Возвращает {ok, errors, code}: code — 'unsupported' | 'locked' |
    'validation'; 'locked' значит «править можно только последнюю
    выполненную стадию» (UI и API различают эти случаи)."""
    if stage not in EDITABLE_STAGES:
        return {"ok": False, "code": "unsupported",
                "errors": [_t("Стадия {stage} не поддерживается.",
                              stage=stage)]}

    current = editable_stage()
    if current != stage:
        return {"ok": False, "code": "locked", "errors": [_t(
            "Стадия {stage} больше не является последней выполненной — "
            "редактирование заблокировано, чтобы не противоречить "
            "сгенерированному лору.", stage=stage)]}

    if not isinstance(data, dict):
        return {"ok": False, "code": "validation",
                "errors": [translate("Ожидался JSON-объект.")]}

    errors = [translate(x) if isinstance(x, str) else x
              for x in _validate_stage(stage, data)]
    if errors:
        return {"ok": False, "code": "validation", "errors": errors}

    db.save_bible_stage(stage, data, validated=True)
    # Правка — самостоятельный вариант «manual»: видна в окне вариантов,
    # можно сравнить с local/strong и откатить.
    try:
        db.save_stage_variant(stage, "manual", data, errors=[],
                              is_active=True)
    except Exception:
        pass  # варианты — вспомогательная функциональность
    return {"ok": True, "errors": []}
