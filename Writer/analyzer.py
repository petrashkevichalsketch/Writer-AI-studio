"""Извлечение state_patch из текста главы. Отдельный вызов LLM."""

import json
from pathlib import Path

import llm
import db
from pipeline.json_utils import parse_json

PROMPTS = Path(__file__).parent / "prompts"


def _system_prompt() -> str:
    return (PROMPTS / "chapter_analyzer.txt").read_text(encoding="utf-8")


def _known_characters(bible: dict) -> list[dict]:
    """Персонажи + их текущие способности (из БД, поле current_state_json).

    Важно: способности читаются из таблицы characters, а не из bible.
    Это даёт модели актуальный список — чтобы она могла отличить
    новую способность от развития существующей."""
    chars = (bible.get("characters") or {}).get("characters") or []

    with db.conn() as conn:
        rows = conn.execute(
            "SELECT id, current_state_json FROM characters"
        ).fetchall()
    state_by_id = {r["id"]: r["current_state_json"] for r in rows}

    result = []
    for ch in chars:
        if not isinstance(ch, dict):
            continue
        cid = ch.get("id")
        if not cid:
            continue

        abilities = []
        raw = state_by_id.get(cid)
        if raw:
            try:
                state = json.loads(raw)
                ab_map = state.get("abilities") or {}
                for name, data in ab_map.items():
                    if not isinstance(data, dict):
                        continue
                    abilities.append({
                        "name":        name,
                        "level":       data.get("level", 1),
                        "description": data.get("description", ""),
                    })
            except Exception:
                pass

        result.append({
            "id":                cid,
            "name":              ch.get("name"),
            "current_abilities": abilities,
        })
    return result


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
        # Патч главы включает summary до 150 слов + события + изменения —
        # 3000 токенов обрезали его на больших главах.
        max_tokens=6000,
    )
    patch = parse_json(raw)

    # Гарантируем наличие всех секций
    for key in ("events_created", "character_state_changes",
                "relationship_changes", "knowledge_gained",
                "secrets_revealed", "new_locations", "new_institutions",
                "abilities_gained", "abilities_upgraded", "abilities_used"):
        patch.setdefault(key, [])
    patch["chapter_num"] = chapter_num
    return patch


# ────────────────────────────────────────────────────────────────
# Sanitize: отбросить записи, которые не ложатся в нашу модель
# ────────────────────────────────────────────────────────────────

def _load_current_abilities() -> dict[str, dict]:
    """Возвращает {char_id: {ability_name: {...}}} из БД."""
    with db.conn() as conn:
        rows = conn.execute(
            "SELECT id, current_state_json FROM characters"
        ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        try:
            st = json.loads(r["current_state_json"] or "{}")
            out[r["id"]] = st.get("abilities") or {}
        except Exception:
            out[r["id"]] = {}
    return out


def _normalize(s: str) -> str:
    return (s or "").lower().replace("ё", "е").strip()


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

    # ── abilities_gained / abilities_upgraded
    current_abilities = _load_current_abilities()

    clean_ag: list[dict] = []
    auto_upgraded: list[dict] = []

    # Шаг 1. Разбор abilities_gained от модели:
    #  - если имя похоже на существующую способность → переводим в upgraded
    #  - если такой нет → оставляем как gained
    for ab in patch.get("abilities_gained") or []:
        if not isinstance(ab, dict):
            continue
        cid = ab.get("char_id")
        if cid not in char_ids:
            warnings.append(
                f"отброшена способность для {cid}: неизвестный персонаж"
            )
            continue

        name = (ab.get("name") or "").strip()
        if not name:
            warnings.append("отброшена способность без имени")
            continue

        existing = current_abilities.get(cid) or {}

        norm_new = _normalize(name)
        matched: str | None = None
        for ex_name in existing.keys():
            norm_ex = _normalize(ex_name)
            if norm_ex == norm_new:
                matched = ex_name
                break
            if len(norm_new) >= 4 and len(norm_ex) >= 4:
                if norm_new in norm_ex or norm_ex in norm_new:
                    matched = ex_name
                    break

        if matched:
            existing_level = int(existing[matched].get("level", 1) or 1)
            new_level = min(existing_level + 1, 5)
            if new_level < 2:
                new_level = 2
            auto_upgraded.append({
                "char_id":   cid,
                "name":      matched,
                "new_level": new_level,
                "reason":    f"новая формулировка «{name}» — развитие "
                             f"существующей «{matched}»",
            })
            warnings.append(
                f"«{name}» похожа на существующую «{matched}» у {cid} — "
                f"переведена в abilities_upgraded (level {existing_level} → {new_level})"
            )
            continue

        clean_ag.append(ab)

    # Шаг 2. Обработка abilities_upgraded (модель + авто).
    # Правила:
    #   - new_level < 2 → это первое появление, переводим в gained
    #   - new_level > 5 → обрезаем до 5
    #   - прыжок больше +1 от текущего → урезаем до текущий+1
    existing_ug = list(patch.get("abilities_upgraded") or [])
    existing_ug.extend(auto_upgraded)

    clean_ug: list[dict] = []
    for ab in existing_ug:
        if not isinstance(ab, dict):
            continue
        cid = ab.get("char_id")
        if cid not in char_ids:
            warnings.append(
                f"отброшен апгрейд для {cid}: неизвестный персонаж"
            )
            continue

        name = (ab.get("name") or "").strip()
        if not name:
            warnings.append("отброшен апгрейд без имени")
            continue

        nl = ab.get("new_level")

        # Апгрейд с уровнем < 2 — на самом деле новое появление
        if not isinstance(nl, int) or nl < 2:
            gained_item = {
                "char_id":     cid,
                "name":        name,
                "level":       1,
                "description": ab.get("reason") or ab.get("description") or name,
                "reason":      ab.get("reason") or "первое появление",
            }
            clean_ag.append(gained_item)
            warnings.append(
                f"апгрейд «{name}» у {cid} с new_level={nl} — "
                f"переведён в abilities_gained (level 1)"
            )
            continue

        # Верхняя граница
        if nl > 5:
            nl = 5

        # Ограничение скорости прокачки: не более +1 за главу
        current_lvl = 0
        current_abil = current_abilities.get(cid) or {}
        if name in current_abil:
            current_lvl = int(current_abil[name].get("level", 1) or 1)

        if current_lvl and nl > current_lvl + 1:
            warnings.append(
                f"апгрейд «{name}» у {cid} урезан с {nl} до {current_lvl + 1} "
                f"(не более +1 за главу)"
            )
            nl = current_lvl + 1

        ab = dict(ab)
        ab["new_level"] = nl
        clean_ug.append(ab)

    patch["abilities_gained"] = clean_ag
    patch["abilities_upgraded"] = clean_ug

    return patch, warnings