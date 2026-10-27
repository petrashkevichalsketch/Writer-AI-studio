"""EN-шаблоны сообщений validator.py.

validator.py НЕ обёрнут вызовами перевода: он возвращает готовые
русские строки с уже подставленными значениями. translations.py
сопоставляет такие сообщения с этими шаблонами ({0}, {1}, ... —
позиционные группы) и подставляет захваченные значения в EN-шаблон.

Префикс "WARN: " — программный протокол (парсится runner/audit_fix),
поэтому он сохранён и в EN-значениях.
"""

STRINGS = {
    # ── Общие
    "Ожидался JSON-объект.": "A JSON object was expected.",
    "Ожидался JSON-объект с полем events.": "A JSON object with an 'events' field was expected.",

    # ── world_core
    "central_concept.name/one_line пусты.": "central_concept.name/one_line are empty.",
    "immutable_rules: нужно ≥2.": "immutable_rules: at least 2 required.",
    "immutable_rules: у правила нет statement.": "immutable_rules: a rule has no statement.",
    "central_paradox пуст.": "central_paradox is empty.",
    "core_question пуст.": "core_question is empty.",
    "core_question должен быть ровно одним вопросом (со знаком ? в конце).":
        "core_question must be exactly one question (ending with a '?').",
    "tone_tags: пусто.": "tone_tags: empty.",

    # ── world_rules
    "technology должен быть объектом.": "technology must be an object.",
    "technology.{0} пусто.": "technology.{0} is empty.",
    "constraints: нужно ≥3.": "constraints: at least 3 required.",
    "constraints: элемент не объект.": "constraints: an item is not an object.",
    "constraints: у ограничения нет statement.": "constraints: a constraint has no statement.",
    "constraints: у ограничения пуст implications[].": "constraints: a constraint has an empty implications[].",
    "forbidden_techs: пусто.": "forbidden_techs: empty.",
    "В ядре мира нет immutable_rules — не с чем сверять правила.":
        "The world core has no immutable_rules — there is nothing to check the rules against.",

    # ── history
    "events должен быть массивом.": "events must be an array.",
    "events: нужно 10–20, получено {0}.": "events: expected 10–20, got {0}.",
    "events: элемент не объект.": "events: an item is not an object.",
    "events: у события нет id.": "events: an event has no id.",
    "events: дубликат id {0}.": "events: duplicate id {0}.",
    "{0}: causes → несуществующий {1}.": "{0}: causes → non-existent {1}.",
    "{0}: consequences → несуществующий {1}.": "{0}: consequences → non-existent {1}.",
    "{0} (год {1}) не может быть РАНЬШЕ причины {2} (год {3}).":
        "{0} (year {1}) cannot be EARLIER than its cause {2} (year {3}).",
    "Цикл в причинах: {0}": "Cycle in causes: {0}",
    "Нет точки бифуркации (события с ≥2 consequences).":
        "No bifurcation point (an event with ≥2 consequences).",

    # ── institutions
    "institutions должен быть массивом.": "institutions must be an array.",
    "institutions: нужно 5–6, получено {0}.": "institutions: expected 5–6, got {0}.",
    "institutions: элемент не объект.": "institutions: an item is not an object.",
    "institutions: у институции нет id.": "institutions: an institution has no id.",
    "institutions: дубликат id {0}.": "institutions: duplicate id {0}.",
    "{0}: недопустимый type '{1}'.": "{0}: invalid type '{1}'.",
    "{0}: тип '{1}' уже использован (дубликат типа).": "{0}: the type '{1}' is already used (duplicate type).",
    "{0}: поле {1} пусто.": "{0}: the field {1} is empty.",
    "{0}: public_role совпадает с real_role — нет двойного дна.":
        "{0}: public_role matches real_role — no hidden underside.",
    "{0}: {1} пуст.": "{0}: {1} is empty.",

    # ── geography
    "locations должен быть массивом.": "locations must be an array.",
    "locations: нужно 5–8, получено {0}.": "locations: expected 5–8, got {0}.",
    "locations: элемент не объект.": "locations: an item is not an object.",
    "locations: у локации нет id.": "locations: a location has no id.",
    "locations: дубликат id {0}.": "locations: duplicate id {0}.",
    "{0}: traits пуст.": "{0}: traits is empty.",
    "{0}.controlled_by → неизвестная институция {1}.":
        "{0}.controlled_by → unknown institution {1}.",
    "{0}: connected_to пуст.": "{0}: connected_to is empty.",
    "{0}.connected_to: элемент не объект.": "{0}.connected_to: an item is not an object.",
    "{0}: ссылка на саму себя в connected_to.": "{0}: self-reference in connected_to.",
    "{0}.connected_to → неизвестная локация {1}.": "{0}.connected_to → unknown location {1}.",
    "controlled_by пусто у {0} локаций (макс 2).":
        "controlled_by is empty for {0} locations (max 2).",

    # ── economy
    "currency пусто.": "currency is empty.",
    "major_resources: нужно ≥3.": "major_resources: at least 3 required.",
    "scarce_resources: нужно ≥2.": "scarce_resources: at least 2 required.",
    "power_centers: пусто.": "power_centers: empty.",
    "power_centers → неизвестная институция {0}.": "power_centers → unknown institution {0}.",
    "wealth_distribution пусто.": "wealth_distribution is empty.",
    "black_markets: пусто.": "black_markets: empty.",

    # ── society / culture
    "society должен быть объектом.": "society must be an object.",
    "society.{0}: пусто.": "society.{0}: empty.",
    "society.entertainment: пусто.": "society.entertainment: empty.",
    "WARN: common_fears слабо связаны с central_paradox — проверьте вручную на этапе APPROVE #1.":
        "WARN: common_fears are weakly connected to central_paradox — check manually at the APPROVE #1 stage.",
    "culture должен быть объектом.": "culture must be an object.",
    "culture.{0}: пусто.": "culture.{0}: empty.",
    "culture.holidays: максимум 3, получено {0}.": "culture.holidays: maximum 3, got {0}.",
    "culture.popular_myths: нужно ≥3.": "culture.popular_myths: at least 3 required.",

    # ── conflicts
    "primary_conflict: отсутствует или не объект.": "primary_conflict: missing or not an object.",
    "primary_conflict.factions: нужно ровно 2.": "primary_conflict.factions: exactly 2 required.",
    "primary_conflict.factions → неизвестная {0}.": "primary_conflict.factions → unknown {0}.",
    "primary_conflict.{0}: пусто.": "primary_conflict.{0}: empty.",
    "secondary_conflicts: нужно 2–4, получено {0}.": "secondary_conflicts: expected 2–4, got {0}.",
    "secondary_conflicts[{0}].{1}: пусто.": "secondary_conflicts[{0}].{1}: empty.",
    "secondary_conflicts[{0}] → неизвестная {1}.": "secondary_conflicts[{0}] → unknown {1}.",
    "latent_conflicts: нужно ≥2.": "latent_conflicts: at least 2 required.",
    "latent_conflicts[{0}].description пуст.": "latent_conflicts[{0}].description is empty.",
    "latent_conflicts[{0}].activation_conditions пуст.": "latent_conflicts[{0}].activation_conditions is empty.",
    "latent_conflicts[{0}].visibility должен быть 'hidden'.":
        "latent_conflicts[{0}].visibility must be 'hidden'.",

    # ── secrets
    "secrets должен быть массивом.": "secrets must be an array.",
    "secrets: нужно 3–7, получено {0}.": "secrets: expected 3–7, got {0}.",
    "secrets: элемент не объект.": "secrets: an item is not an object.",
    "secrets: у секрета нет id.": "secrets: a secret has no id.",
    "secrets: дубликат id {0}.": "secrets: duplicate id {0}.",
    "{0}.truth пуст.": "{0}.truth is empty.",
    "{0}.reveal_rules: не объект.": "{0}.reveal_rules: not an object.",
    "{0}.reveal_rules.earliest_chapter должно быть 1..{1}.":
        "{0}.reveal_rules.earliest_chapter must be 1..{1}.",
    "{0}.reveal_priority должно быть числом 0..1.":
        "{0}.reveal_priority must be a number from 0 to 1.",
    "Нужен хотя бы один секрет с reveal_priority > 0.8 (главная тайна).":
        "At least one secret with reveal_priority > 0.8 is required (the book's main secret).",

    # ── lore_graph / relevance_map
    "nodes: пусто или не массив.": "nodes: empty or not an array.",
    "edges: не массив.": "edges: not an array.",
    "stats: не объект.": "stats: not an object.",
    "relevance: пусто или не объект.": "relevance: empty or not an object.",
    "relevance[{0}] = {1} вне диапазона 0..1.": "relevance[{0}] = {1} is out of the 0..1 range.",

    # ── consistency_audit
    "problems должен быть массивом.": "problems must be an array.",
    "problems[{0}]: не объект.": "problems[{0}]: not an object.",
    "problems[{0}]: severity '{1}' не из списка.": "problems[{0}]: severity '{1}' is not in the list.",
    "problems[{0}]: layer пусто.": "problems[{0}]: layer is empty.",
    "problems[{0}]: description пусто.": "problems[{0}]: description is empty.",
    "overall_verdict должен быть pass|warn|fail.": "overall_verdict must be pass|warn|fail.",

    # ── characters
    "characters должен быть массивом.": "characters must be an array.",
    "characters: нужно 3–7, получено {0}.": "characters: expected 3–7, got {0}.",
    "characters: элемент не объект.": "characters: an item is not an object.",
    "characters: у персонажа нет id.": "characters: a character has no id.",
    "characters: дубликат id {0}.": "characters: duplicate id {0}.",
    "{0}.name пусто.": "{0}.name is empty.",
    "{0}.personal_stake пусто.": "{0}.personal_stake is empty.",
    "{0}.contradiction пусто.": "{0}.contradiction is empty.",
    "{0}.side → неизвестная институция {1}.": "{0}.side → unknown institution {1}.",
    "{0}.secrets → неизвестный секрет {1}.": "{0}.secrets → unknown secret {1}.",
    "{0}.initial_abilities: должен быть массивом.": "{0}.initial_abilities: must be an array.",
    "{0}.initial_abilities: максимум 3, получено {1}.": "{0}.initial_abilities: maximum 3, got {1}.",
    "{0}.initial_abilities[{1}]: не объект.": "{0}.initial_abilities[{1}]: not an object.",
    "{0}.initial_abilities[{1}]: нет name.": "{0}.initial_abilities[{1}]: no name.",
    "{0}.initial_abilities[{1}]: нет description.": "{0}.initial_abilities[{1}]: no description.",
    "{0}.initial_abilities[{1}]: level должен быть 1..3.":
        "{0}.initial_abilities[{1}]: level must be 1..3.",
    "Персонажи занимают одну сторону — нужно ≥2 разных сторон или хотя бы один neutral.":
        "All characters are on one side — at least 2 different sides or one neutral character are required.",

    # ── relations
    "relations должен быть массивом.": "relations must be an array.",
    "relations: элемент не объект.": "relations: an item is not an object.",
    "relations: отсутствует from/to.": "relations: from/to is missing.",
    "relations: {0} связан сам с собой.": "relations: {0} is linked to themselves.",
    "relations: неизвестный участник {0}→{1}.": "relations: unknown participant {0}→{1}.",
    "relations: дубликат пары {0}↔{1}.": "relations: duplicate pair {0}↔{1}.",
    "relations {0}→{1}: недопустимый type '{2}'.": "relations {0}→{1}: invalid type '{2}'.",
    "relations {0}→{1}: tension должен быть 0..100.": "relations {0}→{1}: tension must be 0..100.",
    "relations: у {0} только {1} связей (нужно ≥2).": "relations: {0} has only {1} links (at least 2 required).",
    "relations: нет ни одной связи enemy.": "relations: no enemy link at all.",
    "relations: нет ни одной связи ally.": "relations: no ally link at all.",

    # ── story_structure
    "total_chapters: нужно целое 1..50, получено {0}.": "total_chapters: an integer 1..50 is required, got {0}.",
    "story_beats: должен быть массивом.": "story_beats: must be an array.",
    "story_beats: отсутствуют обязательные биты: {0}.": "story_beats: required beats are missing: {0}.",
    "story_beats: неизвестные ключи: {0}.": "story_beats: unknown keys: {0}.",
    "story_beats: дубликаты ключей: {0}.": "story_beats: duplicate keys: {0}.",
    "story_beats: главы должны идти в порядке возрастания.":
        "story_beats: chapters must be in ascending order.",
    "story_beats[{0}]: chapter вне 1..{1}.": "story_beats[{0}]: chapter is outside 1..{1}.",
    "story_beats[{0}]: пустой description.": "story_beats[{0}]: empty description.",
    "story_beats: opening_image должен быть в главе 1.":
        "story_beats: opening_image must be in chapter 1.",
    "story_beats: final_image должен быть в главе {0}.":
        "story_beats: final_image must be in chapter {0}.",
    "story_beats: между break_into_two и midpoint должно быть минимум 2 главы.":
        "story_beats: at least 2 chapters are required between break_into_two and midpoint.",
    "story_beats: между midpoint и all_is_lost должно быть минимум 3 главы.":
        "story_beats: at least 3 chapters are required between midpoint and all_is_lost.",
    "story_beats: между all_is_lost и final_image должно быть минимум 3 главы.":
        "story_beats: at least 3 chapters are required between all_is_lost and final_image.",
    "acts: пусто.": "acts: empty.",
    "acts: глава {0} вне 1..{1}.": "acts: chapter {0} is outside 1..{1}.",
    "acts: глава {0} встречается дважды.": "acts: chapter {0} appears twice.",
    "acts: покрыто {0} глав из {1}.": "acts: {0} of {1} chapters are covered.",
    "pov_threads: пусто.": "pov_threads: empty.",
    "pov_threads: неизвестный персонаж {0}.": "pov_threads: unknown character {0}.",
    "pov_threads: глава {0} назначена двум нитям.": "pov_threads: chapter {0} is assigned to two threads.",
    "pov_threads: не покрыты главы {0}.": "pov_threads: chapters not covered: {0}.",
    "character_arcs: пусто.": "character_arcs: empty.",
    "character_arcs: неизвестный персонаж {0}.": "character_arcs: unknown character {0}.",
    "reveal_schedule: не массив.": "reveal_schedule: not an array.",
    "reveal_schedule: секрет {0} не запланирован.": "reveal_schedule: the secret {0} is not scheduled.",
    "reveal_schedule[{0}]: reveal_at_chapter вне 1..{1}.":
        "reveal_schedule[{0}]: reveal_at_chapter is outside 1..{1}.",
    "reveal_schedule[{0}]: foreshadow_from ≥ reveal_at_chapter.":
        "reveal_schedule[{0}]: foreshadow_from ≥ reveal_at_chapter.",
    "tension_curve: длина {0}, ожидается {1}.": "tension_curve: length {0}, expected {1}.",
    "tension_curve: значения должны быть 0..1.": "tension_curve: values must be 0..1.",

    # ── chapter_outline
    "chapters должен быть массивом.": "chapters must be an array.",
    "chapters: {0} глав, ожидалось {1}.": "chapters: {0} chapters, expected {1}.",
    "chapters: num должны идти 1..N без пропусков.": "chapters: num must run 1..N without gaps.",
    "ch.{0}: pov {1} не из characters.": "ch.{0}: pov {1} is not in characters.",
    "ch.{0}: location {1} не из geography.": "ch.{0}: location {1} is not in geography.",
    "ch.{0}: characters_present → {1} не существует.": "ch.{0}: characters_present → {1} does not exist.",
    "ch.{0}: events → {1} не из history (новые события не указывать).":
        "ch.{0}: events → {1} is not in history (do not introduce new events).",
    "ch.{0}: purpose пусто.": "ch.{0}: purpose is empty.",
    "ch.{0}: beats должен быть массивом.": "ch.{0}: beats must be an array.",
    "ch.{0}: beats — 3–5 сцен, получено {1}.": "ch.{0}: beats — 3–5 scenes required, got {1}.",
    "ch.{0}.beats[{1}]: пусто.": "ch.{0}.beats[{1}]: empty.",
    "ch.{0}.beats[{1}]: слишком длинный ({2} слов, максимум 70).":
        "ch.{0}.beats[{1}]: too long ({2} words, maximum 70).",
    "ch.{0}: tension_target вне 0..1.": "ch.{0}: tension_target is outside 0..1.",
    "ch.{0}: tension_target не совпадает с tension_curve.":
        "ch.{0}: tension_target does not match tension_curve.",

    # ── state_patch
    "patch должен быть объектом.": "patch must be an object.",
    "chapter_summary: пусто.": "chapter_summary: empty.",
    "chapter_summary: слишком короткий ({0} слов, минимум 15).":
        "chapter_summary: too short ({0} words, minimum 15).",
    "chapter_summary: слишком длинный ({0} слов, максимум 150).":
        "chapter_summary: too long ({0} words, maximum 150).",
    "abilities_gained: должен быть массивом.": "abilities_gained: must be an array.",
    "WARN: abilities_gained: {0} новых способностей за главу — обычно не больше 2. Проверьте, не раздувается ли.":
        "WARN: abilities_gained: {0} new abilities in one chapter — usually no more than 2. Check that the story is not bloating.",
    "abilities_gained[{0}]: не объект.": "abilities_gained[{0}]: not an object.",
    "abilities_gained[{0}]: нет name.": "abilities_gained[{0}]: no name.",
    "abilities_gained[{0}]: нет description.": "abilities_gained[{0}]: no description.",
    "abilities_gained[{0}]: level должен быть 1.": "abilities_gained[{0}]: level must be 1.",
    "abilities_upgraded: должен быть массивом.": "abilities_upgraded: must be an array.",
    "WARN: abilities_upgraded: {0} повышений за главу — обычно не больше 1. Проверьте, не слишком ли быстро растёт сила.":
        "WARN: abilities_upgraded: {0} upgrades in one chapter — usually no more than 1. Check that power is not growing too fast.",
    "abilities_upgraded[{0}]: не объект.": "abilities_upgraded[{0}]: not an object.",
    "abilities_upgraded[{0}]: нет name.": "abilities_upgraded[{0}]: no name.",
    "abilities_upgraded[{0}]: new_level должен быть 2..5, получено {1}.":
        "abilities_upgraded[{0}]: new_level must be 2..5, got {1}.",
    "abilities_used: должен быть массивом.": "abilities_used: must be an array.",
    "events_created: элемент не объект.": "events_created: an item is not an object.",
    "events_created: участник {0} не из characters.": "events_created: the participant {0} is not in characters.",
    "events_created: пустое description.": "events_created: empty description.",
    "character_state_changes: элемент не объект.": "character_state_changes: an item is not an object.",
    "character_state_changes: {0} не из characters.": "character_state_changes: {0} is not in characters.",
    "character_state_changes: недопустимое field '{0}'.":
        "character_state_changes: invalid field '{0}'.",
    "character_state_changes[{0}]: delta {1} вне -30..30.":
        "character_state_changes[{0}]: delta {1} is outside -30..30.",
    "relationship_changes: элемент не объект.": "relationship_changes: an item is not an object.",
    "relationship_changes: недопустимое field '{0}'.":
        "relationship_changes: invalid field '{0}'.",
    "relationship_changes[{0}→{1}]: delta {2} вне -30..30.":
        "relationship_changes[{0}→{1}]: delta {2} is outside -30..30.",
    "knowledge_gained: элемент не объект.": "knowledge_gained: an item is not an object.",
    "knowledge_gained: {0} не из characters.": "knowledge_gained: {0} is not in characters.",
    "knowledge_gained: пустое fact.": "knowledge_gained: empty fact.",
    "secrets_revealed: элемент не объект.": "secrets_revealed: an item is not an object.",
    "secrets_revealed: {0} не из secrets.": "secrets_revealed: {0} is not in secrets.",
    "WARN: секрет {0} раскрыт в главе {1}, а по плану предвестники начинаются с главы {2}. Можно оставить — но проверьте, не портит ли это интригу.":
        "WARN: the secret {0} is revealed in chapter {1}, but per the outline its foreshadowing starts at chapter {2}. You can keep it — but check that it does not spoil the intrigue.",
    "secrets_revealed[{0}]: to_whom {1} неизвестен.": "secrets_revealed[{0}]: to_whom {1} is unknown.",
    "{0} должен быть массивом.": "{0} must be an array.",
    "{0}: у элемента нет id.": "{0}: an item has no id.",
}
