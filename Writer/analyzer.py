"""Извлечение state_patch из текста главы. Отдельный вызов LLM."""

import json
from pathlib import Path

import llm
from pipeline.json_utils import parse_json

PROMPTS = Path(__file__).parent / "prompts"


def _system_prompt() -> str:
    return (PROMPTS / "chapter_analyzer.txt").read_text(encoding="utf-8")


def _known_characters(bible: dict) -> list[dict]:
    chars = (bible.get("characters") or {}).get("characters") or []
    return [
        {"id": c.get("id"), "name": c.get("name")}
        for c in chars if isinstance(c, dict)
    ]


def _known_secrets(bible: dict) -> list[dict]:
    secrets = (bible.get("secrets") or {}).get("secrets") or []
    return [
        {"id": s.get("id"), "truth": s.get("truth")}
        for s in secrets if isinstance(s, dict)
    ]


def _known_locations(bible: dict) -> list[dict]:
    locs = (bible.get("geography") or {}).get("locations") or []
    return [
        {"id": l.get("id"), "name": l.get("name")}
        for l in locs if isinstance(l, dict)
    ]


def analyze(chapter_num: int, text: str, plan: dict,
            bible: dict) -> dict:
    payload = {
        "task": "chapter_analyzer",
        "input": {
            "chapter_num": chapter_num,
            "chapter_text": text,
            "chapter_plan": plan,
            "characters_known": _known_characters(bible),
            "secrets_known": _known_secrets(bible),
            "locations_known": _known_locations(bible),
        },
    }
    raw = llm.chat(
        [
            {"role": "system", "content": _system_prompt()},
            {"role": "user",
             "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ],
        stream=False,
        temperature=0.3,
        max_tokens=3000,
    )
    patch = parse_json(raw)

    # Гарантируем наличие всех секций
    for key in ("events_created", "character_state_changes",
                "relationship_changes", "knowledge_gained",
                "secrets_revealed", "new_locations", "new_institutions"):
        patch.setdefault(key, [])
    patch["chapter_num"] = chapter_num
    return patch

# ────────────────────────────────────────────────────────────────
# Sanitize: отбросить записи, которые не ложатся в нашу модель
# ────────────────────────────────────────────────────────────────

def sanitize_patch(patch: dict, bible: dict) -> tuple[dict, list[str]]:
    """Удаляет из патча записи, которые не применимы к нашей схеме.
    Возвращает (очищенный_патч, список_предупреждений)."""
    warnings: list[str] = []

    char_ids = {
        c.get("id") for c in (bible.get("characters") or {}).get("characters", [])
        if isinstance(c, dict) and c.get("id")
    }
    secret_ids = {
        s.get("id") for s in (bible.get("secrets") or {}).get("secrets", [])
        if isinstance(s, dict) and s.get("id")
    }
    existing_loc_ids = {
        l.get("id") for l in (bible.get("geography") or {}).get("locations", [])
        if isinstance(l, dict) and l.get("id")
    }
    existing_loc_names = {
        (l.get("name") or "").strip().lower()
        for l in (bible.get("geography") or {}).get("locations", [])
        if isinstance(l, dict)
    }
    existing_inst_ids = {
        i.get("id") for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict) and i.get("id")
    }
    existing_inst_names = {
        (i.get("name") or "").strip().lower()
        for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict)
    }

    # ── events_created: чистим participants
    clean_events = []
    for ev in patch.get("events_created") or []:
        if not isinstance(ev, dict):
            continue
        parts = [p for p in (ev.get("participants") or []) if p in char_ids]
        ev = dict(ev)
        ev["participants"] = parts
        clean_events.append(ev)
    patch["events_created"] = clean_events

    # ── character_state_changes: только известные персонажи
    clean_csc = []
    for c in patch.get("character_state_changes") or []:
        if not isinstance(c, dict):
            continue
        if c.get("char_id") in char_ids:
            clean_csc.append(c)
        else:
            warnings.append(f"отброшено изменение состояния: {c.get('char_id')} не персонаж")
    patch["character_state_changes"] = clean_csc

    # ── relationship_changes: только персонаж↔персонаж
    clean_rc = []
    for r in patch.get("relationship_changes") or []:
        if not isinstance(r, dict):
            continue
        a, b = r.get("from"), r.get("to")
        if a in char_ids and b in char_ids:
            clean_rc.append(r)
        else:
            warnings.append(
                f"отброшено отношение {a}↔{b}: отношения бывают только между персонажами"
            )
    patch["relationship_changes"] = clean_rc

    # ── knowledge_gained: только известные персонажи
    clean_kg = []
    for k in patch.get("knowledge_gained") or []:
        if not isinstance(k, dict):
            continue
        if k.get("char_id") in char_ids:
            clean_kg.append(k)
        else:
            warnings.append(f"отброшено знание для {k.get('char_id')}: неизвестный персонаж")
    patch["knowledge_gained"] = clean_kg

    # ── secrets_revealed: только известные секреты, только персонажи в to_whom
    clean_sr = []
    for s in patch.get("secrets_revealed") or []:
        if not isinstance(s, dict):
            continue
        sid = s.get("secret_id")
        if sid not in secret_ids:
            warnings.append(f"отброшено раскрытие секрета {sid}: неизвестный id")
            continue
        s = dict(s)
        s["to_whom"] = [x for x in (s.get("to_whom") or []) if x in char_ids]
        clean_sr.append(s)
    patch["secrets_revealed"] = clean_sr

    # ── new_locations: не допускать дубликатов по id и по имени
    clean_nl = []
    for l in patch.get("new_locations") or []:
        if not isinstance(l, dict):
            continue
        lid = l.get("id")
        lname = (l.get("name") or "").strip().lower()
        if lid in existing_loc_ids:
            warnings.append(f"отброшена локация {lid}: уже существует")
            continue
        if lname and lname in existing_loc_names:
            warnings.append(f"отброшена локация «{l.get('name')}»: дубликат по имени")
            continue
        clean_nl.append(l)
    patch["new_locations"] = clean_nl

    # ── new_institutions: аналогично
    clean_ni = []
    for i in patch.get("new_institutions") or []:
        if not isinstance(i, dict):
            continue
        iid = i.get("id")
        iname = (i.get("name") or "").strip().lower()
        if iid in existing_inst_ids:
            warnings.append(f"отброшена институция {iid}: уже существует")
            continue
        if iname and iname in existing_inst_names:
            warnings.append(f"отброшена институция «{i.get('name')}»: дубликат по имени")
            continue
        clean_ni.append(i)
    patch["new_institutions"] = clean_ni

    return patch, warnings