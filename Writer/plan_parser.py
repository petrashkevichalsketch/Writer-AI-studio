"""Custom Mode: parsing a ready-made text plan via LLM.

Divided into two phases:
  parse_custom_plan() — a long LLM call, does not touch the DB at all;
  apply_custom_plan() — fast writing to the DB.

This protects the existing project: until parsing succeeds, 
the old database remains untouched.
"""

import json

import db
import llm
import prompt_loader
from pipeline.json_utils import parse_json
from translations import trf as _t


def parse_custom_plan(plan_text: str) -> dict:
    """Parses the plan via LLM WITHOUT touching the DB.
    Returns {"ok": True, "data": ...} or {"ok": False, "error": ...}."""
    system = prompt_loader.get_prompt("plan_parser")

    try:
        raw = llm.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": plan_text}],
            stream=False, temperature=0.3, max_tokens=8000
        )
        data = parse_json(raw)
    except Exception as e:
        return {"ok": False, "error": _t("LLM error: {e}", e=e)}

    if not isinstance(data, dict):
        return {"ok": False, "error": _t("The model returned a non-JSON object.")}

    # Validate the core layer
    if "chapter_outline" not in data or not data["chapter_outline"].get("chapters"):
        return {"ok": False, "error": _t("The model failed to create a chapter outline.")}

    return {"ok": True, "data": data}


def apply_custom_plan(data: dict) -> None:
    """Saves the already parsed plan to the DB.
    Call only after a successful parse_custom_plan and project creation."""
    
    # 1. Basic world layers and characters
    for stage in ("world_core", "world_rules", "characters"):
        if stage in data and data[stage]:
            db.save_bible_stage(stage, data[stage], validated=True)
            db.set_stage(stage, "done")

    # 2. Geography and institutions (if extracted by the model)
    if "geography" in data and data["geography"].get("locations"):
        db.save_bible_stage("geography", data["geography"], validated=True)
        db.set_stage("geography", "done")

    if "institutions" in data and data["institutions"].get("institutions"):
        db.save_bible_stage("institutions", data["institutions"], validated=True)
        db.set_stage("institutions", "done")

    # 3. Relations and story structure (if extracted by the model)
    if "relations" in data and data["relations"].get("relations"):
        db.save_bible_stage("relations", data["relations"], validated=True)
        db.set_stage("relations", "done")

    if "story_structure" in data and data["story_structure"].get("story_beats"):
        db.save_bible_stage("story_structure", data["story_structure"], validated=True)
        db.set_stage("story_structure", "done")

    # 4. Save the chapter outline
    db.save_bible_stage("chapter_outline", data["chapter_outline"], validated=True)
    db.set_stage("chapter_outline", "done")

    # 5. Stubs ONLY for background layers that don't affect the main plot
    stubs = ["history", "economy", "society", "culture", "conflicts", "secrets"]
    for s in stubs:
        if not db.get_bible_stage(s):
            # Save a dummy object to prevent the autobuild from breaking
            db.save_bible_stage(s, {"status": "skipped_in_custom_mode"}, validated=True)
        db.set_stage(s, "done")