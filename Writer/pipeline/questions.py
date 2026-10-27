"""Уточняющие вопросы к стадиям пайплайна.
Копия механики ask_questions из chapter_engine, но для стадий."""

import asyncio
import json
import threading
from pathlib import Path

import db
import llm
import prompt_loader
from .json_utils import JSONParseError, parse_json
from .registry import get as reg_get
from config import STAGES_PHASE1, STAGES_PHASE2
from translations import trf as _t

PROMPTS = Path(__file__).parent.parent / "prompts"

EXCLUDED = {"lore_graph", "relevance_map"}

# Monkeypatch _call не потокобезопасен — сериализуем (см. pipeline_bridge).
_prompt_lock = threading.Lock()


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
    # Override стадии важнее общего промпта; при EN ищем EN-версию
    # override'а, иначе — общий промпт через loader (EN → fallback RU).
    suffix = "_en" if prompt_loader.current_language() == "en" else ""
    override = PROMPTS / f"pipeline_questions_{stage}{suffix}.txt"
    if override.exists():
        return override.read_text(encoding="utf-8")
    return prompt_loader.get_prompt("pipeline_questions")


async def ask_questions(stage: str) -> dict:
    """Возвращает {ok, questions} или {ok: False, error}."""
    if stage in EXCLUDED:
        return {"ok": False,
                "error": _t("Стадия {stage} не задаёт вопросов.", stage=stage)}
    if stage not in STAGES_PHASE1 and stage not in STAGES_PHASE2:
        return {"ok": False,
                "error": _t("Неизвестная стадия: {stage}.", stage=stage)}

    mod = _pick_module(stage)
    spec = reg_get(stage)
    if mod is None or spec is None:
        return {"ok": False,
                "error": _t("Модуль стадии {stage} не найден.", stage=stage)}

    project = db.get_project()
    if not project:
        return {"ok": False, "error": _t("Проект не создан.")}

    storage: dict = {}
    with _prompt_lock:
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
            return {"ok": False, "error": _t("Сборка контекста: {e}", e=e)}
        finally:
            mod._call = original

    if "payload" not in storage:
        return {"ok": False,
                "error": _t("Стадия {stage} не использует LLM.", stage=stage)}

    system = _pick_system_prompt(stage)
    user = {
        "task":    "pipeline_questions",
        "stage":   stage,
        "project": project,
        "bible":   storage["payload"].get("input") or {},
    }

    loop = asyncio.get_running_loop()

    # Reasoning-модели тратят бюджет на рассуждения и обрываются до JSON:
    # даём запас токенов и одну строгую повторную попытку.
    retry_note = (
        "Your previous answer was not valid JSON (or got cut off before "
        "the JSON). Return ONLY the JSON object with the questions — no "
        "reasoning, no explanations, nothing before or after. The first "
        "character must be '{'."
        if prompt_loader.current_language() == "en" else
        "Предыдущий ответ не был валидным JSON (или оборвался до JSON). "
        "Верни ТОЛЬКО JSON-объект с вопросами — без рассуждений и "
        "пояснений, ничего до и после. Первый символ — «{»."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user",
         "content": json.dumps(user, ensure_ascii=False, indent=2)},
    ]
    raw = ""
    try:
        for attempt in (1, 2):
            raw = await loop.run_in_executor(
                None,
                lambda: llm.chat(messages, stream=False,
                                 temperature=0.7, max_tokens=5000),
            )
            try:
                data = parse_json(raw)
                break
            except JSONParseError:
                if attempt == 2:
                    raise
                messages = [messages[0],
                            {"role": "user", "content": retry_note}]
    except JSONParseError as e:
        return {"ok": False, "error": _t("Не удалось распарсить JSON: {e}", e=e),
                "raw": raw[:500]}
    except Exception as e:
        return {"ok": False, "error": _t("Ошибка запроса к модели: {e}", e=e)}

    questions = data.get("questions") or []
    if not isinstance(questions, list) or not (3 <= len(questions) <= 5):
        return {"ok": False,
                "error": _t("Ожидалось 3–5 вопросов, получено {n}.",
                            n=len(questions)),
                "raw": data}

    for q in questions:
        if not isinstance(q, dict):
            return {"ok": False, "error": _t("Элемент questions не объект.")}
        if not q.get("text"):
            return {"ok": False, "error": _t("У вопроса нет text.")}
        opts = q.get("options") or []
        if not isinstance(opts, list) or not (2 <= len(opts) <= 4):
            return {"ok": False,
                    "error": _t("У вопроса {id} должно быть 2–4 варианта.",
                                id=q.get('id', '?'))}

    return {"ok": True, "questions": questions}