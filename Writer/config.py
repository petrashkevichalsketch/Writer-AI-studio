"""Глобальные константы и настройки по умолчанию."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _data_dir() -> Path:
    """Каталог для изменяемых данных (БД, экспорты, логи).

    WRITER_DATA_DIR задаёт Android-обёртка (main_android.py) — файловое
    хранилище приложения. В установленной копии (Program Files) запись
    рядом с кодом у обычного пользователя запрещена, поэтому используем
    %APPDATA%\\WriterAIStudio. Старый book.db из папки программы
    переносится в db.init().
    """
    env_dir = os.environ.get("WRITER_DATA_DIR")
    if env_dir:
        d = Path(env_dir)
    else:
        appdata = os.environ.get("APPDATA")
        d = Path(appdata) / "WriterAIStudio" if appdata else BASE_DIR / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "book.db"
STYLE_DIR = BASE_DIR / "style"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = DATA_DIR / "logs"

HOST = "127.0.0.1"
PORT = 8013

# Версия статики: подставляется в ?v= у css/js. Менять при каждом
# релизе — иначе браузеры держат старые js/css в кэше.
STATIC_VERSION = "0.3.5-outline-export"

# Версия приложения: футер и сверка с релизами GitHub (кнопка
# «Проверить обновления» в Настройках). Меняется руками при релизе.
APP_VERSION = "0.6.7"

# ─── Уровни автономии ───────────────────────────────────────────
AUTONOMY_LEVELS = ("assisted", "supervised", "autonomous")
DEFAULT_AUTONOMY = "supervised"

# ─── Жанры / Категории ──────────────────────────────────────────
GENRES = (
    # Фантастика
    "cyberpunk", "space_opera", "hard_sf", "dystopia",
    "post_apocalypse", "first_contact", "time_travel", "biopunk",
    "military_sf", "generation_ship", "climate_fiction",
    "singularity", "social_sf", "fantasy",
    # Фэнтези-жанры (сильно влияют на стилистику и тон сюжета)
    "dark_fantasy", "epic_fantasy", "urban_fantasy", "slavic_fantasy",
    "steampunk",
    # Современная проза
    "detective", "thriller", "historical", "romance",
    "horror", "magical_realism", "adventure", "mystery",
    "drama", "comedy", "satire"
)

GENRE_LABELS = {
    # Фантастика
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
    "fantasy":          "Фэнтези",
    "dark_fantasy":     "Тёмное фэнтези",
    "epic_fantasy":     "Эпическое фэнтези",
    "urban_fantasy":    "Городское фэнтези",
    "slavic_fantasy":   "Славянское фэнтези",
    "steampunk":        "Стимпанк",
    # Современная проза
    "detective":        "Детектив",
    "thriller":         "Триллер",
    "historical":       "Исторический роман",
    "romance":          "Романтика / Любовный роман",
    "horror":           "Хоррор / Ужасы",
    "magical_realism":  "Магический реализм",
    "adventure":        "Приключения",
    "mystery":          "Мистика / Загадка",
    "drama":            "Драма",
    "comedy":           "Комедия",
    "satire":           "Сатира",
}

# EN-варианты для англоязычного интерфейса (переключатель en|ru в шапке)
GENRE_LABELS_EN = {
    # Фантастика
    "cyberpunk":        "Cyberpunk",
    "space_opera":      "Space Opera",
    "hard_sf":          "Hard SF",
    "dystopia":         "Dystopia",
    "post_apocalypse":  "Post-Apocalypse",
    "first_contact":    "First Contact",
    "time_travel":      "Time Travel",
    "biopunk":          "Biopunk",
    "military_sf":      "Military SF",
    "generation_ship":  "Generation Ship",
    "climate_fiction":  "Climate Fiction",
    "singularity":      "Singularity",
    "social_sf":        "Social SF",
    "fantasy":          "Fantasy",
    "dark_fantasy":     "Dark fantasy",
    "epic_fantasy":     "Epic fantasy",
    "urban_fantasy":    "Urban fantasy",
    "slavic_fantasy":   "Slavic fantasy",
    "steampunk":        "Steampunk",
    # Современная проза
    "detective":        "Detective",
    "thriller":         "Thriller",
    "historical":       "Historical Fiction",
    "romance":          "Romance",
    "horror":           "Horror",
    "magical_realism":  "Magical Realism",
    "adventure":        "Adventure",
    "mystery":          "Mystery",
    "drama":            "Drama",
    "comedy":           "Comedy",
    "satire":           "Satire",
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

ALL_STAGES = STAGES_PHASE1 + STAGES_PHASE2

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

# EN-вариант меток стадий (для переключателя языка UI)
STAGE_LABELS_EN = {
    "world_core":        "World Core",
    "world_rules":       "World Rules",
    "history":           "History",
    "institutions":      "Institutions",
    "geography":         "Geography",
    "economy":           "Economy",
    "society":           "Society",
    "culture":           "Culture",
    "conflicts":         "Conflicts",
    "secrets":           "Secrets",
    "lore_graph":        "Lore Graph",
    "relevance_map":     "Relevance Map",
    "consistency_audit": "Consistency Audit",
    # ── Фаза 2
    "characters":        "Characters",
    "relations":         "Relations",
    "story_structure":   "Plot Structure",
    "chapter_outline":   "Chapter Outline",
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
    "story_structure":   {"max_calls": 3, "retry": 4, "max_objects": 20},
    "chapter_outline":   {"max_calls": 3, "retry": 3, "max_objects": 20},
    "chapter_generate":  {"max_calls": 1, "retry": 0, "max_objects": 0},
    "chapter_analyze":   {"max_calls": 3, "retry": 3, "max_objects": 0},
    "chapter_audit":     {"max_calls": 2, "retry": 3, "max_objects": 0},
}

# ─── Правила литературной структуры ─────────────────────────────
# Целевой объём главы по умолчанию берётся из BOOK_FORMATS
# (words_per_chapter); настройка chapter_words в settings — override.

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

# EN-подписи форматов (label/description подменяются в ctx() при ui='en')
BOOK_FORMATS_LABELS_EN = {
    "short_story": {
        "label":       "Short story",
        "description": "1–3 chapters, 30–80k chars. ~15 minutes to generate.",
    },
    "novella": {
        "label":       "Novella",
        "description": "4–8 chapters, 150–300k chars. ~1 hour to generate.",
    },
    "novel": {
        "label":       "Novel",
        "description": "15–20 chapters, 350–500k chars. ~2 hours to generate.",
    },
}

DEFAULT_BOOK_FORMAT = "novel"

# ─── Режим RPG (модификатор жанра, выбирается на первой странице) ──
# none — обычный режим (стандартные промпты, поведение по умолчанию);
# litrpg / realrpg — промпты всех мировых стадий (Фаза 1) и
# story_structure, chapter_outline, chapter_writer, chapter_writer_scene
# (Фаза 2) заменяются на жанровые *_rpg.txt. В RPG-режиме поле «Жанр»
# трактуется как жанр игрового мира/Системы, «Место и эпоха» — основная
# локация книги (для litrpg — мир игры), «Начальная локация» — слой
# реальности, где живёт герой.
RPG_MODES = ("none", "litrpg", "realrpg")

RPG_MODE_LABELS = {
    "none":    "1 — Обычный (текущие промпты)",
    "litrpg":  "2 — ЛитРПГ",
    "realrpg": "3 — РеалРПГ",
}

RPG_MODE_LABELS_EN = {
    "none":    "1 — Standard (default prompts)",
    "litrpg":  "2 — LitRPG",
    "realrpg": "3 — RealRPG",
}

# Стадии, промпты которых заменяются в RPG-режиме: Фаза 1 строит
# двухслойный мир (реальность + игра/Система) по жанровым промптам,
# Фаза 2 — жанровую структуру, план глав и сцены.
RPG_PROMPT_STAGES = (
    # Фаза 1 — мировые стадии
    "world_core", "world_rules", "history", "institutions",
    "geography", "economy", "society", "culture", "conflicts",
    "secrets", "consistency_audit",
    # Фаза 2 — сюжетные стадии
    "story_structure", "chapter_outline", "chapter_writer",
    "chapter_writer_scene",
)

# ─── Режим исторической прозы (модификатор, рядом с режимом RPG) ──
# none — мир строится как вымышленный (стандартные промпты);
# historical — мир эпохи из поля «Место и эпоха» собирается из знания
# модели о реальном периоде (хроника, институции, быт), а не
# выдумывается. Основная категория (genre) остаётся жанром книги
# (детектив, драма и т.д.). Приоритет подмены: rpg_mode > hist_mode.
HIST_MODES = ("none", "historical")

HIST_MODE_LABELS = {
    "none":       "1 — Обычный (мир строится как вымышленный)",
    "historical": "2 — Историческая проза (мир эпохи — по реальной истории)",
}

HIST_MODE_LABELS_EN = {
    "none":       "1 — Standard (fictional world)",
    "historical": "2 — Historical prose (era world from real history)",
}

# Стадии, промпты которых заменяются в режиме исторической прозы:
# только мировые стадии Фазы 1 (сюжетные промпты жанрово-нейтральны).
HIST_PROMPT_STAGES = (
    "world_core", "world_rules", "history", "institutions",
    "geography", "economy", "society", "culture", "conflicts",
    "secrets", "consistency_audit",
)

# ─── База знаний мира/эпохи (era_kb) ────────────────────────────
# Справка пользователя о реальном периоде/месте/вселенной (не сюжет).
# Инъектируется в payload мировых стадий Фазы 1 целиком — без
# эмбеддингов и поиска: справка влезает в контекст сильных моделей.
# Лимит — защита payload'а от раздувания; лишнее обрезается.
ERA_KB_MAX_CHARS = 60000

# ─── Провайдеры LLM для селектора на странице настроек ──────────
# Базовый набор (OpenAI-совместимые): (id, подпись, base_url).
# base_url подставляется в поле одним кликом; ручной ввод остаётся.
LLM_PROVIDERS = [
    ("anthropic",  "Anthropic (Claude)", "https://api.anthropic.com/v1"),
    ("openai",     "OpenAI",             "https://api.openai.com/v1"),
    ("openrouter", "OpenRouter",         "https://openrouter.ai/api/v1"),
    ("deepseek",   "DeepSeek",           "https://api.deepseek.com/v1"),
    ("groq",       "Groq",               "https://api.groq.com/openai/v1"),
    ("gemini",     "Google Gemini",      "https://generativelanguage.googleapis.com/v1beta/openai"),
    ("zai",        "z.ai (GLM)",         "https://api.z.ai/api/paas/v4"),
    ("kimi",       "Kimi (Moonshot)",    "https://api.moonshot.ai/v1"),
    ("xai",        "xAI (Grok)",         "https://api.x.ai/v1"),
    ("aiai",       "aiai.by",            "https://api.aiai.by/v1"),
]

# ─── Настройки по умолчанию (таблица settings) ──────────────────
DEFAULTS = {
    "llm_base_url":       "http://127.0.0.1:8888/v1",
    "llm_api_token":      "",
    "llm_model_name":     "",
    "autonomy_level":     DEFAULT_AUTONOMY,
    "language":           "ru",
    "ui_language":        "ru",
    # Пусто = целевой объём главы берётся из формата книги проекта
    "chapter_words":      "",
    "chapter_max_tokens": "12000",
    "enable_thinking":    "false",
    # Уровень размышлений Gemini 4 (thinking_level): low/medium/high,
    # xhigh — только Hydrogen/Neon. medium = дефолт провайдера, параметр
    # не отправляется. Применяется, только если имя обычной модели
    # содержит «gemini-4» (другие провайдеры 400 на неизвестное поле).
    "thinking_level":     "medium",
    "book_format":        DEFAULT_BOOK_FORMAT,
    # ── Профиль «сильной модели» (кнопка 🤖 в пайплайне) ──────────
    # Пустой base_url или model_name = профиль не настроен, будет
    # использован основной (локальный) профиль.
    "strong_llm_base_url":   "",
    "strong_llm_api_token":  "",
    "strong_llm_model_name": "",
    "strong_max_tokens":     "32000",
    "strong_enable_thinking": "false",
    # Усилие Opus 5.5 (output_config.effort): low/medium/high/xhigh/max.
    # medium = дефолт провайдера, параметр не отправляется. Применяется,
    # только если имя сильной модели содержит «opus».
    "strong_effort":         "medium",
    # Промпт-кэш Anthropic (cache_control) в по-сценной генерации глав:
    # стабильный префикс (системный промпт + лор/контекст) помечается
    # cache_control и на следующих сценах читается из кэша со скидкой.
    "strong_prompt_caching": "true",
    # Пакетная генерация плана глав: пусто — авто (романы ≥10 глав —
    # пакетами по 5), 0 — всегда одним вызовом, 3..10 — размер пакета.
    "outline_batch_size": "",
    # Какой профиль LLM пишет главы: 'main' (локальная) или 'strong'
    # (облачная). Переключается кнопками на странице главы.
    "chapter_profile":   "main",
    # Авторский стиль: отрывок-образец стилистики для генерации глав
    # (кнопка «Авторский стиль» на странице главы). Один на проект;
    # в промпт добавляет chapter_engine._author_style_block().
    "author_style_text":    "",
    "author_style_enabled": "false",
}
