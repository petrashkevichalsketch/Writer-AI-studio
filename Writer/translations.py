"""Локализация интерфейса (UI): словарь EN с ключом по русскому тексту.

Русский — исходный язык приложения: translate() возвращает текст как
есть. Для EN выполняется lookup; строка, отсутствующая в словаре,
возвращается по-русски — пропуск перевода не ломает страницу, а только
оставляет её непереведённой до пополнения словаря.

Язык UI хранится в settings под ключом ui_language ('ru' по умолчанию)
и НЕ зависит от языка книги проекта (project.language).

Словарь составлен из секций: базовая _EN ниже + словари подсистем
(translations_help.py — подключается напрямую, translations_validator.py —
шаблоны сообщений валидатора, матчатся по позициям), которые
подхватываются автоматически, если файл существует.
"""

import db
import json
import re as _re

LANGS = ("ru", "en")

_EN: dict[str, str] = {
    # ── Шапка и навигация (base.html)
    "AI-Писатель": "AI Writer",
    "Старт": "Start",
    "Пайплайн": "Pipeline",
    "Мир": "World",
    "Персонажи": "Characters",
    "Структура": "Structure",
    "План": "Outline",
    "Книга": "Book",
    "Справка": "Help",
    "Настройки": "Settings",
    "Supervised по умолчанию": "Supervised by default",

    # ── Страница «Старт» (index.html)
    "Старт — AI-Писатель": "Start — AI Writer",
    "Создать проект": "Create a Project",
    "Стандартный (сборка мира)": "Standard (world building)",
    "Готовый план (Custom)": "Ready-made plan (Custom)",
    "Заполните пять полей. Всё остальное — мир, персонажи, сюжет — приложение построит само.":
        "Fill in five fields. Everything else — the world, characters, plot — the app will build itself.",
    "1. Тема": "1. Theme",
    "например: тайна старой усадьбы": "e.g.: the secret of an old manor",
    "2. Жанр / Категория": "2. Genre / Category",
    "2а. Формат": "2a. Format",
    "3. Место и эпоха": "3. Setting and era",
    "например: Царицын, 1890 год": "e.g.: Tsaritsyn, 1890",
    "4. Центральный конфликт": "4. Central conflict",
    "Одна фраза: кто с кем и из-за чего": "One sentence: who against whom, and over what",
    "5. Тональность (опционально)": "5. Tone (optional)",
    "мрачная, ироничная, медитативная": "dark, ironic, meditative",
    "6. Язык книги / Book Language": "6. Book Language",
    "Язык книги / Book Language": "Book Language",
    "Русский": "Russian",
    "Построить мир →": "Build the world →",
    "Вставьте ваш готовый план. Приложение вызовет модель, которая извлечёт из текста персонажей, базовые правила мира и разобьёт ваши главы на сцены (beats).":
        "Paste your ready-made plan. The app will call the model to extract characters and basic world rules from the text and split your chapters into scenes (beats).",
    "⚠ Если проект уже существует — он будет заменён только после успешного разбора плана. Пока модель работает, старый проект в безопасности.":
        "⚠ If a project already exists, it will be replaced only after the plan is parsed successfully. While the model is working, the old project stays safe.",
    "Название проекта": "Project title",
    "Мой готовый роман": "My finished novel",
    "Текст плана": "Plan text",
    "Глава 1: Детектив приезжает в поместье и находит тело...&#10;Глава 2: Допрос дворецкого...":
        "Chapter 1: The detective arrives at the manor and finds a body...&#10;Chapter 2: Interrogating the butler...",
    "Импортировать и начать →": "Import and start →",
    "Текущий проект:": "Current project:",
    "создан": "created",
    "Удалить проект и весь прогресс? Действие необратимо.": "Delete the project and all progress? This action cannot be undone.",
    "Сбросить всё": "Reset everything",

    # ── Страница «Настройки» (settings.html)
    "например, qwen2.5-14b-instruct": "e.g., qwen2.5-14b-instruct",
    "Слов на главу (пусто = из формата книги)": "Words per chapter (empty = from the book format)",
    "напр. 3000; пусто — формат книги проекта": "e.g. 3000; empty — use the project's book format",
    "Max tokens генерации главы": "Max tokens for chapter generation",
    "Сохранить": "Save",
    "Бэкап проекта": "Project backup",
    "Сохранить копию": "Save a copy",
    "скачивает консистентный снапшот": "downloads a consistent snapshot of",
    "через": "via",
    "Работает на живом сервере, ничего не ломает. Складывайте копии в облако или на флешку.":
        "Works on a live server without breaking anything. Keep copies in the cloud or on a flash drive.",
    "Восстановить": "Restore",
    "принимает ранее сохранённый": "accepts a previously saved",
    "проверяет целостность, делает резервную копию текущей базы": "verifies its integrity, backs up the current database",
    "и подменяет файл.": "and swaps in the file.",
    "После восстановления нужно перезапустить uvicorn.": "After restoring, restart uvicorn.",
    "💾 Сохранить копию": "💾 Save a copy",
    "📥 Восстановить из файла": "📥 Restore from file",
    "Восстановление базы": "Database restore",
    "Восстановить базу из файла «{name}»?\n\n• Текущая база будет сохранена как book_before_restore_*.db\n• После восстановления нужно ПЕРЕЗАПУСТИТЬ приложение":
        "Restore the database from file \"{name}\"?\n\n• The current database will be saved as book_before_restore_*.db\n• After restoring you must RESTART the application",
    "загрузка...": "loading...",
    "Резервная копия:": "Backup copy:",
    "ошибка:": "error:",

    # ── Страница «Пайплайн» (pipeline.html)
    "Компиляция мира и сюжета": "Compiling the world and the plot",
    "Запускайте стадии по порядку сверху вниз. Жёлтый индикатор — идёт генерация, зелёный — готово, красный — провал.":
        "Run the stages in order, top to bottom. Yellow — generating, green — done, red — failed.",
    "Кнопка": "The button",
    "внизу — проверка связи с локальной LLM.": "at the bottom tests the local LLM connection.",
    "Фаза 1 — Мир": "Phase 1 — World",
    "Фаза 2 — Персонажи и сюжет": "Phase 2 — Characters and plot",
    "Задать уточняющие вопросы": "Ask clarifying questions",
    "Запустить стадию": "Run the stage",
    "Промпт для внешней модели": "Prompt for an external model",
    "Вставить JSON": "Paste JSON",
    "Автосбор: мир + сюжет": "Auto-build: world + plot",
    "Автосбор с вопросами": "Auto-build with questions",
    "Проверить LLM (_ping)": "Test LLM (_ping)",
    "Очистить лог": "Clear log",
    "Автосбор": "Auto-build",
    "проходит все стадии Фазы 1 и Фазы 2 по порядку, пропускает уже готовые (✓), останавливается на первой ошибке.":
        "runs all Phase 1 and Phase 2 stages in order, skips completed ones (✓), and stops at the first error.",
    "— то же, но перед каждой стадией открывает wizard уточнений. Можно пропустить вопросы у стадии («Пропустить всё») или прервать весь автосбор (крестик).":
        "— the same, but opens a clarifying-questions wizard before each stage. You can skip a stage's questions (\"Skip all\") or abort the whole auto-build (the cross).",
    "Approve-кнопки и генерация глав — по-прежнему вручную.": "Approve buttons and chapter generation remain manual.",
    "Уточним стадию": "Clarify the stage",
    "Загрузка вопросов…": "Loading questions…",
    "← Назад": "← Back",
    "Пропустить": "Skip",
    "Пропустить всё": "Skip all",
    "Далее →": "Next →",

    # ── Страница «Мир» (world.html)
    "Все слои мира. Можно просмотреть, откатить любую стадию с каскадом или принять мир целиком.":
        "All world layers. You can view them, roll back any stage with a cascade, or approve the world as a whole.",
    "✓ Мир утверждён": "✓ World approved",
    "Отозвать approve": "Revoke approval",
    "Мир не утверждён": "World not approved",
    "✋ Approve #1 — принять мир": "✋ Approve #1 — accept the world",
    "Мир ещё не построен": "World not built yet",
    "Сгенерируйте все слои на": "Generate all the layers on",
    "Аудит": "Audit",
    "Сбросить стадию «{name}» и все зависимые?": "Reset stage \"{name}\" and everything downstream?",
    "Сбросить с каскадом": "Reset with cascade",
    "Слой ещё не сгенерирован.": "The layer has not been generated yet.",
    "Отчёт аудита целостности": "Consistency audit report",
    "Вердикт:": "Verdict:",
    "проблем:": "problems:",
    "слой:": "layer:",
    "🛠 Исправить": "🛠 Fix",
    "✏️ Ручная правка": "✏️ Manual edit",
    "Аудит ещё не запускался.": "The audit has not been run yet.",
    "Исправить проблему аудита": "Fix an audit problem",
    "Слой:": "Layer:",
    "Уровень:": "Severity:",
    "Проблема": "Problem",
    "Рекомендация": "Suggestion",
    "Внимание.": "Warning.",
    "После правки слоя": "After editing the layer",
    "все стадии ниже по каскаду будут": "all downstream stages will be",
    "сброшены": "reset",
    ", Approve #1 снят. Перед применением автоматически создаётся снапшот — его можно откатить.":
        "; Approve #1 is revoked. A snapshot is created automatically before applying — you can roll it back.",
    "🛠 Применить": "🛠 Apply",
    "↺ Откатить фикс": "↺ Roll back the fix",
    "↻ Обновить страницу": "↻ Reload the page",
    "Отмена": "Cancel",
    "Ручная правка слоя:": "Manual layer edit:",
    "Отредактируйте JSON ниже. Валидатор слоя проверит структуру перед записью. Ошибки будут показаны.":
        "Edit the JSON below. The layer validator will check the structure before saving. Errors will be shown.",
    "Проблема аудита": "Audit problem",
    "↻ Загрузить текущее": "↻ Load current",
    "JSON слоя…": "Layer JSON…",
    "Риск повреждения связей.": "Risk of breaking references.",
    "Правка сохраняется в": "The edit is saved to",
    "Слои ниже по каскаду останутся в": ". Downstream layers will stay at the",
    "старой": "old",
    "версии — возможен внутренний рассинхрон (например,": "version — an internal desync is possible (e.g.,",
    "изменён, а": "is changed while",
    "ссылается на старые события.": "still references the old events).",
    "Канон-таблицы (": "Canon tables (",
    "не обновляются": "are NOT updated",
    "этой правкой — они синхронизируются только при": "by this edit — they are synced only via",
    "из главы.": "from a chapter.",
    "↺ Сбросить все стадии ниже по каскаду (как при «🛠 Исправить»)": "↺ Reset all downstream stages (as with \"🛠 Fix\")",
    "💾 Записать": "💾 Save",

    # ── Страница «Глава» (chapter.html)
    "Глава {n}": "Chapter {n}",
    "Глава {n} —": "Chapter {n} —",
    "Оглавление": "Contents",
    "❓ Уточнить": "❓ Clarify",
    "📋 Промпт": "📋 Prompt",
    "📥 Вставить текст": "📥 Paste text",
    "статус:": "status:",
    "слов:": "words:",
    "Редактирование:": "Editing:",
    "двойной клик по тексту — режим правки.": "double-click the text to edit it.",
    "Ctrl+V / Ctrl+C работают. Сохраняется кнопкой": "Ctrl+V / Ctrl+C work. Save with the button",
    "(клик вне текста — не сохраняет).": "(clicking outside the text does not save).",
    "Workflow с внешней моделью:": "Workflow with an external model:",
    "[📋 Промпт] → скопировать → вставить в чат с мощной моделью → её ответ вернуть через [📥 Вставить текст] → [🔎 Analyze].":
        "[📋 Prompt] → copy → paste into a chat with a powerful model → return its answer via [📥 Paste text] → [🔎 Analyze].",
    "Или нажмите": "Or press",
    "— модель задаст 3–5 вопросов о развитии главы перед генерацией.": "— the model will ask 3–5 questions about the chapter's development before generation.",
    "План главы": "Chapter plan",
    "Акт:": "Act:",
    "Цель:": "Purpose:",
    "Локация:": "Location:",
    "Сцены главы ({n})": "Chapter scenes ({n})",
    "Ключевые предметы": "Key objects",
    "Персонажи в сцене": "Characters in the scene",
    "Трогает секреты": "Touches secrets",
    "Патч канона": "Canon patch",
    "Промпт для главы {n}": "Prompt for chapter {n}",
    "Скопируйте целиком и вставьте в чат с мощной моделью (Claude, GPT, DeepSeek и т.п.). Первый блок — системная инструкция, второй — JSON с контекстом главы. Ответ модели — чистый текст главы.":
        "Copy it in full and paste it into a chat with a powerful model (Claude, GPT, DeepSeek, etc.). The first block is the system instruction, the second is the JSON with the chapter context. The model's answer is the plain text of the chapter.",
    "📋 Скопировать всё": "📋 Copy all",
    "⬇ Скачать .txt": "⬇ Download .txt",
    "Вставить текст главы {n}": "Paste text for chapter {n}",
    "Вставьте текст, полученный от внешней модели. Он заменит текущий текст главы и сохранится как черновик. Затем нажмите":
        "Paste the text received from the external model. It will replace the current chapter text and be saved as a draft. Then press",
    "для извлечения патча канона.": "to extract the canon patch.",
    "Markdown-обёртки": "Markdown wrappers",
    "вокруг всего текста снимаются автоматически.": "around the whole text are removed automatically.",
    "Вставьте текст главы…": "Paste the chapter text…",
    "💾 Сохранить в главу": "💾 Save into the chapter",
    "Уточним главу": "Clarify the chapter",

    # ── Страница «Персонажи» (characters.html)
    "✓ Персонажи утверждены": "✓ Characters approved",
    "✋ Approve #2 — принять персонажей": "✋ Approve #2 — accept the characters",
    "Персонажи ещё не построены": "Characters not built yet",
    "Сначала сгенерируйте characters и relations на": "First generate characters and relations on",
    "Сбросить персонажей и ВСЮ последующую цепочку (relations, story_structure, chapter_outline)? Уже написанные главы и применённые патчи канона НЕ откатываются.":
        "Reset the characters and the ENTIRE downstream chain (relations, story_structure, chapter_outline)? Already written chapters and applied canon patches are NOT rolled back.",
    "↺ Сбросить персонажей + хвост": "↺ Reset characters + downstream",
    "Карточки": "Cards",
    "Ставка:": "Stake:",
    "Противоречие:": "Contradiction:",
    "Цели:": "Goals:",
    "Изъяны:": "Flaws:",
    "Арка:": "Arc:",
    "Сеть отношений": "Relationship network",

    # ── Страница «Структура» (structure.html)
    "Структура сюжета": "Plot structure",
    "Структура ещё не сгенерирована": "Structure not generated yet",
    "Запустите story_structure на": "Run story_structure on",
    "Глав:": "Chapters:",
    "Актов:": "Acts:",
    "Объём:": "Length:",
    "знаков": "chars",
    "Структура:": "Structure:",
    "Акты": "Acts",
    "Акт {n}": "Act {n}",
    "Главы:": "Chapters:",
    "POV-нити": "POV threads",
    "Кривая напряжения": "Tension curve",
    "Расписание раскрытий": "Reveal schedule",
    "— раскрытие в главе {n},": "— revealed in chapter {n},",
    "предвестники с главы {n}": "foreshadowed from chapter {n}",

    # ── Страница «План» (outline.html)
    "План глав": "Chapter outline",
    "✓ План утверждён": "✓ Outline approved",
    "Начать генерацию глав →": "Start generating chapters →",
    "✋ Approve #3 — принять план книги": "✋ Approve #3 — accept the book outline",
    "План ещё не сгенерирован": "Outline not generated yet",
    "Запустите chapter_outline на": "Run chapter_outline on",
    "Сбросить структуру сюжета и план глав? Уже написанные главы и применённые патчи канона НЕ откатываются.":
        "Reset the plot structure and the chapter outline? Already written chapters and applied canon patches are NOT rolled back.",
    "↺ Сбросить структуру + план": "↺ Reset structure + outline",
    "Название": "Title",
    "Акт": "Act",
    "Цель": "Purpose",
    "Локация": "Location",
    "Слов": "Words",

    # ── Страница «Книга» (book.html)
    "глав": "chapters",
    "слов": "words",
    "принято": "accepted",
    "черновиков": "drafts",
    "Пока ни одна глава не сгенерирована.": "No chapters have been generated yet.",
    "Глава {n}.": "Chapter {n}.",
    "(пусто)": "(empty)",
    "→ открыть в редакторе": "→ open in the editor",

    # ── Мост (модалки внешней модели, _bridge_modals.html)
    "Скопируйте целиком и вставьте в чат с мощной моделью (Sonnet, GPT, DeepSeek и т.п.). Ответ модели — JSON. Верните его через":
        "Copy it in full and paste it into a chat with a powerful model (Sonnet, GPT, DeepSeek, etc.). The model's answer is JSON. Return it via",
    "📥 Вставить JSON": "📥 Paste JSON",
    "Вставить JSON от внешней модели": "Paste JSON from the external model",
    "Вставьте JSON от внешней модели. Он пройдёт валидацию, и при успехе заменит текущую стадию в БД. Markdown-обёртки":
        "Paste the JSON from the external model. It will be validated and, on success, replace the current stage in the DB. Markdown wrappers",
    "вокруг": "around",
    "снимаются автоматически.": "are removed automatically.",
    "Вставьте JSON…": "Paste JSON…",
    "💾 Проверить и сохранить": "💾 Validate and save",

    # ── JavaScript (static/js/*.js, ключи те же — русская исходная строка)
    "ОК": "OK",
    "<b>{n}</b> слов": "<b>{n}</b> words",
    "цель {n}": "target {n}",
    "~{n} слов/мин": "~{n} wpm",
    "✓ готово": "✓ done",
    "✗ ошибка": "✗ error",
    "⛔ Ошибки ({n})": "⛔ Errors ({n})",
    "⚠ Предупреждения ({n})": "⚠ Warnings ({n})",
    "копировать": "copy",
    "Скопировано": "Copied",
    "Не удалось скопировать": "Could not copy",
    "Подтвердить": "Confirm",
    "▶ Запуск {name}": "▶ Running {name}",
    "  ! сеть: {msg}": "  ! network: {msg}",
    "  → старт": "  → start",
    "  попытка {a}/{m}": "  attempt {a}/{m}",
    "  ⚠ предупреждение: {w}": "  ⚠ warning: {w}",
    "  ⚠ {w}": "  ⚠ {w}",
    "  ✗ валидация: {e}": "  ✗ validation: {e}",
    "  ✓ готово. Превью: {p}": "  ✓ done. Preview: {p}",
    "  ✗ провал: {e}": "  ✗ failed: {e}",
    "— поток закрыт —": "— stream closed —",
    "Запустить автосбор?\n\n• Все стадии Фазы 1 и Фазы 2 по порядку\n• Уже готовые (done) будут пропущены\n• При первой ошибке автосбор останавливается\n\nЭто может занять 30–90 минут (зависит от модели).":
        "Start the auto-build?\n\n• All Phase 1 and Phase 2 stages in order\n• Completed (done) stages will be skipped\n• The auto-build stops at the first error\n\nThis can take 30–90 minutes (depends on the model).",
    "⏳ Автосбор идёт…": "⏳ Auto-build running…",
    "═══ АВТОСБОР НАЧАТ ═══": "═══ AUTO-BUILD STARTED ═══",
    "Всего стадий: {n}": "Total stages: {n}",
    "⏭ {s} — уже готово, пропуск": "⏭ {s} — done, skipping",
    "⛔ Автосбор прерван на стадии «{s}»": "⛔ Auto-build aborted at stage \"{s}\"",
    "Проверьте ошибку выше, исправьте и запустите автосбор заново — готовые стадии будут пропущены.":
        "Review the error above, fix it, and start the auto-build again — completed stages will be skipped.",
    "═══ ✓ АВТОСБОР ЗАВЕРШЁН ═══": "═══ ✓ AUTO-BUILD FINISHED ═══",
    "Мир и сюжет готовы. Переходите на /world, /characters, /outline — проверяйте и жмите Approve.":
        "World and plot are ready. Go to /world, /characters, /outline — review and press Approve.",
    "Автосбор завершён — мир и сюжет готовы": "Auto-build finished — world and plot are ready",
    "Запустить автосбор с уточнениями?\n\n• Перед каждой стадией — wizard уточнений\n• «Пропустить всё» — идти без вопросов\n• Крестик — прервать весь автосбор\n• Уже готовые (done) — пропускаются\n\nПродолжить?":
        "Start the auto-build with clarifications?\n\n• A clarifications wizard opens before each stage\n• \"Skip all\" — go without questions\n• The cross — abort the whole auto-build\n• Completed (done) stages are skipped\n\nContinue?",
    "pipeline_wizard.js не загрузился.": "pipeline_wizard.js failed to load.",
    "⏳ Автосбор с вопросами…": "⏳ Auto-build with questions…",
    "═══ АВТОСБОР С ВОПРОСАМИ НАЧАТ ═══": "═══ AUTO-BUILD WITH QUESTIONS STARTED ═══",
    "  ❓ уточнения…": "  ❓ clarifications…",
    "⛔ Автосбор прерван пользователем": "⛔ Auto-build aborted by user",
    "  ⏭ вопросы пропущены": "  ⏭ questions skipped",
    "  ✓ получено ответов: {n}": "  ✓ answers received: {n}",
    "Автосбор прерван: {s}": "Auto-build aborted: {s}",
    "═══ ✓ АВТОСБОР С ВОПРОСАМИ ЗАВЕРШЁН ═══": "═══ ✓ AUTO-BUILD WITH QUESTIONS FINISHED ═══",
    "Мир и сюжет готовы. Переходите на /world, /characters, /outline.":
        "World and plot are ready. Go to /world, /characters, /outline.",
    "system: {a} симв. · user: {b} симв.": "system: {a} chars · user: {b} chars",
    "ошибка: {msg}": "error: {msg}",
    "Промпт скопирован": "Prompt copied",
    "Скопируйте вручную: Ctrl+C": "Copy manually: Ctrl+C",
    "Пусто.": "Empty.",
    "проверка…": "checking…",
    "✓ сохранено": "✓ saved",
    "Стадия обновлена": "Stage updated",
    "⏳ Генерация…": "⏳ Generating…",
    "Генерация главы": "Chapter generation",
    "Сгенерировать главу заново? Текущий текст будет перезаписан.":
        "Regenerate the chapter? The current text will be overwritten.",
    "Сгенерировать": "Generate",
    "соединение (с ответами на {n} вопросов)…": "connecting (with answers to {n} questions)…",
    "соединение с моделью…": "connecting to the model…",
    "Ошибка: {msg}": "Error: {msg}",
    "глава «{t}» · POV: {pov} · модель пишет…": "chapter \"{t}\" · POV: {pov} · the model is writing…",
    "Модель размышляет…": "Model is thinking…",
    "модель размышляет…": "the model is thinking…",
    "модель пишет…": "the model is writing…",
    "Размышления · {n} знаков": "Thinking · {n} chars",
    "глава короткая ({a}/{b} слов) — запрашиваю продолжение…":
        "the chapter is short ({a}/{b} words) — requesting a continuation…",
    "статус: draft · слов: <span id=\"wc\">{n}</span>": "status: draft · words: <span id=\"wc\">{n}</span>",
    "✓ готово · {w} слов · {c} знаков": "✓ done · {w} words · {c} chars",
    "Глава сгенерирована": "Chapter generated",
    "Не удалось сохранить": "Could not save",
    "Сохранено": "Saved",
    "анализ…": "analyzing…",
    "✗ ошибки валидации — см. список ниже": "✗ validation errors — see the list below",
    "✓ анализ готов · {n} предупреждений": "✓ analysis ready · {n} warnings",
    "✓ анализ готов": "✓ analysis ready",
    "События ({n})": "Events ({n})",
    "Состояние персонажей": "Character states",
    "Отношения": "Relationships",
    "Знание": "Knowledge",
    "Секреты": "Secrets",
    "(частично)": "(partial)",
    "Новые локации": "New locations",
    "Новые институции": "New institutions",
    "Изменений нет": "No changes",
    "✗ нечего применять: сначала нажмите Analyze.": "✗ nothing to apply: press Analyze first.",
    "Применить патч": "Apply the patch",
    "Применить патч к канону? Будет создан снапшот для отката.":
        "Apply the patch to the canon? A snapshot for rollback will be created.",
    "Применить": "Apply",
    "применение…": "applying…",
    "✓ применено {t}": "✓ applied {t}",
    "Патч применён": "Patch applied",
    "Откат канона": "Canon rollback",
    "Откатить канон к состоянию ДО главы {n}?": "Roll the canon back to the state BEFORE chapter {n}?",
    "Откатить": "Roll back",
    "Ошибка": "Error",
    "Ошибка отката": "Rollback error",
    "Откат выполнен": "Rollback complete",
    "✓ применён {t}": "✓ applied {t}",
    "анализ готов": "analysis ready",
    "Текст вставлен — нажмите Analyze": "Text pasted — press Analyze",
    "Модель формулирует вопросы…": "The model is composing questions…",
    "неизвестная": "unknown",
    "Ошибка сети: {msg}": "Network error: {msg}",
    "Вопрос {a} из {b}": "Question {a} of {b}",
    "Или свой вариант:": "Or your own variant:",
    "Свободный ответ…": "Free-form answer…",
    "▶ Сгенерировать с ответами": "▶ Generate with answers",
    "Прервать автосбор?": "Abort the auto-build?",
    "pipeline.js не загрузился — генерация недоступна.": "pipeline.js failed to load — generation is unavailable.",
    "(не указана)": "(not given)",
    "модель правит слой…": "the model is editing the layer…",
    "✓ применено": "✓ applied",
    "✓ Слой «{s}» обновлён.": "✓ Layer \"{s}\" updated.",
    "↺ Сброшено {n} стадий: {list}": "↺ Reset {n} stages: {list}",
    "Аудит: было {a} проблем ({v1}) → стало {b} ({v2}).": "Audit: was {a} problems ({v1}) → now {b} ({v2}).",
    "Откат фикса": "Roll back the fix",
    "Откатить фикс? Слой вернётся к состоянию до правки.": "Roll back the fix? The layer returns to its pre-edit state.",
    "откат…": "rolling back…",
    "✓ откат выполнен": "✓ rollback complete",
    "// ошибка: {msg}": "// error: {msg}",
    "загружено": "loaded",
    "✗ невалидный JSON: {msg}": "✗ invalid JSON: {msg}",
    "запись…": "saving…",
    "✗ HTTP {code}, ответ не-JSON: {body}": "✗ HTTP {code}, non-JSON response: {body}",
    "✓ записано": "✓ saved",
    "· предупреждений: {n}": "· warnings: {n}",
    "Нет данных о персонажах.": "No character data.",

    # ── Серверные сообщения (detail=, warnings, SSE) — trf() на бэкенде
    "Глава {num} не найдена в плане.": "Chapter {num} was not found in the outline.",
    "Глава не сгенерирована.": "The chapter has not been generated.",
    "Патч не найден.": "Patch not found.",
    "Сначала запустите Analyze.": "Run Analyze first.",
    "Патч этой главы уже применён. Для повторного применения откатите канон (Rollback) и запустите Analyze заново.":
        "The patch for this chapter has already been applied. To re-apply, roll the canon back (Rollback) and run Analyze again.",
    "Неизвестный формат: {fmt}": "Unknown format: {fmt}",
    "Пустой текст.": "Empty text.",
    "Не удалось создать снапшот: {e}": "Could not create a snapshot: {e}",
    "Ожидается файл .db": "A .db file is expected",
    "Файл слишком мал, чтобы быть базой.": "The file is too small to be a database.",
    "Файл не является SQLite-базой.": "The file is not an SQLite database.",
    "База повреждена: {res}": "The database is corrupt: {res}",
    "В файле нет таблицы pipeline_state — это не база AI-Романиста.":
        "The file has no pipeline_state table — it is not an AI Novelist database.",
    "Не удалось прочитать БД: {e}": "Could not read the database: {e}",
    "База восстановлена, но схему обновить не удалось: {e}. Перезапустите приложение вручную.":
        "The database was restored but the schema update failed: {e}. Restart the application manually.",
    "База восстановлена и схема обновлена.": "The database was restored and the schema updated.",
    "Слой '{stage}' пуст.": "The layer '{stage}' is empty.",
    "Слой '{layer}' пуст.": "The layer '{layer}' is empty.",
    "В аудите нет проблемы со слоем '{stage}'.": "The audit has no problem for the layer '{stage}'.",
    "Пустой JSON.": "Empty JSON.",
    "Невалидный JSON: {e}": "Invalid JSON: {e}",
    "base_url не настроен": "base_url is not configured",
    "LLM base_url не настроен (Settings).": "LLM base_url is not configured (Settings).",
    "LLM model_name не настроен (Settings).": "LLM model_name is not configured (Settings).",
    "Стадия '{name}' ещё не реализована.": "The stage '{name}' is not implemented yet.",
    "Стадия {stage} не поддерживается.": "The stage {stage} is not supported.",
    "Не удалось собрать промпт для {stage} — возможно, отсутствуют предыдущие стадии.":
        "Could not assemble the prompt for {stage} — previous stages may be missing.",
    "В тексте не найден JSON-объект.": "No JSON object found in the text.",
    "Ошибка парсинга JSON: {e}": "JSON parsing error: {e}",
    "Ошибка LLM: {e}": "LLM error: {e}",
    "Модель вернула не JSON-объект.": "The model returned something that is not a JSON object.",
    "Модель не смогла создать план глав.": "The model could not create the chapter outline.",
    "отброшено изменение состояния: {cid} не персонаж": "dropped a state change: {cid} is not a character",
    "отброшено отношение {a}↔{b}: отношения бывают только между персонажами":
        "dropped a relation {a}↔{b}: relations exist only between characters",
    "отброшено знание для {cid}: неизвестный персонаж": "dropped knowledge for {cid}: unknown character",
    "отброшено раскрытие секрета {sid}: неизвестный id": "dropped a secret reveal {sid}: unknown id",
    "отброшена локация {lid}: уже существует": "dropped location {lid}: already exists",
    "отброшена локация «{name}»: дубликат по имени": "dropped location \"{name}\": duplicate name",
    "отброшена институция {iid}: уже существует": "dropped institution {iid}: already exists",
    "отброшена институция «{name}»: дубликат по имени": "dropped institution \"{name}\": duplicate name",
    "отброшена способность для {cid}: неизвестный персонаж": "dropped an ability for {cid}: unknown character",
    "отброшена способность без имени": "dropped an ability without a name",
    "новая формулировка «{name}» — развитие существующей «{matched}»":
        "new wording \"{name}\" — a development of the existing \"{matched}\"",
    "«{name}» похожа на существующую «{matched}» у {cid} — переведена в abilities_upgraded (level {lv1} → {lv2})":
        "\"{name}\" resembles the existing \"{matched}\" of {cid} — moved to abilities_upgraded (level {lv1} → {lv2})",
    "отброшен апгрейд для {cid}: неизвестный персонаж": "dropped an upgrade for {cid}: unknown character",
    "отброшен апгрейд без имени": "dropped an upgrade without a name",
    "первое появление": "first appearance",
    "апгрейд «{name}» у {cid} с new_level={nl} — переведён в abilities_gained (level 1)":
        "upgrade \"{name}\" of {cid} with new_level={nl} — moved to abilities_gained (level 1)",
    "апгрейд «{name}» у {cid} урезан с {nl} до {target} (не более +1 за главу)":
        "upgrade \"{name}\" of {cid} capped from {nl} to {target} (at most +1 per chapter)",
    "Проблема с таким индексом не найдена.": "No problem with this index.",
    "Слой '{layer}' нельзя править через LLM.": "The layer '{layer}' cannot be edited via LLM.",
    "Для слоя '{layer}' нет валидатора.": "There is no validator for the layer '{layer}'.",
    "Слой '{layer}' пуст — нечего править.": "The layer '{layer}' is empty — nothing to fix.",
    "Модель не смогла исправить: {err}": "The model could not fix it: {err}",
    "Ошибка валидатора: {e}": "Validator error: {e}",
    "Перед фиксом {layer} (проблема #{idx})": "Before fixing {layer} (problem #{idx})",
    "Фикс применён, но ре-аудит упал: {e}": "The fix was applied but the re-audit failed: {e}",
    "Нет валидатора для слоя '{layer}'.": "No validator for the layer '{layer}'.",
    "Проблема не найдена.": "Problem not found.",
    "Модель не смогла: {err}": "The model could not: {err}",
    "Предложение модели не проходит валидацию:": "The model's suggestion fails validation:",
    "Слой '{layer}' нельзя править вручную.": "The layer '{layer}' cannot be edited manually.",
    "Ручная правка {layer} (downstream={mode})": "Manual edit of {layer} (downstream={mode})",
    "Проект не создан.": "No project has been created.",
    "Ошибка генерации: {e}": "Generation error: {e}",
    "Продолжение не удалось: {e}": "The continuation failed: {e}",
    "Соединение оборвалось — частичный текст ({n} слов) сохранён как черновик.":
        "The connection dropped — partial text ({n} words) saved as a draft.",
    "Ошибка запроса к модели: {e}": "Model request error: {e}",
    "Не удалось распарсить JSON: {e}": "Could not parse the JSON: {e}",
    "Ожидалось 3–5 вопросов, получено {n}.": "Expected 3–5 questions, got {n}.",

    # ── json_utils + questions (уточняющие вопросы)
    "JSON не найден: {text}": "JSON not found: {text}",
    "Не закрыта фигурная скобка.": "Unclosed curly brace.",
    "Не закрыта квадратная скобка.": "Unclosed square bracket.",
    "Пустой ответ модели.": "Empty model response.",
    "JSON не парсится: {err}. Начало: {chunk}": "JSON does not parse: {err}. Start: {chunk}",
    "Стадия {stage} не задаёт вопросов.": "The stage {stage} does not ask questions.",
    "Неизвестная стадия: {stage}.": "Unknown stage: {stage}.",
    "Модуль стадии {stage} не найден.": "The module for stage {stage} was not found.",
    "Сборка контекста: {e}": "Context assembly: {e}",
    "Стадия {stage} не использует LLM.": "The stage {stage} does not use the LLM.",
    "Элемент questions не объект.": "A questions item is not an object.",
    "У вопроса нет text.": "A question has no text.",
    "У вопроса {id} должно быть 2–4 варианта.": "Question {id} must have 2–4 options.",

    # ── Сильная модель (🤖) и варианты стадии (🗂)
    "Написать сильной моделью (профиль strong)":
        "Write with the strong model (strong profile)",
    "Варианты стадии: сравнить и применить":
        "Stage variants: compare and apply",
    "Сильная модель (облако) — для кнопки 🤖 в пайплайне":
        "Strong model (cloud) — for the 🤖 button in the pipeline",
    "OpenAI-совместимый API внешней модели (Sonnet, GPT, DeepSeek и т.п.). Если пусто — кнопка 🤖 использует основной профиль.":
        "OpenAI-compatible API of an external model (Sonnet, GPT, DeepSeek, etc.). If empty, the 🤖 button falls back to the main profile.",
    "Strong API token": "Strong API token",
    "Strong model name": "Strong model name",
    "Strong max tokens (для больших JSON)": "Strong max tokens (for large JSON)",
    "Генерация плана глав": "Chapter outline generation",
    "Пакетная генерация (глав в пакете)": "Batched generation (chapters per batch)",
    "пусто — авто; 0 — одним вызовом; 3–10 — размер пакета":
        "empty — auto; 0 — single call; 3–10 — batch size",
    "Профиль сильной модели не настроен (Настройки → Сильная модель).":
        "The strong-model profile is not configured (Settings → Strong model).",
    "Профиль сильной модели не настроен.":
        "The strong-model profile is not configured.",
    "Не удалось восстановить payload промпта.":
        "Could not restore the prompt payload.",
    "JSON не распознан: {e}": "JSON not recognized: {e}",
    "🤖 Запрос к сильной модели: {name}":
        "🤖 Request to the strong model: {name}",
    "Сильная модель уже работает — дождитесь завершения":
        "The strong model is already running — wait for it to finish",
    "  → модель: {m}": "  → model: {m}",
    "  … получено {n} симв.": "  … {n} chars received",
    "  ✓ вариант «сильная модель» сохранён (id {id})":
        "  ✓ 'strong model' variant saved (id {id})",
    "попытка {a}/{m}": "attempt {a}/{m}",
    "Сильная модель закончила — вариант сохранён":
        "The strong model finished — variant saved",
    "Откройте 🗂 «Варианты стадии», чтобы сравнить и применить.":
        "Open 🗂 'Stage variants' to compare and apply.",
    "Варианты стадии": "Stage variants",
    "Варианты стадии: {stage}": "Stage variants: {stage}",
    "«Локальная модель» — результат кнопки ▶, «Сильная модель» — кнопки 🤖, «Вставка» — ручной вставки. Сравнение — с текущим активным слоем; применение заменяет его (после downstream-стадии может потребоваться пересбор).":
        "'Local model' — the result of the ▶ button, 'Strong model' — the 🤖 button, 'Manual paste' — pasted by hand. Comparison runs against the current active layer; applying replaces it (downstream stages may need rebuilding).",
    "Вариантов пока нет — запустите стадию ▶, нажмите 🤖 или вставьте JSON через 📥.":
        "No variants yet — run the stage ▶, press 🤖, or paste JSON via 📥.",
    "Локальная модель": "Local model",
    "Сильная модель": "Strong model",
    "Вставка вручную": "Manual paste",
    "активный": "active",
    "симв.": "chars",
    "⚖ Сравнить": "⚖ Compare",
    "✓ Применить": "✓ Apply",
    "сравнение…": "comparing…",
    "Текущий слой → выбранный вариант": "Current layer → selected variant",
    "Различий нет.": "No differences.",
    "⚠ Вариант не проходит валидацию против текущей библии ({n})":
        "⚠ The variant fails validation against the current bible ({n})",
    "Вариант валиден против текущей библии.":
        "The variant is valid against the current bible.",
    "Применить вариант": "Apply variant",
    "Вариант заменит текущий активный слой стадии «{stage}». Стадии, собранные после неё, могут стать неактуальными. Продолжить?":
        "The variant will replace the current active layer of the '{stage}' stage. Stages built after it may become outdated. Continue?",
    "Вариант применён": "Variant applied",
    "Вариант не найден.": "Variant not found.",
    "Глав (текущий → вариант)": "Chapters (current → variant)",
    "Глава {num}: {field}": "Chapter {num}: {field}",
    "Глава {num}: число сцен": "Chapter {num}: number of scenes",
    "Глава {num}: сумма word_target сцен":
        "Chapter {num}: sum of scene word_targets",
    "Глава {num}: events": "Chapter {num}: events",
    "Глава {num}: secrets_touched": "Chapter {num}: secrets_touched",
    "Глава {num}: без изменений": "Chapter {num}: unchanged",
    "{key}: элементов": "{key}: item count",
    "{key}: добавлены id": "{key}: ids added",
    "{key}: удалены id": "{key}: ids removed",
    "{key}: ключей": "{key}: key count",
    "Проверить сильную модель": "Test the strong model",
    "— стадию пишет сильная модель (профиль в Настройках),":
        "— the strong model writes the stage (profile in Settings),",
    "— варианты стадии: сравнить и применить.":
        "— stage variants: compare and apply.",

    # ── «Голографический экран» стадии
    "пакет {i}/{n} · главы {a}..{b}": "batch {i}/{n} · chapters {a}..{b}",
    "сборка и финальная проверка плана…":
        "assembling and final validation of the outline…",
    "одним вызовом": "single call",
    "<b>{n}</b> глав": "<b>{n}</b> chapters",
    "<b>{n}</b> знаков": "<b>{n}</b> chars",
    "сильная модель · {m}": "strong model · {m}",
    "валидация ответа…": "validating the response…",
    "✓ вариант сохранён": "✓ variant saved",

    # ── Переключатель модели генерации глав
    "Обычная модель": "Main model",
    "Профиль LLM для генерации глав (меняется в Настройках)":
        "LLM profile for chapter generation (change in Settings)",
    "не настроен — профиль в Настройках":
        "not configured — profile in Settings",
    "не настроен": "not configured",
    "Сильная модель не настроена (Настройки)":
        "The strong model is not configured (Settings)",
    "Главы пишет сильная модель": "The strong model writes the chapters",
    "Главы пишет обычная модель": "The main model writes the chapters",
    "Не удалось переключить: {msg}": "Could not switch: {msg}",
    "глава «{t}» · POV: {pov} · пишет {m}…":
        "chapter «{t}» · POV: {pov} · {m} is writing…",
    "Профиль должен быть main или strong.": "Profile must be main or strong.",

    # ── Селектор провайдеров и живой список моделей
    "Провайдер": "Provider",
    "— выбрать провайдера —": "— choose a provider —",
    "Модели провайдера": "Provider models",
    "загрузка моделей…": "loading models…",
    "✓ найдено {n} моделей — начните вводить имя или выберите из списка":
        "✓ {n} models found — start typing a name or pick one from the list",
    "Укажите base_url провайдера.": "Enter the provider base_url.",
}

# ── Секции словаря подсистем. ВАЖНО: только СТАТИЧЕСКИЕ import —
# Nuitka не видит динамические __import__ и не включает такие модули
# в сборку (в установленной программе help/валидатор оставались
# русскими именно из-за этого). Отсутствие файла — норма (dev-режим).
try:
    import translations_help
    _EN.update(translations_help.STRINGS)
except ModuleNotFoundError:
    pass

# ── Шаблоны сообщений валидатора: validator.py возвращает ГОТОВЫЕ
# русские строки (значения уже подставлены), поэтому они переводятся
# сопоставлением с позиционными шаблонами ({0}, {1}, ...), а не lookup.
try:
    import translations_validator
    _VALIDATOR_TEMPLATES = dict(translations_validator.STRINGS)
except ModuleNotFoundError:
    _VALIDATOR_TEMPLATES = {}

_template_rx = None


def _match_template(text: str):
    """Сопоставить готовое сообщение с шаблоном валидатора.
    Возвращает EN-строку или None, если шаблон не найден."""
    en = _VALIDATOR_TEMPLATES.get(text)
    if en is not None:
        return en
    global _template_rx
    if _template_rx is None:
        _template_rx = []
        for ru, en in _VALIDATOR_TEMPLATES.items():
            parts = _re.split(r"\{\d+\}", ru)
            if len(parts) < 2:
                continue
            pat = _re.escape(parts[0])
            for i in range(1, len(parts)):
                pat += "(.*)" if i == len(parts) - 1 else "(.+?)"
                pat += _re.escape(parts[i])
            _template_rx.append(
                (_re.compile("^" + pat + "$", _re.S), en))
    for rx, en in _template_rx:
        m = rx.match(text)
        if m:
            try:
                return en.format(*m.groups())
            except Exception:
                return None
    return None


def current_lang() -> str:
    """Текущий язык интерфейса; 'ru', если настройка отсутствует или бита."""
    lang = db.get_setting("ui_language", "ru")
    return lang if lang in ("ru", "en") else "ru"


def translate(text: str) -> str:
    """Перевод строки UI на текущий язык (fallback — исходный русский)."""
    if current_lang() == "ru":
        return text
    en = _EN.get(text)
    if en is not None:
        return en
    # Готовые сообщения валидатора — сопоставлением с шаблоном.
    matched = _match_template(text)
    return matched if matched is not None else text


def trf(template: str, *args, **kw) -> str:
    """Перевод шаблона с подстановками: trf('глава {n}', n=1)."""
    s = translate(template)
    if args or kw:
        s = s.format(*args, **kw)
    return s


def stage_labels() -> dict:
    """Метки стадий пайплайна на языке UI."""
    import config
    return (config.STAGE_LABELS_EN if current_lang() == "en"
            else config.STAGE_LABELS)


def js_dict_json() -> str:
    """Весь EN-словарь как JSON для window.I18N (в RU-режиме — пустой)."""
    if current_lang() == "ru":
        return "{}"
    return json.dumps(_EN, ensure_ascii=False)
