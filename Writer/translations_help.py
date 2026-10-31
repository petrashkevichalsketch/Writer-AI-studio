"""EN-словарь страницы «Справка» (help.html).

Ключ — точный русский текст из шаблона (в т.ч. обрывки предложений
вокруг инлайн-тегов <b>/<code>/<a>), значение — английский фрагмент.
Подхватывается translations.py автоматически.
"""

STRINGS = {
    "Полное руководство от установки до готовой книги.":
        "The complete guide, from setup to a finished book.",

    # ── Что это такое
    "Что это такое": "What it is",
    "AI Novelist — локальный инструмент, который пишет литературное произведение целиком. Ты задаёшь пять полей, приложение строит мир, персонажей, сюжет и генерирует главы одну за другой. Весь прогресс хранится локально в файле":
        "AI Novelist is a local tool that writes a literary work in full. You fill in five fields, and the app builds the world, the characters, the plot, and generates the chapters one by one. All progress is stored locally in",
    "Работает с любой OpenAI-совместимой моделью: локальной (Unsloth, vLLM, Ollama) или облачной (OpenAI, DeepSeek, OpenRouter, Groq и др.).":
        "Works with any OpenAI-compatible model: local (Unsloth, vLLM, Ollama) or cloud (OpenAI, DeepSeek, OpenRouter, Groq, etc.).",

    # ── Шаг 1
    "Шаг 1. Настройка LLM": "Step 1. Setting up the LLM",
    "Открой": "Open",
    "Три поля, которые надо заполнить:": "Three fields to fill in:",
    "— адрес OpenAI-совместимого сервера. По умолчанию":
        "— the address of an OpenAI-compatible server. Default:",
    "Для облачных провайдеров:": "For cloud providers:",
    "Для локальных:": "For local servers:",
    "— ключ доступа. Для облачных провайдеров (OpenAI, DeepSeek, OpenRouter) обязателен. Для локальных серверов часто можно оставить пустым (Ollama, LM Studio). Однако, если твой локальный сервер (например, Unsloth Studio или vLLM с флагом":
        "— the access key. Required for cloud providers (OpenAI, DeepSeek, OpenRouter). For local servers it can often be left empty (Ollama, LM Studio). However, if your local server (e.g., Unsloth Studio or vLLM started with the",
    ") требует токен, впиши его сюда. Приложение будет передавать его в заголовке":
        ") flag requires a token, enter it here. The app will send it in the",
    "— точное имя модели, как его знает сервер. Для локальных:":
        "— the exact model name as the server knows it. For local servers:",
    "и т.п. Для облачных — то, что указано в документации провайдера.":
        "etc. For cloud providers — whatever their documentation specifies.",
    "Слов на главу": "Words per chapter",
    "и": "and",
    "— оставь по умолчанию, если не уверен.":
        "— leave at the defaults if unsure.",
    "После заполнения нажми": "After filling in, press",
    ". Проверить связь с моделью можно кнопкой":
        ". To test the model connection, use the button",
    "на странице": "on the",
    "— она отправит тестовый запрос и покажет ответ в логе.":
        "— it sends a test request and shows the answer in the log.",

    # ── Шаг 2
    "Шаг 2. Создание проекта": "Step 2. Creating a project",
    "На": "On the",
    "главной": "home page",
    "заполни пять полей и выбери формат:": "fill in the five fields and choose a format:",
    "Тема": "Theme",
    "— о чём книга («цена бессмертия»).": "— what the book is about (\"the price of immortality\").",
    "Жанр": "Genre",
    "— тип фантастики.": "— the type of fiction.",
    "Формат": "Format",
    "— рассказ (1–3 главы), повесть (4–8), роман (15–20).":
        "— short story (1–3 chapters), novella (4–8), novel (15–20).",
    "Место и эпоха": "Setting and era",
    "— например, «Земля, 2187 год».": "— e.g., \"Earth, year 2187\".",
    "Центральный конфликт": "Central conflict",
    "— одна фраза, кто с кем и из-за чего.": "— one sentence: who against whom, and over what.",
    "Тональность": "Tone",
    "— необязательно («мрачная», «ироничная»).": "— optional (\"dark\", \"ironic\").",
    "Нажми": "Press",
    "Построить мир": "Build the world",
    "Откроется пайплайн.": "The pipeline will open.",

    # ── Шаг 3
    "Шаг 3. Сборка мира и сюжета": "Step 3. Building the world and the plot",
    "На странице": "On the",
    "две кнопки автосбора:": "page there are two auto-build buttons:",
    "— проходит все 17 стадий Фазы 1 и Фазы 2 последовательно, без остановок на уточнения. Это быстрее, но результат — на усмотрение модели.":
        "— runs all 17 stages of Phase 1 and Phase 2 sequentially, without stopping for clarifications. Faster, but the result is up to the model.",
    "— то же самое, но": "— the same, but",
    "перед каждой стадией": "before each stage",
    "открывается wizard уточнений. Модель задаёт 3–5 вопросов о том, как развить эту стадию. Ответы уходят в промпт генерации и приоритетнее догадок модели.":
        "a clarifications wizard opens. The model asks 3–5 questions about how to develop that stage. The answers go into the generation prompt and take priority over the model's guesses.",
    "Полный автосбор занимает 30–90 минут — в зависимости от модели и от того, используешь ли ты уточнения.":
        "A full auto-build takes 30–90 minutes — depending on the model and on whether you use clarifications.",
    "Если стадия упадёт — автосбор остановится. Правь ошибку и жми автосбор заново. Уже готовые стадии пропустятся.":
        "If a stage fails, the auto-build stops. Fix the error and start the auto-build again. Completed stages will be skipped.",
    "Можно запускать стадии вручную — по одной кнопкой ▶ напротив каждой.":
        "You can also run stages manually — one at a time with the ▶ button next to each.",
    "Или нажать": "Or press",
    "у стадии, чтобы получить вопросы именно к ней, а потом запустить генерацию с ответами.":
        "on a stage to get questions for that specific stage, and then run the generation with the answers.",

    # ── Шаг 4
    "Шаг 4. Проверка и утверждение": "Step 4. Review and approval",
    "После автосбора открой": "After the auto-build, open the",
    ". Там все слои в виде JSON и отчёт аудита целостности. Если всё устраивает — жми":
        ". It shows all layers as JSON and the consistency audit report. If you like what you see, press",
    "Затем": "Then",
    "— карточки и сеть отношений. Если нравится —":
        "— the cards and the relationship network. If you like them, press",
    ". Проверь список глав и утверди —": ". Review the chapter list and approve —",
    "Сбросить любой слой — на соответствующей странице. Кнопка":
        "Reset any layer on its own page. The button",
    "обнулит слой и все зависящие.": "clears the layer and everything downstream.",
    "↺ Сбросить с каскадом": "↺ Reset with cascade",
    "▶▶ Автосбор: мир + сюжет": "▶▶ Auto-build: world + plot",
    "❓▶▶ Автосбор с вопросами": "❓▶▶ Auto-build with questions",
    "ссылается на старые события).": "still references the old events).",

    # ── Аудит
    "Работа с аудитом целостности": "Working with the consistency audit",
    "странице Мира": "World page",
    "есть вкладка": "has a",
    "«Аудит»": "\"Audit\"",
    ". Модель-судья проверяет мир на противоречия между слоями, битые ссылки и логические дыры. Вердикт —":
        " tab. The judge model checks the world for contradictions between layers, broken references, and logical holes. The verdict is",
    "(0–2 проблемы),": "(0–2 problems),",
    "Каждую проблему можно": "Each problem can be",
    "исправить одним из двух способов": "fixed in one of two ways",
    "— модель получает одну проблему и один слой, возвращает новую версию слоя. После применения все стадии ниже по каскаду":
        "— the model receives one problem and one layer, and returns a new version of that layer. After applying, all downstream stages",
    "сбрасываются": "are reset",
    "— их придётся перегенерировать. Перед применением автоматически делается снапшот — можно откатить.":
        "— you will have to regenerate them. A snapshot is made automatically before applying — you can roll back.",
    "— открывается редактор JSON текущего слоя. Ты правишь вручную и сохраняешь. Downstream":
        "— opens a JSON editor for the current layer. You edit manually and save. Downstream",
    "не сбрасывается": "is NOT reset",
    "— но это и риск: возможен рассинхрон (например,":
        "— but that is also the risk: a desync is possible (e.g.,",
    ") обновятся только при следующем": ") are updated only at the next",
    "главы.": "of a chapter.",
    "Важно:": "Important:",
    "избегай": "avoid",
    "на слоях верхнего каскада (": "on top-cascade layers (",
    "), если мир уже развит. Сброс 16 стадий — большая потеря. Для точечных правок лучше использовать":
        ") if the world is already developed. Resetting 16 stages is a big loss. For targeted edits, prefer",
    "✏️ Ручную правку": "✏️ Manual edit",
    "Некоторые «проблемы» — намеренные (например, «запрет на код, но кто-то его обходит» — это и есть сюжет). Аудит — советник, не судья.":
        "Some \"problems\" are intentional (e.g., \"code is banned, but someone circumvents it\" — that IS the plot). The audit is an advisor, not a judge.",

    # ── Шаг 5
    "Шаг 5. Генерация глав": "Step 5. Generating chapters",
    "Главу 1": "Chapter 1",
    "и нажми": "and press",
    ". Текст будет стримиться в центр экрана. Когда закончится — жми":
        ". The text will stream into the center of the screen. When it finishes, press",
    "Analyze — это второй вызов модели: она читает текст и извлекает":
        "Analyze is a second model call: it reads the text and extracts the",
    "патч канона": "canon patch",
    "— что изменилось в мире после этой главы (события, состояния персонажей, раскрытые секреты).":
        "— what changed in the world after this chapter (events, character states, revealed secrets).",
    "Проверь diff, нажми": "Review the diff and press",
    "— патч применится, снапшот канона сохранится. Если что-то не так —":
        "— the patch is applied and a canon snapshot is saved. If something is wrong,",
    "откатит.": "rolls it back.",
    "Перед генерацией можно нажать": "Before generating you can press",
    "— модель задаст 3–5 вопросов о развитии главы. Ответы уйдут в промпт генерации. Это тот же механизм, что и у стадий пайплайна.":
        "— the model will ask 3–5 questions about the chapter's development. The answers go into the generation prompt. This is the same mechanism the pipeline stages use.",

    # ── Редактирование
    "Редактирование текста главы": "Editing the chapter text",
    "Готовый текст можно править прямо в браузере — например, поправить диалог или убрать лишний абзац.":
        "You can edit the finished text right in the browser — for example, fix a line of dialogue or remove an extra paragraph.",
    "Двойной клик": "Double-click",
    "по тексту — он станет редактируемым (появится синяя рамка вокруг).":
        "the text — it becomes editable (a blue frame appears around it).",
    "Правишь как в обычном текстовом редакторе: клавиатура, мышь,":
        "Edit as in a regular text editor: keyboard, mouse,",
    ". Правой кнопкой мыши вызывается системное контекстное меню браузера — Вставить, Копировать, Вырезать.":
        ". Right-click opens the browser's system context menu — Paste, Copy, Cut.",
    "Когда закончил — нажми": "When done, press",
    ". Счётчик слов обновится, текст сохранится в базу.":
        ". The word counter updates and the text is saved to the database.",
    "Клик вне текста тоже выключает режим редактирования, но":
        "Clicking outside the text also exits edit mode, but",
    "не сохраняет": "does NOT save",
    ". Сохраняй кнопкой.": ". Save with the button.",
    "После ручной правки нажми": "After manual edits, press",
    ", чтобы канон учёл изменения. Иначе патч будет построен по старой версии текста.":
        " so the canon accounts for the changes. Otherwise the patch will be built from the old version of the text.",

    # ── Внешняя модель
    "Альтернатива: внешняя модель": "Alternative: an external model",
    "Если у тебя локальная модель слаба для прозы, но есть доступ к сильной (например, веб-версия Claude или GPT), используй кнопки":
        "If your local model is too weak for prose but you have access to a strong one (e.g., the web version of Claude or GPT), use the",
    "— откроется готовый промпт с контекстом главы.":
        "— a ready-made prompt with the chapter context opens.",
    "Скопируй, вставь в чат с мощной моделью.": "Copy it and paste it into a chat with a powerful model.",
    "Получи текст главы — верни его через": "Get the chapter text — return it via",
    "Жми": "Press",
    "— дальше как обычно.": "— then as usual.",
    "те же кнопки есть у стадий": "the same buttons exist for the stages",
    "— их можно сгенерировать во внешней модели и вернуть через":
        "— they can be generated with an external model and returned via",

    # ── Экспорт и бэкап
    "Экспорт книги": "Exporting the book",
    "Когда главы готовы, открой": "When the chapters are ready, open the",
    "Книгу": "Book",
    "— увидишь весь текст и статистику. Экспорт в":
        " page — you will see the full text and statistics. Export to",
    "— одной кнопкой.": "— one button each.",
    "Бэкап": "Backup",
    "есть кнопки": "page there are the buttons",
    "Настройках": "Settings",
    ". Первая — скачивает снапшот": ". The first one downloads a snapshot of",
    ", вторая — загружает ранее сохранённый. Перед восстановлением текущая база копируется в":
        ", the second one uploads a previously saved copy. Before restoring, the current database is copied to",
    "не копируй": "do not copy",
    "через проводник при работающем сервере — получишь битый файл. Для бэкапа пользуйся кнопкой. После восстановления нужно перезапустить uvicorn.":
        " with File Explorer while the server is running — you will get a corrupt file. Use the button for backups. After restoring, restart uvicorn.",

    # ── FAQ
    "Частые вопросы": "FAQ",
    "Сколько это стоит?": "How much does it cost?",
    "Локально — бесплатно (нужна видеокарта от 8 ГБ). Через облако — зависит от провайдера, обычно $1–5 за весь роман на хорошей модели.":
        "Locally — free (you need a GPU with 8+ GB of VRAM). Via the cloud — depends on the provider, usually $1–5 for a whole novel on a good model.",
    "Можно перегенерировать только одну главу?": "Can I regenerate just one chapter?",
    "Да. Открой главу и нажми": "Yes. Open the chapter and press",
    "— текст перезапишется. Старый патч можно откатить через":
        "— the text will be overwritten. The old patch can be rolled back via",
    "Что делать, если аудит нашёл проблемы?": "What if the audit finds problems?",
    "Смотри раздел": "See the section",
    "«Работа с аудитом целостности»": "\"Working with the consistency audit\"",
    "выше. Коротко: если правка точечная —": "above. In short: for a targeted edit —",
    ". Если проблема структурная и слой не верхний —":
        ". If the problem is structural and the layer is not a top one —",
    ". Намеренные противоречия — оставить.": ". Intentional contradictions — leave them.",
    "Как переключиться на другую модель?": "How do I switch to a different model?",
    ". Все стадии берут модель из настроек в момент запуска. Можно вести мир на одной модели, а главы генерировать на другой.":
        ". All stages take the model from the settings at launch time. You can build the world on one model and generate chapters on another.",
    "Модель не возвращает валидный JSON. Что делать?":
        "The model does not return valid JSON. What do I do?",
    "Мелкие модели часто «срываются» на длинных структурированных ответах. Попробуй: 1) перезапустить стадию — иногда проходит со второй попытки; 2) переключиться на более крупную модель; 3) уменьшить объём работы, разбив её на подзадачи через ❓ уточнения.":
        "Small models often break down on long structured answers. Try: 1) re-running the stage — it sometimes works on the second attempt; 2) switching to a larger model; 3) reducing the amount of work by splitting it into subtasks via ❓ clarifications.",
    "Что показывает панель размышлений модели?":
        "What does the model thinking panel show?",
    "Reasoning-модели (DeepSeek-R1, Qwen с thinking и подобные) сначала рассуждают, потом пишут. Размышления видны на странице главы: моноширинный поток без рамки, затухающий к краям. Когда модель переходит к прозе, панель сворачивается в кнопку":
        "Reasoning models (DeepSeek-R1, Qwen with thinking, and the like) reason first and write afterwards. The thinking is visible on the chapter page: a monospaced stream without a frame, fading out at the edges. When the model switches to prose, the panel collapses into a button",
    "Размышления": "Thinking",
    " — клик разворачивает полный текст мыслей. Приложение читает и поле":
        " — clicking it expands the full train of thought. The app reads both the",
    ", и инлайновые": " field and inline",
    ". Отключить рассуждения можно в настройках":
        ". You can disable reasoning in the settings",
    ") — или использовать не-reasoning модель для генерации глав.":
        ") — or use a non-reasoning model for chapter generation.",

    # ── Кнопка 🤖 и варианты стадии
    "Кнопка 🤖: стадию пишет сильная модель":
        "The 🤖 button: the strong model writes the stage",
    "Если в": "If the",
    "Настройках": "Settings",
    "заполнен раздел": "section",
    "«Сильная модель (облако)»": "'Strong model (cloud)'",
    "(base_url, token, имя модели — любой OpenAI-совместимый API), у стадий":
        "(base_url, token, model name — any OpenAI-compatible API) is filled in, the stages",
    "появляется кнопка": "get the",
    "Она сама отправляет промпт стадии в облачную модель, валидирует ответ и сохраняет его как вариант «Сильная модель» — без копирования через чат.":
        "button. It sends the stage's prompt to the cloud model itself, validates the response, and saves it as a 'Strong model' variant — no copying through a chat.",
    "Ответ стримится в лог пайплайна; при ошибках валидации делается одна повторная попытка со списком ошибок.":
        "The response streams into the pipeline log; on validation errors one retry is made with the error list.",
    "Результат НЕ заменяет активный слой — он ждёт в":
        "The result does NOT replace the active layer — it waits in",
    "«Варианты стадии»": "'Stage variants'",
    "Кнопка": "The",
    "в настройках проверяет токен и связь до запуска.":
        "button in Settings checks the token and connection before a run.",
    "Каждый способ сборки стадии оставляет свой вариант: «Локальная модель» (кнопка ▶), «Сильная модель» (🤖), «Вставка вручную» (📥). В окне вариантов можно:":
        "Each way of building a stage leaves its own variant: 'Local model' (the ▶ button), 'Strong model' (🤖), 'Manual paste' (📥). In the variants window you can:",
    "— структурный дифф с текущим слоем: число глав, POV, локации, tension_target, объёмы и сцены каждой главы + свежая валидация варианта против текущей библии (id-шники могли измениться).":
        "— a structural diff against the current layer: chapter count, POVs, locations, tension_target, lengths, and each chapter's scenes, plus a fresh validation of the variant against the current bible (ids may have changed).",
    "— заменить активный слой вариантом (с повторной валидацией). Стадии, собранные после, могут потребовать пересборки.":
        "— replace the active layer with the variant (re-validated first). Stages built after it may need rebuilding.",
    "Локальная модель и большие романы": "The local model and long novels",
    "План глав нового формата (5 объектов-сцен на главу) для романа в 15–20 глав — это большой JSON. Настройка":
        "A chapter outline in the new format (5 scene objects per chapter) for a 15–20-chapter novel is a large JSON. The",
    "Адрес можно не вбивать вручную: у обоих профилей есть селектор":
        "You don't have to type the address by hand: both profiles have a",
    "(Anthropic, OpenAI, OpenRouter, DeepSeek, Groq, Gemini, z.ai, Kimi, xAI, aiai.by) — выбор подставляет base_url. Кнопка":
        "selector (Anthropic, OpenAI, OpenRouter, DeepSeek, Groq, Gemini, z.ai, Kimi, xAI, aiai.by) — picking one fills in the base_url. The",
    "подтягивает живой список моделей прямо с сайта провайдера (по текущим значениям base_url и токена из формы) — начните вводить имя и выберите из подсказок; ручной ввод при этом остаётся доступен.":
        "button pulls the live model list straight from the provider's site (using the current base_url and token from the form) — start typing a name and pick from the suggestions; manual entry remains available.",
    "«Пакетная генерация (глав в пакете)»": "'Batched generation (chapters per batch)'",
    "делит работу: пусто — авто (романы ≥10 глав собираются пакетами по 5 глав), 0 — одним вызовом, 3–10 — размер пакета. Пакет проверяется сразу, ошибки уходят модели на исправление до перехода к следующему; в конце весь план проходит полную валидацию.":
        "setting splits the work: empty — auto (novels of ≥10 chapters are built in batches of 5), 0 — a single call, 3–10 — the batch size. Each batch is validated immediately and errors are fed back to the model before the next batch; the merged plan then passes full validation.",
    "Живой экран стадии": "Live stage screen",
    "Пока собирается план (кнопки ▶ и 🤖), над логом работает тот же «голографический экран», что и при написании глав: фаза («пакет 2/4 · главы 6–10»), прогресс-бар по главам, счётчик символов и хвост размышлений модели, если модель их отдаёт (Qwen, облачные reasoning-модели). Если модель думает молча (Gemma и др.) — экран показывает фазы и объём, а мыслей просто не появляется.":
        "While the outline is being built (▶ and 🤖 buttons), the same 'holographic screen' as in chapter writing runs above the log: the phase ('batch 2/4 · chapters 6–10'), a per-chapter progress bar, a character counter, and the tail of the model's reasoning when the model emits it (Qwen, cloud reasoning models). If the model thinks silently (Gemma etc.), the screen shows phases and volume — there are simply no thoughts to show.",
}
