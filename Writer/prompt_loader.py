"""Единая точка входа для чтения промптов.

Выбирает файл по языку текущего проекта: для EN-проекта берётся
<имя>_en.txt, при его отсутствии — русский оригинал (fallback).
Ключи JSON в промптах с кодом не связаны, поэтому дублировать
проверку языка в каждом модуле не нужно.
"""

import db
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def current_language() -> str:
    """Язык текущего проекта; 'ru', если проекта ещё нет."""
    project = db.get_project()
    return project.get("language", "ru") if project else "ru"


def get_prompt(stage_name: str) -> str:
    """Прочитать промпт этапа с учётом языка проекта."""
    suffix = "_en" if current_language() == "en" else ""
    path = PROMPTS_DIR / f"{stage_name}{suffix}.txt"
    if not path.exists():
        path = PROMPTS_DIR / f"{stage_name}.txt"  # fallback на русский
    return path.read_text(encoding="utf-8")
