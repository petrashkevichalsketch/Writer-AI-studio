"""Уточняющие вопросы к стадиям пайплайна.
Копия механики ask_questions из chapter_engine, но для стадий."""

import asyncio
import json
from pathlib import Path

import db
import llm
from .json_utils import parse_json
from .registry import get as reg_get
from config import STAGES_PHASE1, STAGES_PHASE2

PROMPTS = Path(__file__).parent.parent / "prompts"

EXCLUDED = {"lore_graph", "relevance_map"}


def _capture(storage: dict):
    """Заглушка вместо _call: сохраняет system+payload, не вызывает LLM."""
    def fake(system, user_payload, max_tokens, prev_errors=None, user_answers=None):
        storage["system"] = system
        storage["payload"] = user_payload
        return {}
    return fake


def _pick_module(stage: str):
    if stage in STAGES_PHASE1:
        import pipeline.phase1_world as mod
        return mod
    if stage in STAGES_PHASE2:
        import pipeline.phase2_story as mod
        return mod
    return None


def _pick_system_prompt(stage: str) -> str:
    override = PROMPTS / f"pipeline_questions_{stage}.txt"
    if override.exists():
        return override.read_text(encoding="utf-8")
    return (PROMPTS / "pipeline_questions.txt").read_text(encoding="utf-8")


async def ask_questions(stage: str) -> dict:
    """Возвращает {ok, questions} или {ok: False, error}."""
    if stage in EXCLUDED:
        return {"ok": False, "error": f"Стадия {stage} не задаёт вопросов."}
    if stage not in STAGES_PHASE1 and stage not in STAGES_PHASE2:
        return {"ok": False, "error": f"Неизвестная стадия: {stage}."}

    mod = _pick_module(stage)
    spec = reg_get(stage)
    if mod is None or spec is None:
        return {"ok": False, "error": f"Модуль стадии {stage} не найден."}

    project = db.get_project()
    if not project:
        return {"ok": False, "error": "Проект не создан."}

    storage: dict = {}
    original = mod._call
    mod._call = _capture(storage)
    try:
        bible = db.get_full_bible()
        ctx = {
            "stage":        stage,
            "attempt":      1,
            "project":      project,
            "bible":        bible,
            "prev_errors":  [],
            "user_answers": [],
        }
        spec.fn(ctx)
    except Exception as e:
        return {"ok": False, "error": f"Сборка контекста: {e}"}
    finally:
        mod._call = original

    if "payload" not in storage:
        return {"ok": False, "error": f"Стадия {stage} не использует LLM."}

    system = _pick_system_prompt(stage)
    user = {
        "task":    "pipeline_questions",
        "stage":   stage,
        "project": project,
        "bible":   storage["payload"].get("input") or {},
    }

    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(
            None,
            lambda: llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False, indent=2)},
                ],
                stream=False, temperature=0.7, max_tokens=2500,
            ),
        )
    except Exception as e:
        return {"ok": False, "error": f"Ошибка запроса к модели: {e}"}

    try:
        data = parse_json(raw)
    except Exception as e:
        return {"ok": False, "error": f"Не удалось распарсить JSON: {e}",
                "raw": raw[:500]}

    questions = data.get("questions") or []
    if not isinstance(questions, list) or not (3 <= len(questions) <= 5):
        return {"ok": False,
                "error": f"Ожидалось 3–5 вопросов, получено {len(questions)}.",
                "raw": data}

    for q in questions:
        if not isinstance(q, dict):
            return {"ok": False, "error": "Элемент questions не объект."}
        if not q.get("text"):
            return {"ok": False, "error": "У вопроса нет text."}
        opts = q.get("options") or []
        if not isinstance(opts, list) or not (2 <= len(opts) <= 4):
            return {"ok": False,
                    "error": f"У вопроса {q.get('id','?')} должно быть 2–4 варианта."}

    return {"ok": True, "questions": questions}