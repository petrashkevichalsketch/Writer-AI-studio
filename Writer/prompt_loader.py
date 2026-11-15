"""Единая точка входа для чтения промптов.

Выбирает файл по языку текущего проекта: для EN-проекта берётся
<имя>_en.txt, при его отсутствии — русский оригинал (fallback).
Ключи JSON в промптах с кодом не связаны, поэтому дублировать
проверку языка в каждом модуле не нужно.
"""

import db
from pathlib import Path

from config import RPG_MODES, RPG_PROMPT_STAGES, HIST_MODES, HIST_PROMPT_STAGES

PROMPTS_DIR = Path(__file__).parent / "prompts"


def current_language() -> str:
    """Язык текущего проекта; 'ru', если проекта ещё нет."""
    project = db.get_project()
    return project.get("language", "ru") if project else "ru"


# Правила синтаксиса JSON для системных промптов, у которых этого
# раздела нет в тексте файла (мировые стадии). Ошибка в одном значении
# роняет весь ответ модели, поэтому напоминание дешевле ретрая.
_JSON_RULES = {
    "ru": (
        "\n\n━━━ СИНТАКСИС JSON (критично для парсинга) ━━━\n"
        "1. Кавычка \" используется ТОЛЬКО для разметки JSON — ключи и "
        "границы строк. Внутри текстовых значений для цитат и названий "
        "используй русские «ёлочки»: неэкранированная \" внутри значения "
        "ломает парсинг.\n"
        "2. Каждое текстовое значение — одной строкой, без переносов.\n"
        "3. Между соседними полями и элементами массивов всегда ставь "
        "запятую; запятая перед ] или } запрещена (trailing comma).\n"
        "4. Первый символ ответа — «{» (или «[»), последний — «}» (или "
        "«]»), без какого-либо текста до и после."
    ),
    "en": (
        "\n\n━━━ JSON SYNTAX (critical for parsing) ━━━\n"
        "1. The double quote \" is used ONLY for JSON markup — keys and "
        "string boundaries. Inside string values use «guillemets» or "
        "single quotes for citations: an unescaped \" breaks parsing.\n"
        "2. Every text value must be a single line, no line breaks inside.\n"
        "3. Always put a comma between adjacent fields and array items; a "
        "comma before ] or } is forbidden (trailing comma).\n"
        "4. The first character of the answer is \"{\" (or \"[\"), the last "
        "is \"}\" (or \"]\"), with no text before or after."
    ),
}


def json_syntax_rules() -> str:
    """Блок правил синтаксиса JSON под язык текущего проекта."""
    return _JSON_RULES[current_language()]


def get_prompt(stage_name: str) -> str:
    """Прочитать промпт этапа с учётом языка и режимов проекта.

    Приоритет: 1) жанровый промпт *_rpg.txt, если проект создан в
    режиме litrpg/realrpg и стадия подлежит подмене (файлы жанровые
    и сами задают язык текста по input.project.language); 2) промпт
    исторической прозы *_hist.txt — мир эпохи из «Места и эпохи»
    собирается из знания модели, а не выдумывается; 3) EN-промпт для
    англоязычного проекта; 4) русский оригинал (fallback).
    Режимы не комбинируются: rpg_mode имеет приоритет над hist_mode.
    """
    project = db.get_project()
    if (stage_name in RPG_PROMPT_STAGES
            and project and project.get("rpg_mode") in RPG_MODES
            and project["rpg_mode"] != "none"):
        rpg_path = PROMPTS_DIR / f"{stage_name}_rpg.txt"
        if rpg_path.exists():
            return rpg_path.read_text(encoding="utf-8")
    if (stage_name in HIST_PROMPT_STAGES
            and project and project.get("hist_mode") in HIST_MODES
            and project["hist_mode"] != "none"):
        hist_path = PROMPTS_DIR / f"{stage_name}_hist.txt"
        if hist_path.exists():
            return hist_path.read_text(encoding="utf-8")
    suffix = "_en" if (project or {}).get("language", "ru") == "en" else ""
    path = PROMPTS_DIR / f"{stage_name}{suffix}.txt"
    if not path.exists():
        path = PROMPTS_DIR / f"{stage_name}.txt"  # fallback на русский
    return path.read_text(encoding="utf-8")
