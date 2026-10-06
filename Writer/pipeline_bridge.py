"""Мост между Writer AI Studio и внешними LLM для стадий планирования.

Собирает промпт стадии в текст (для копирования в Sonnet/GPT) и принимает
ответ в виде JSON с валидацией и сохранением в БД.
"""

import json

import db
import validator


SUPPORTED_STAGES = ("story_structure", "chapter_outline")


def _capture_call(storage: dict):
    """Заглушка вместо _call: сохраняет system+user, не вызывает LLM."""
    def fake_call(system, user_payload, max_tokens, prev_errors=None):
        if prev_errors:
            user_payload = dict(user_payload)
            user_payload["previous_attempt_errors"] = prev_errors
            user_payload["instruction"] = (
                "Предыдущая попытка не прошла валидацию. Исправь именно эти "
                "проблемы, не меняя остальное."
            )
        storage["system"] = system
        storage["user_payload"] = user_payload
        return {}
    return fake_call


def build_prompt(stage: str) -> dict:
    """Возвращает {system, user, combined} для указанной стадии."""
    if stage not in SUPPORTED_STAGES:
        raise ValueError(f"Стадия {stage} не поддерживается.")

    import pipeline.phase2_story as p2

    storage = {}
    original_call = p2._call
    p2._call = _capture_call(storage)
    try:
        project = db.get_project()
        bible = db.get_full_bible()
        ctx = {
            "stage": stage,
            "project": project,
            "bible": bible,
            "prev_errors": [],
        }
        if stage == "story_structure":
            p2.story_structure_fn(ctx)
        elif stage == "chapter_outline":
            p2.chapter_outline_fn(ctx)
    finally:
        p2._call = original_call

    if "system" not in storage:
        raise ValueError(
            f"Не удалось собрать промпт для {stage} — "
            f"возможно, отсутствуют предыдущие стадии."
        )

    system = storage["system"]
    user = json.dumps(storage["user_payload"], ensure_ascii=False, indent=2)
    combined = (
        "=== SYSTEM ===\n" + system.rstrip() + "\n\n"
        "=== USER ===\n" + user + "\n"
    )
    return {
        "stage":        stage,
        "system":       system,
        "user":         user,
        "combined":     combined,
        "system_chars": len(system),
        "user_chars":   len(user),
    }


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def import_payload(stage: str, raw_text: str) -> dict:
    """Парсит JSON из ответа, валидирует, сохраняет. Возвращает {ok, errors}."""
    if stage not in SUPPORTED_STAGES:
        return {"ok": False, "errors": [f"Стадия {stage} не поддерживается."]}

    text = _strip_fences(raw_text)
    i = text.find("{")
    j = text.rfind("}")
    if i < 0 or j < 0:
        return {"ok": False, "errors": ["В тексте не найден JSON-объект."]}

    try:
        data = json.loads(text[i:j+1])
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [f"Ошибка парсинга JSON: {e}"]}

    bible = db.get_full_bible()
    if stage == "story_structure":
        errors = validator.validate_story_structure(data, bible)
    else:
        errors = validator.validate_chapter_outline(data, bible)

    if errors:
        return {"ok": False, "errors": errors}

    db.save_bible_stage(stage, data, validated=True)
    db.set_stage(stage, "done")
    return {"ok": True, "errors": []}