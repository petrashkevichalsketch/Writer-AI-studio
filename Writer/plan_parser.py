"""Custom Mode: разбор готового текстового плана через LLM.

Разделён на две фазы:
  parse_custom_plan() — долгий LLM-вызов, БД не трогает вообще;
  apply_custom_plan() — быстрая запись в БД.

Это защищает существующий проект: пока разбор не прошёл успешно,
старая база остаётся нетронутой.
"""

import json

import db
import llm
import prompt_loader
from pipeline.json_utils import parse_json
from translations import trf as _t


def parse_custom_plan(plan_text: str) -> dict:
    """Разбирает план через LLM, НЕ трогая БД.
    Возвращает {"ok": True, "data": ...} или {"ok": False, "error": ...}."""
    system = prompt_loader.get_prompt("plan_parser")

    try:
        raw = llm.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": plan_text}],
            stream=False, temperature=0.3, max_tokens=8000
        )
        data = parse_json(raw)
    except Exception as e:
        return {"ok": False, "error": _t("Ошибка LLM: {e}", e=e)}

    if not isinstance(data, dict):
        return {"ok": False, "error": _t("Модель вернула не JSON-объект.")}

    # Валидация ключевого слоя
    if "chapter_outline" not in data or not data["chapter_outline"].get("chapters"):
        return {"ok": False, "error": _t("Модель не смогла создать план глав.")}

    return {"ok": True, "data": data}


def apply_custom_plan(data: dict) -> None:
    """Сохранляет уже разобранный план в БД.
    Вызывать только после успешного parse_custom_plan и создания проекта."""
    for stage in ("world_core", "world_rules", "characters"):
        if stage in data:
            db.save_bible_stage(stage, data[stage], validated=True)
            db.set_stage(stage, "done")

    # Сохраняем план глав
    db.save_bible_stage("chapter_outline", data["chapter_outline"], validated=True)
    db.set_stage("chapter_outline", "done")

    # Заглушки для остальных стадий, чтобы pipeline.js их пропустил
    stubs = ["history", "institutions", "geography", "economy", "society",
             "culture", "conflicts", "secrets", "relations", "story_structure"]
    for s in stubs:
        if not db.get_bible_stage(s):
            # Сохраняем пустышку, чтобы автосбор не ломался
            db.save_bible_stage(s, {"status": "skipped_in_custom_mode"},
                                validated=True)
        db.set_stage(s, "done")
