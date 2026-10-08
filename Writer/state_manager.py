"""Применение patch к канону, снапшоты, откат."""

import json
from typing import Any

import db


# ────────────────────────────────────────────────────────────────
# Снимок канона
# ────────────────────────────────────────────────────────────────

def snapshot_canon() -> dict:
    """Полный снимок изменяемых таблиц."""
    with db.conn() as c:
        chars = [dict(r) for r in c.execute("SELECT * FROM characters").fetchall()]
        rels = [dict(r) for r in c.execute("SELECT * FROM relations").fetchall()]
        events = [dict(r) for r in c.execute("SELECT * FROM events").fetchall()]
        locs = [dict(r) for r in c.execute("SELECT * FROM locations").fetchall()]
        insts = [dict(r) for r in c.execute("SELECT * FROM institutions").fetchall()]
        secrets = [dict(r) for r in c.execute("SELECT * FROM secrets").fetchall()]
    return {
        "characters":  chars,
        "relations":   rels,
        "events":      events,
        "locations":   locs,
        "institutions": insts,
        "secrets":     secrets,
    }


def init_canon_from_bible(bible: dict) -> None:
    """Первичная заливка канона из world_bible (после approve).
    Идемпотентно: чистит таблицы и заливает заново."""
    with db.conn() as c:
        for t in ("characters", "relations", "events", "locations",
                  "institutions", "secrets"):
            c.execute(f"DELETE FROM {t}")

        for ch in (bible.get("characters") or {}).get("characters", []) or []:
            c.execute(
                """INSERT INTO characters(id, name, role_in_conflict, side,
                        personal_stake, contradiction, goals_json, secrets_json,
                        knowledge_json, current_state_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ch.get("id"), ch.get("name"),
                    ch.get("role_in_conflict"), ch.get("side"),
                    ch.get("personal_stake"), ch.get("contradiction"),
                    json.dumps(ch.get("goals") or [], ensure_ascii=False),
                    json.dumps(ch.get("secrets") or [], ensure_ascii=False),
                    json.dumps(ch.get("knowledge") or [], ensure_ascii=False),
                    json.dumps({}, ensure_ascii=False),
                    db.now(),
                ),
            )

        for r in (bible.get("relations") or {}).get("relations", []) or []:
            c.execute(
                """INSERT INTO relations(from_char, to_char, type, history,
                        tension, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    r.get("from"), r.get("to"), r.get("type"),
                    r.get("history"), int(r.get("tension") or 0),
                    db.now(),
                ),
            )

        for ev in (bible.get("history") or {}).get("events", []) or []:
            c.execute(
                """INSERT INTO events(id, chapter_num, type, description,
                        participants_json, causes_json, consequences_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ev.get("id"), None, ev.get("type"), ev.get("description"),
                    json.dumps([], ensure_ascii=False),
                    json.dumps(ev.get("causes") or [], ensure_ascii=False),
                    json.dumps(ev.get("consequences") or [], ensure_ascii=False),
                    db.now(),
                ),
            )

        for l in (bible.get("geography") or {}).get("locations", []) or []:
            c.execute(
                """INSERT INTO locations(id, name, type, population, traits_json,
                        controlled_by_json, connected_to_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    l.get("id"), l.get("name"), l.get("type"),
                    str(l.get("population") or ""),
                    json.dumps(l.get("traits") or [], ensure_ascii=False),
                    json.dumps(l.get("controlled_by") or [], ensure_ascii=False),
                    json.dumps(l.get("connected_to") or [], ensure_ascii=False),
                ),
            )

        for i in (bible.get("institutions") or {}).get("institutions", []) or []:
            c.execute(
                """INSERT INTO institutions(id, name, type, public_role, real_role,
                        resources_json, weaknesses_json, goals_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    i.get("id"), i.get("name"), i.get("type"),
                    i.get("public_role"), i.get("real_role"),
                    json.dumps(i.get("resources") or [], ensure_ascii=False),
                    json.dumps(i.get("weaknesses") or [], ensure_ascii=False),
                    json.dumps(i.get("goals") or [], ensure_ascii=False),
                ),
            )

        for s in (bible.get("secrets") or {}).get("secrets", []) or []:
            c.execute(
                """INSERT INTO secrets(id, truth, known_by_json, reveal_rules_json,
                        revealed_at_chapter)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    s.get("id"), s.get("truth"),
                    json.dumps(s.get("known_by") or [], ensure_ascii=False),
                    json.dumps(s.get("reveal_rules") or {}, ensure_ascii=False),
                    None,
                ),
            )

    # Снапшот «до главы 1»
    db.save_canon_snapshot(0, snapshot_canon())


# ────────────────────────────────────────────────────────────────
# Применение патча
# ────────────────────────────────────────────────────────────────

def apply_patch(chapter_num: int, patch: dict) -> dict:
    """Применить патч к канону + сохранить снапшот + пометить главу analyzed."""
    stats = {"events": 0, "char_changes": 0, "rel_changes": 0,
             "knowledge": 0, "secrets": 0, "locations": 0, "institutions": 0}

    summary = (patch.get("chapter_summary") or "").strip()
    if summary:
        db.set_chapter_summary(chapter_num, summary)

    with db.conn() as c:
        # 1. События
        for ev in patch.get("events_created") or []:
            c.execute(
                """INSERT OR IGNORE INTO events
                       (id, chapter_num, type, description,
                        participants_json, causes_json, consequences_json, created_at)
                   VALUES (?, ?, ?, ?, ?, '[]', '[]', ?)""",
                (
                    ev.get("id"), chapter_num,
                    ev.get("type") or "chapter_event",
                    ev.get("description") or "",
                    json.dumps(ev.get("participants") or [], ensure_ascii=False),
                    db.now(),
                ),
            )
            stats["events"] += 1

        # 2. Изменения состояния персонажей → current_state_json
        for ch in patch.get("character_state_changes") or []:
            cid = ch.get("char_id")
            row = c.execute(
                "SELECT current_state_json FROM characters WHERE id = ?", (cid,)
            ).fetchone()
            if not row:
                continue
            try:
                state = json.loads(row["current_state_json"] or "{}")
            except Exception:
                state = {}
            state[ch["field"]] = state.get(ch["field"], 0) + int(ch["delta"])
            c.execute(
                "UPDATE characters SET current_state_json = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), cid),
            )
            stats["char_changes"] += 1

        # 3. Изменения отношений
        for r in patch.get("relationship_changes") or []:
            a, b, field, delta = r.get("from"), r.get("to"), r.get("field"), r.get("delta")
            if field not in ("trust", "sympathy", "resentment",
                             "attraction", "tension"):
                continue
            row = c.execute(
                "SELECT 1 FROM relations WHERE from_char=? AND to_char=?",
                (a, b),
            ).fetchone()
            if row:
                c.execute(
                    f"UPDATE relations SET {field} = {field} + ?, updated_at = ? "
                    "WHERE from_char=? AND to_char=?",
                    (int(delta), db.now(), a, b),
                )
            else:
                c.execute(
                    f"""INSERT INTO relations(from_char, to_char, {field}, updated_at)
                        VALUES (?, ?, ?, ?)""",
                    (a, b, int(delta), db.now()),
                )
            stats["rel_changes"] += 1

        # 4. Знание
        for k in patch.get("knowledge_gained") or []:
            cid = k.get("char_id")
            row = c.execute(
                "SELECT knowledge_json FROM characters WHERE id = ?", (cid,)
            ).fetchone()
            if not row:
                continue
            try:
                kn = json.loads(row["knowledge_json"] or "[]")
            except Exception:
                kn = []
            kn.append(k.get("fact") or "")
            c.execute(
                "UPDATE characters SET knowledge_json = ? WHERE id = ?",
                (json.dumps(kn, ensure_ascii=False), cid),
            )
            stats["knowledge"] += 1

        # 5. Секреты
        for s in patch.get("secrets_revealed") or []:
            c.execute(
                "UPDATE secrets SET revealed_at_chapter = ? WHERE id = ?",
                (chapter_num, s.get("secret_id")),
            )
            stats["secrets"] += 1

        # 6. Новые локации/институции (если пришли)
        for l in patch.get("new_locations") or []:
            c.execute(
                """INSERT OR IGNORE INTO locations(id, name, type, population,
                        traits_json, controlled_by_json, connected_to_json)
                   VALUES (?, ?, ?, ?, ?, '[]', '[]')""",
                (
                    l.get("id"), l.get("name") or "", l.get("type") or "",
                    str(l.get("population") or ""),
                    json.dumps(l.get("traits") or [], ensure_ascii=False),
                ),
            )
            stats["locations"] += 1

        for i in patch.get("new_institutions") or []:
            c.execute(
                """INSERT OR IGNORE INTO institutions(id, name, type,
                        public_role, real_role, resources_json,
                        weaknesses_json, goals_json)
                   VALUES (?, ?, ?, ?, ?, '[]', '[]', '[]')""",
                (
                    i.get("id"), i.get("name") or "", i.get("type") or "",
                    i.get("public_role") or "", i.get("real_role") or "",
                ),
            )
            stats["institutions"] += 1

    # Снапшот после применения
    db.save_canon_snapshot(chapter_num, snapshot_canon())
    db.set_chapter_status(chapter_num, "accepted")
    return stats


# ────────────────────────────────────────────────────────────────
# Откат
# ────────────────────────────────────────────────────────────────

def rollback_to(chapter_num: int) -> None:
    """Откатить канон к состоянию до главы chapter_num.
    Использует снапшот с номером chapter_num - 1."""
    target = chapter_num - 1
    snap = db.get_canon_snapshot(target)
    if snap is None:
        raise ValueError(f"Снапшот для главы {target} не найден.")

    with db.conn() as c:
        for t in ("characters", "relations", "events", "locations",
                  "institutions", "secrets"):
            c.execute(f"DELETE FROM {t}")

        for ch in snap.get("characters") or []:
            c.execute(
                """INSERT INTO characters(id, name, role_in_conflict, side,
                        personal_stake, contradiction, goals_json, secrets_json,
                        knowledge_json, current_state_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(ch.get(k) for k in (
                    "id", "name", "role_in_conflict", "side",
                    "personal_stake", "contradiction",
                    "goals_json", "secrets_json", "knowledge_json",
                    "current_state_json", "created_at",
                )),
            )
        for r in snap.get("relations") or []:
            c.execute(
                """INSERT INTO relations(from_char, to_char, type, history,
                        tension, sympathy, trust, resentment, attraction, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(r.get(k) for k in (
                    "from_char", "to_char", "type", "history",
                    "tension", "sympathy", "trust", "resentment",
                    "attraction", "updated_at",
                )),
            )
        for ev in snap.get("events") or []:
            c.execute(
                """INSERT INTO events(id, chapter_num, type, description,
                        participants_json, causes_json, consequences_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(ev.get(k) for k in (
                    "id", "chapter_num", "type", "description",
                    "participants_json", "causes_json",
                    "consequences_json", "created_at",
                )),
            )
        for l in snap.get("locations") or []:
            c.execute(
                """INSERT INTO locations(id, name, type, population, traits_json,
                        controlled_by_json, connected_to_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                tuple(l.get(k) for k in (
                    "id", "name", "type", "population",
                    "traits_json", "controlled_by_json", "connected_to_json",
                )),
            )
        for i in snap.get("institutions") or []:
            c.execute(
                """INSERT INTO institutions(id, name, type, public_role, real_role,
                        resources_json, weaknesses_json, goals_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(i.get(k) for k in (
                    "id", "name", "type", "public_role", "real_role",
                    "resources_json", "weaknesses_json", "goals_json",
                )),
            )
        for s in snap.get("secrets") or []:
            c.execute(
                """INSERT INTO secrets(id, truth, known_by_json, reveal_rules_json,
                        revealed_at_chapter)
                   VALUES (?, ?, ?, ?, ?)""",
                tuple(s.get(k) for k in (
                    "id", "truth", "known_by_json",
                    "reveal_rules_json", "revealed_at_chapter",
                )),
            )

    # Помечаем главу и последующие как stale
    with db.conn() as c:
        c.execute(
            "UPDATE chapters SET status = 'draft', updated_at = ? WHERE num = ?",
            (db.now(), chapter_num),
        )
        c.execute(
            "UPDATE chapters SET status = 'stale', updated_at = ? WHERE num > ?",
            (db.now(), chapter_num),
        )