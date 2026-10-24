import json
import db
import llm
import validator
from pipeline.json_utils import parse_json
from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"

def import_custom_plan(plan_text: str) -> dict:
    system = (PROMPTS / "plan_parser.txt").read_text(encoding="utf-8")
    
    try:
        raw = llm.chat(
            [{"role": "system", "content": system}, 
             {"role": "user", "content": plan_text}],
            stream=False, temperature=0.3, max_tokens=8000
        )
        data = parse_json(raw)
    except Exception as e:
        return {"ok": False, "error": f"Ошибка LLM: {e}"}

    # Валидация ключевых слоев
    if "chapter_outline" not in data or not data["chapter_outline"].get("chapters"):
        return {"ok": False, "error": "Модель не смогла создать план глав."}

    bible = db.get_full_bible()
    
    # Сохраняем базовые слои
    if "world_core" in data: 
        db.save_bible_stage("world_core", data["world_core"], validated=True)
        db.set_stage("world_core", "done")
        
    if "world_rules" in data: 
        db.save_bible_stage("world_rules", data["world_rules"], validated=True)
        db.set_stage("world_rules", "done")
        
    if "characters" in data:
        db.save_bible_stage("characters", data["characters"], validated=True)
        db.set_stage("characters", "done")

    # Сохраняем план глав
    db.save_bible_stage("chapter_outline", data["chapter_outline"], validated=True)
    db.set_stage("chapter_outline", "done")

    # Заглушки для остальных стадий, чтобы pipeline.js их пропустил
    stubs = ["history", "institutions", "geography", "economy", "society", "culture", "conflicts", "secrets", "relations", "story_structure"]
    for s in stubs:
        if not db.get_bible_stage(s):
            # Сохраняем пустышку, чтобы автосбор не ломался
            db.save_bible_stage(s, {"status": "skipped_in_custom_mode"}, validated=True)
        db.set_stage(s, "done")

    return {"ok": True}