"""Сборка контекста для генерации одной главы. Программно, без LLM."""

from typing import Any


def _project_block(project: dict) -> dict:
    return {
        "theme":    project["theme"],
        "genre":    project["genre"],
        "setting":  project["setting"],
        "conflict": project["conflict"],
        "tone":     project.get("tone") or "",
    }


def _get_outline(bible: dict, num: int) -> dict | None:
    chapters = (bible.get("chapter_outline") or {}).get("chapters") or []
    for c in chapters:
        if isinstance(c, dict) and c.get("num") == num:
            return c
    return None


def _characters_by_ids(bible: dict, ids: list[str]) -> list[dict]:
    all_chars = (bible.get("characters") or {}).get("characters") or []
    wanted = set(ids or [])
    return [c for c in all_chars if c.get("id") in wanted]


def _relations_for(bible: dict, ids: list[str]) -> list[dict]:
    rels = (bible.get("relations") or {}).get("relations") or []
    wanted = set(ids or [])
    out = []
    for r in rels:
        if r.get("from") in wanted and r.get("to") in wanted:
            r2 = dict(r)
            r2["ambivalence"] = _ambivalence_notes(r)
            out.append(r2)
    return out


def _ambivalence_notes(rel: dict) -> list[str]:
    """Программно вычислить противоречия в чувствах.
    Модель тратит меньше внимания на анализ чисел."""
    trust = rel.get("trust") or 0
    symp  = rel.get("sympathy") or 0
    res   = rel.get("resentment") or 0
    attr  = rel.get("attraction") or 0

    notes = []
    if symp >= 50 and trust < 30:
        notes.append("симпатия высокая, доверие низкое — "
                     "тёплые жесты, холодные решения")
    if attr >= 50 and res >= 50:
        notes.append("притяжение и обида одновременно — "
                     "любовь-ненависть")
    if trust >= 50 and symp < 30:
        notes.append("доверяет, но не симпатизирует — "
                     "деловой тон без тепла")
    if trust < 30 and res >= 50:
        notes.append("не доверяет и обижен — "
                     "закрытость, короткие ответы")
    if attr >= 50 and trust < 30:
        notes.append("влечение без доверия — "
                     "сближение через конфликт")
    return notes


def _find_location(bible: dict, loc_id: str) -> dict | None:
    for l in (bible.get("geography") or {}).get("locations") or []:
        if l.get("id") == loc_id:
            return l
    return None


def _recent_events(bible: dict, num: int, limit: int = 10) -> list[dict]:
    """Последние N событий, которые уже произошли в каноне или истории.
    В 9.1 берём события из history + события, добавленные ранее
    сгенерированными главами (позже — из таблицы events)."""
    events = (bible.get("history") or {}).get("events") or []
    # Просто последние N по году
    events = sorted(
        [e for e in events if isinstance(e, dict) and isinstance(e.get("year"), int)],
        key=lambda e: e["year"],
    )
    return events[-limit:]


def _relevant_lore(bible: dict, threshold: float = 0.5) -> dict:
    rel = (bible.get("relevance_map") or {}).get("relevance") or {}
    institutions = (bible.get("institutions") or {}).get("institutions") or []
    locations = (bible.get("geography") or {}).get("locations") or []

    keep_inst = [
        i for i in institutions
        if rel.get(i.get("id"), 0) >= threshold
    ]
    keep_loc = [
        l for l in locations
        if rel.get(l.get("id"), 0) >= threshold
    ]
    return {
        "institutions": keep_inst,
        "locations": keep_loc,
    }


def _active_secrets(bible: dict, num: int) -> list[dict]:
    """Секреты, чей foreshadow_from ≤ num и reveal_at_chapter ≥ num."""
    ss = bible.get("story_structure") or {}
    schedule = {x.get("secret_id"): x for x in (ss.get("reveal_schedule") or [])}
    secrets = (bible.get("secrets") or {}).get("secrets") or []

    out = []
    for s in secrets:
        sid = s.get("id")
        sch = schedule.get(sid)
        if not sch:
            continue
        ff = sch.get("foreshadow_from", 1)
        rc = sch.get("reveal_at_chapter", 999)
        if ff <= num <= rc:
            out.append({
                "id": sid,
                "truth": s.get("truth"),
                "reveal_at_chapter": rc,
                "foreshadow_from": ff,
                "reveal_priority": s.get("reveal_priority"),
            })
    return out


def _prev_chapter_tail(bible: dict, num: int, max_chars: int = 2000) -> str:
    """Последние ~2000 знаков предыдущей главы, если она уже написана."""
    if num <= 1:
        return ""
    prev = _get_outline(bible, num - 1)
    if not prev:
        return ""
    # текст хранится в таблице chapters, а не в bible.
    # Здесь bible.timeline — но по-хорошему, надо смотреть БД.
    # Импорт внутри функции, чтобы не было цикла.
    import db
    with db.conn() as c:
        row = c.execute(
            "SELECT text FROM chapters WHERE num = ?", (num - 1,)
        ).fetchone()
    if not row or not row["text"]:
        return ""
    text = row["text"]
    return text[-max_chars:]


def build_context(project: dict, bible: dict, num: int,
                  word_target: int = 3000) -> dict:
    """Полный контекст для вызова LLM при генерации главы."""
    outline = _get_outline(bible, num)
    if outline is None:
        raise ValueError(f"Глава {num} не найдена в chapter_outline.")

    present_ids = outline.get("characters_present") or []
    present_chars = _characters_by_ids(bible, present_ids)
    rels = _relations_for(bible, present_ids)
    loc = _find_location(bible, outline.get("location"))

    return {
        "project":     _project_block(project),
        "chapter": {
            "num":         num,
            "title":       outline.get("title"),
            "pov":         outline.get("pov"),
            "act":         outline.get("act"),
            "purpose":     outline.get("purpose"),
            "location":    loc,
            "tension":     outline.get("tension_target"),
            "word_target": word_target,
        },
        "world_core":       bible.get("world_core") or {},
        "world_rules":      bible.get("world_rules") or {},
        "characters":       present_chars,
        "relations":        rels,
        "recent_events":    _recent_events(bible, num, limit=10),
        "relevant_lore":    _relevant_lore(bible, threshold=0.5),
        "active_secrets":   _active_secrets(bible, num),
        "prev_chapter_tail": _prev_chapter_tail(bible, num, max_chars=2000),
    }