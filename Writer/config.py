"""Глобальные константы и настройки по умолчанию."""

from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "book.db"
STYLE_DIR = BASE_DIR / "style"
EXPORT_DIR = BASE_DIR / "exports"

HOST = "127.0.0.1"
PORT = 8013

# ─── Уровни автономии ───────────────────────────────────────────
AUTONOMY_LEVELS = ("assisted", "supervised", "autonomous")
DEFAULT_AUTONOMY = "supervised"

# ─── Жанры sci-fi ───────────────────────────────────────────────
GENRES = (
    "cyberpunk",
    "space_opera",
    "hard_sf",
    "dystopia",
    "post_apocalypse",
    "first_contact",
    "time_travel",
    "biopunk",
    "military_sf",
    "generation_ship",
    "climate_fiction",
    "singularity",
    "social_sf",
)

GENRE_LABELS = {
    "cyberpunk":        "Киберпанк",
    "space_opera":      "Космоопера",
    "hard_sf":          "Твёрдая НФ",
    "dystopia":         "Антиутопия",
    "post_apocalypse":  "Постапокалипсис",
    "first_contact":    "Первый контакт",
    "time_travel":      "Путешествия во времени",
    "biopunk":          "Биопанк",
    "military_sf":      "Военная НФ",
    "generation_ship":  "Поколенческий корабль",
    "climate_fiction":  "Климатическая НФ",
    "singularity":      "Сингулярность",
    "social_sf":        "Социальная НФ",
}

# ─── Фазы и стадии ──────────────────────────────────────────────
STAGES_PHASE1 = [
    "world_core",
    "world_rules",
    "history",
    "institutions",
    "geography",
    "economy",
    "society",
    "culture",
    "conflicts",
    "secrets",
    "lore_graph",         # программно
    "relevance_map",      # программно
    "consistency_audit",  # AI-судья
]

STAGES_PHASE2 = [
    "characters",
    "relations",
    "story_structure",
    "chapter_outline",
]

STAGES_PHASE3 = [
    "style_seed",
    "chapters",           # цикл по главам
]

ALL_STAGES = STAGES_PHASE1 + STAGES_PHASE2 + STAGES_PHASE3

# Человекочитаемые метки для UI
STAGE_LABELS = {
    "world_core":        "Ядро мира",
    "world_rules":       "Правила мира",
    "history":           "История",
    "institutions":      "Институции",
    "geography":         "География",
    "economy":           "Экономика",
    "society":           "Общество",
    "culture":           "Культура",
    "conflicts":         "Конфликты",
    "secrets":           "Секреты",
    "lore_graph":        "Граф лора",
    "relevance_map":     "Релевантность",
    "consistency_audit": "Аудит целостности",
    # ── Фаза 2
    "characters":        "Персонажи",
    "relations":         "Отношения",
    "story_structure":   "Структура сюжета",
    "chapter_outline":   "План глав",
}

# Точки approve
APPROVE_POINTS = {
    "after_world":   "consistency_audit",
    "after_chars":   "relations",
    "after_outline": "chapter_outline",
}

# ─── Бюджеты стадий (из ТЗ) ─────────────────────────────────────
BUDGETS = {
    "world_core":        {"max_calls": 3, "retry": 3, "max_objects": 2},
    "world_rules":       {"max_calls": 3, "retry": 3, "max_objects": 5},
    "history":           {"max_calls": 3, "retry": 3, "max_objects": 20},
    "institutions":      {"max_calls": 3, "retry": 3, "max_objects": 6},
    "geography":         {"max_calls": 3, "retry": 3, "max_objects": 8},
    "economy":           {"max_calls": 2, "retry": 3, "max_objects": 5},
    "society":           {"max_calls": 3, "retry": 3, "max_objects": 8},
    "culture":           {"max_calls": 3, "retry": 3, "max_objects": 5},
    "conflicts":         {"max_calls": 3, "retry": 3, "max_objects": 7},
    "secrets":           {"max_calls": 3, "retry": 3, "max_objects": 7},
    "consistency_audit": {"max_calls": 2, "retry": 3, "max_objects": 0},
    "characters":        {"max_calls": 3, "retry": 3, "max_objects": 7},
    "relations":         {"max_calls": 3, "retry": 3, "max_objects": 0},
    "story_structure":   {"max_calls": 3, "retry": 3, "max_objects": 20},
    "chapter_outline":   {"max_calls": 3, "retry": 3, "max_objects": 20},
    "chapter_generate":  {"max_calls": 1, "retry": 0, "max_objects": 0},
    "chapter_analyze":   {"max_calls": 3, "retry": 3, "max_objects": 0},
    "chapter_audit":     {"max_calls": 2, "retry": 3, "max_objects": 0},
}

# ─── Правила литературной структуры ─────────────────────────────
# ─── Правила литературной структуры ─────────────────────────────
CHAPTER_WORDS_TARGET = 3000
ACT_STRUCTURE_DEFAULT = "3-act"

# Форматы книги: сколько глав, какой объём в знаках
BOOK_FORMATS = {
    "short_story": {
        "label":           "Рассказ",
        "chapters_min":    1,
        "chapters_max":    3,
        "chapters_default": 2,
        "chars_min":       30_000,
        "chars_max":       80_000,
        "chars_default":   50_000,
        "words_per_chapter": 2500,
        "description":     "1–3 главы, 30–80 тыс. знаков. ~15 минут генерации.",
    },
    "novella": {
        "label":           "Повесть",
        "chapters_min":    4,
        "chapters_max":    8,
        "chapters_default": 6,
        "chars_min":       150_000,
        "chars_max":       300_000,
        "chars_default":   200_000,
        "words_per_chapter": 3000,
        "description":     "4–8 глав, 150–300 тыс. знаков. ~1 час генерации.",
    },
    "novel": {
        "label":           "Роман",
        "chapters_min":    15,
        "chapters_max":    20,
        "chapters_default": 18,
        "chars_min":       350_000,
        "chars_max":       500_000,
        "chars_default":   400_000,
        "words_per_chapter": 3000,
        "description":     "15–20 глав, 350–500 тыс. знаков. ~2 часа генерации.",
    },
}

DEFAULT_BOOK_FORMAT = "novel"

# Старые константы оставлены для совместимости (используются в промптах
# как дефолты, если формат не задан явно).
BOOK_TARGET_CHARS = BOOK_FORMATS[DEFAULT_BOOK_FORMAT]["chars_default"]
BOOK_CHAPTERS_MIN = BOOK_FORMATS[DEFAULT_BOOK_FORMAT]["chapters_min"]
BOOK_CHAPTERS_MAX = BOOK_FORMATS[DEFAULT_BOOK_FORMAT]["chapters_max"]

# ─── Настройки по умолчанию (таблица settings) ──────────────────
DEFAULTS = {
    "llm_base_url":     "http://127.0.0.1:8888/v1",
    "llm_api_token":    "",
    "llm_model_name":   "",
    "autonomy_level":   DEFAULT_AUTONOMY,
    "language":         "ru",
    "chapter_words":    str(CHAPTER_WORDS_TARGET),
    "enable_thinking":  "false",
    "book_format":      DEFAULT_BOOK_FORMAT,
}