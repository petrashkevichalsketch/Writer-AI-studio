"""SQLite — source of truth. Все таблицы и минимальный CRUD."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, Optional

from config import DB_PATH, DEFAULTS


# ────────────────────────────────────────────────────────────────
# Подключение
# ────────────────────────────────────────────────────────────────

@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    """Контекст-менеджер: открывает соединение и ГАРАНТИРОВАННО
    закрывает его. Без этого на Windows файл БД остаётся залоченным."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ────────────────────────────────────────────────────────────────
# Схема
# ────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    theme          TEXT NOT NULL,
    genre          TEXT NOT NULL,
    setting        TEXT NOT NULL,
    conflict       TEXT NOT NULL,
    tone           TEXT,
    created_at     TEXT NOT NULL,
    autonomy_level TEXT NOT NULL DEFAULT 'supervised',
    book_format    TEXT NOT NULL DEFAULT 'novel'
);

CREATE TABLE IF NOT EXISTS world_bible (
    stage_name   TEXT PRIMARY KEY,
    content_json TEXT,
    validated    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    role_in_conflict    TEXT,
    side                TEXT,
    personal_stake      TEXT,
    contradiction       TEXT,
    goals_json          TEXT,
    secrets_json        TEXT,
    knowledge_json      TEXT,
    current_state_json  TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    from_char   TEXT NOT NULL,
    to_char     TEXT NOT NULL,
    type        TEXT,
    history     TEXT,
    tension     INTEGER DEFAULT 0,
    sympathy    INTEGER DEFAULT 0,
    trust       INTEGER DEFAULT 0,
    resentment  INTEGER DEFAULT 0,
    attraction  INTEGER DEFAULT 0,
    updated_at  TEXT,
    PRIMARY KEY (from_char, to_char)
);

CREATE TABLE IF NOT EXISTS locations (
    id                 TEXT PRIMARY KEY,
    name               TEXT,
    type               TEXT,
    population         TEXT,
    traits_json        TEXT,
    controlled_by_json TEXT,
    connected_to_json  TEXT
);

CREATE TABLE IF NOT EXISTS institutions (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    type            TEXT,
    public_role     TEXT,
    real_role       TEXT,
    resources_json  TEXT,
    weaknesses_json TEXT,
    goals_json      TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id                  TEXT PRIMARY KEY,
    chapter_num         INTEGER,
    type                TEXT,
    description         TEXT,
    participants_json   TEXT,
    causes_json         TEXT,
    consequences_json   TEXT,
    created_at          TEXT
);

CREATE TABLE IF NOT EXISTS secrets (
    id                    TEXT PRIMARY KEY,
    truth                 TEXT,
    known_by_json         TEXT,
    reveal_rules_json     TEXT,
    revealed_at_chapter   INTEGER
);

CREATE TABLE IF NOT EXISTS chapters (
    num         INTEGER PRIMARY KEY,
    title       TEXT,
    pov_char    TEXT,
    plan_json   TEXT,
    text        TEXT,
    status      TEXT DEFAULT 'draft',
    word_count  INTEGER DEFAULT 0,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS patches (
    chapter_num INTEGER PRIMARY KEY,
    patch_json  TEXT,
    applied_at  TEXT,
    accepted    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS canon_versions (
    chapter_num INTEGER PRIMARY KEY,
    canon_json  TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS style_seeds (
    id             TEXT PRIMARY KEY,
    pov_thread_id  TEXT,
    anchor_author  TEXT,
    exemplars_json TEXT,
    style_notes    TEXT,
    voice          TEXT
);

CREATE TABLE IF NOT EXISTS story_structure (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_json TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_state (
    stage_name  TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',
    started_at  TEXT,
    finished_at TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


ALL_TABLES = (
    "project", "world_bible", "characters", "relations",
    "locations", "institutions", "events", "secrets",
    "chapters", "patches", "canon_versions", "style_seeds",
    "story_structure", "pipeline_state", "settings",
)


def init() -> None:
    """Создать схему + дефолтные настройки + записи pipeline_state.
    Также накатывает миграции на существующие базы."""
    with conn() as c:
        c.executescript(SCHEMA)

        # ── Миграция: добавить book_format в project, если ещё нет
        cols = {r["name"] for r in c.execute("PRAGMA table_info(project)").fetchall()}
        if "book_format" not in cols:
            c.execute(
                "ALTER TABLE project ADD COLUMN book_format "
                "TEXT NOT NULL DEFAULT 'novel'"
            )

        # ── Миграция: добавить qa_json в chapters, если ещё нет
        cols_ch = {r["name"] for r in c.execute("PRAGMA table_info(chapters)").fetchall()}
        if "qa_json" not in cols_ch:
            c.execute("ALTER TABLE chapters ADD COLUMN qa_json TEXT")

        # ── Миграция: добавить summary в chapters, если ещё нет
        cols_ch = {r["name"] for r in c.execute("PRAGMA table_info(chapters)").fetchall()}
        if "summary" not in cols_ch:
            c.execute("ALTER TABLE chapters ADD COLUMN summary TEXT")

        from config import ALL_STAGES
        for k, v in DEFAULTS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (k, v),
            )
        for st in ALL_STAGES:
            c.execute(
                "INSERT OR IGNORE INTO pipeline_state(stage_name) VALUES (?)",
                (st,),
            )


# ────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────

def get_settings() -> dict:
    with conn() as c:
        rows = c.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def save_settings(data: dict) -> None:
    with conn() as c:
        for k, v in data.items():
            c.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str(v)),
            )


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


# ────────────────────────────────────────────────────────────────
# Project
# ────────────────────────────────────────────────────────────────

def create_project(theme: str, genre: str, setting: str,
                   conflict: str, tone: str,
                   autonomy: str = "supervised",
                   book_format: str = "novel") -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO project(theme, genre, setting, conflict, tone,
                                   created_at, autonomy_level, book_format)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (theme, genre, setting, conflict, tone, now(),
             autonomy, book_format),
        )
        return cur.lastrowid


def get_project() -> Optional[dict]:
    with conn() as c:
        row = c.execute("SELECT * FROM project ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


# ────────────────────────────────────────────────────────────────
# Pipeline state
# ────────────────────────────────────────────────────────────────

def set_stage(stage: str, status: str, error: Optional[str] = None) -> None:
    with conn() as c:
        c.execute(
            """UPDATE pipeline_state
                  SET status = ?,
                      error = ?,
                      started_at  = CASE WHEN ? = 'running' THEN ? ELSE started_at END,
                      finished_at = CASE WHEN ? IN ('done','failed','waiting_approval')
                                         THEN ? ELSE finished_at END
                WHERE stage_name = ?""",
            (status, error, status, now(), status, now(), stage),
        )


def get_pipeline() -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM pipeline_state").fetchall()
    return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────────
# world_bible
# ────────────────────────────────────────────────────────────────

def save_bible_stage(stage: str, content: Any, validated: bool = False) -> None:
    payload = json.dumps(content, ensure_ascii=False, indent=2)
    with conn() as c:
        c.execute(
            """INSERT INTO world_bible(stage_name, content_json, validated, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(stage_name) DO UPDATE SET
                   content_json = excluded.content_json,
                   validated    = excluded.validated,
                   created_at   = excluded.created_at""",
            (stage, payload, int(validated), now()),
        )


def get_bible_stage(stage: str) -> Optional[Any]:
    with conn() as c:
        row = c.execute(
            "SELECT content_json FROM world_bible WHERE stage_name = ?", (stage,)
        ).fetchone()
    return json.loads(row["content_json"]) if row and row["content_json"] else None


def get_full_bible() -> dict:
    with conn() as c:
        rows = c.execute("SELECT stage_name, content_json FROM world_bible").fetchall()
    return {
        r["stage_name"]: (json.loads(r["content_json"]) if r["content_json"] else None)
        for r in rows
    }


# ────────────────────────────────────────────────────────────────
# Reset
# ────────────────────────────────────────────────────────────────

# Таблицы, которые wipe НЕ трогает — пользовательские настройки.
PRESERVE_TABLES = ("settings",)


def wipe() -> None:
    """Полный сброс проекта: чистим всё, кроме settings.
    Файл book.db не удаляем — на Windows его может держать
    другая сессия SQLite."""
    tables = [t for t in ALL_TABLES if t not in PRESERVE_TABLES]
    with conn() as c:
        c.execute("PRAGMA foreign_keys = OFF")
        for t in tables:
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sqlite_sequence WHERE name='project'")
        c.execute("PRAGMA foreign_keys = ON")
    init()

# ────────────────────────────────────────────────────────────────
# Одиночный set_setting
# ────────────────────────────────────────────────────────────────

def set_setting(key: str, value: str) -> None:
    save_settings({key: value})


# ────────────────────────────────────────────────────────────────
# Reset отдельных стадий (каскад)
# ────────────────────────────────────────────────────────────────

def reset_stages(stages: list[str]) -> None:
    """Помечает список стадий как pending и удаляет их из world_bible."""
    with conn() as c:
        for s in stages:
            c.execute(
                "UPDATE pipeline_state "
                "SET status='pending', started_at=NULL, finished_at=NULL, error=NULL "
                "WHERE stage_name=?",
                (s,),
            )
            c.execute("DELETE FROM world_bible WHERE stage_name=?", (s,))

# ────────────────────────────────────────────────────────────────
# Chapters
# ────────────────────────────────────────────────────────────────

def get_chapter(num: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute("SELECT * FROM chapters WHERE num = ?", (num,)).fetchone()
    return dict(row) if row else None


def list_chapters() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT num, title, status, word_count, updated_at "
            "FROM chapters ORDER BY num"
        ).fetchall()
    return [dict(r) for r in rows]

# ────────────────────────────────────────────────────────────────
# Patches
# ────────────────────────────────────────────────────────────────

def save_patch(chapter_num: int, patch: dict, applied: bool = False) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO patches(chapter_num, patch_json, applied_at, accepted)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chapter_num) DO UPDATE SET
                   patch_json = excluded.patch_json,
                   applied_at = excluded.applied_at,
                   accepted   = excluded.accepted""",
            (chapter_num, json.dumps(patch, ensure_ascii=False),
             now() if applied else None, 1 if applied else 0),
        )


def get_patch(chapter_num: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(
            "SELECT * FROM patches WHERE chapter_num = ?", (chapter_num,)
        ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["patch"] = json.loads(out["patch_json"]) if out["patch_json"] else {}
    return out


# ────────────────────────────────────────────────────────────────
# Canon versions (снапшоты)
# ────────────────────────────────────────────────────────────────

def save_canon_snapshot(chapter_num: int, canon: dict) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO canon_versions(chapter_num, canon_json, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(chapter_num) DO UPDATE SET
                   canon_json = excluded.canon_json,
                   created_at = excluded.created_at""",
            (chapter_num, json.dumps(canon, ensure_ascii=False), now()),
        )


def get_canon_snapshot(chapter_num: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(
            "SELECT canon_json FROM canon_versions WHERE chapter_num = ?",
            (chapter_num,),
        ).fetchone()
    return json.loads(row["canon_json"]) if row and row["canon_json"] else None


def get_latest_canon_snapshot() -> tuple[Optional[int], Optional[dict]]:
    with conn() as c:
        row = c.execute(
            "SELECT chapter_num, canon_json FROM canon_versions "
            "ORDER BY chapter_num DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None, None
    return row["chapter_num"], json.loads(row["canon_json"])


def set_chapter_status(num: int, status: str) -> None:
    with conn() as c:
        c.execute(
            "UPDATE chapters SET status = ?, updated_at = ? WHERE num = ?",
            (status, now(), num),
        )

# ────────────────────────────────────────────────────────────────
# Пересказы глав
# ────────────────────────────────────────────────────────────────

def set_chapter_summary(num: int, summary: str) -> None:
    """Сохраняет краткий сюжетный пересказ главы."""
    with conn() as c:
        c.execute(
            "UPDATE chapters SET summary = ?, updated_at = ? WHERE num = ?",
            (summary, now(), num),
        )


def get_story_so_far(num: int) -> list[dict]:
    """Возвращает пересказы всех предыдущих глав (num < текущей),
    у которых есть summary. Отсортированы по номеру главы."""
    with conn() as c:
        rows = c.execute(
            """SELECT num, title, summary
                 FROM chapters
                WHERE num < ? AND summary IS NOT NULL AND summary != ''
                ORDER BY num""",
            (num,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_chapter_events(num: int) -> list[dict]:
    """События, порождённые конкретной главой."""
    with conn() as c:
        rows = c.execute(
            """SELECT id, type, description, participants_json,
                      causes_json, consequences_json
                 FROM events
                WHERE chapter_num = ?
                ORDER BY id""",
            (num,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_chapter_events(before_num: int, limit: int = 10) -> list[dict]:
    """Последние N событий из глав, написанных ДО указанной.
    Не включает события из истории мира (chapter_num IS NULL)."""
    with conn() as c:
        rows = c.execute(
            """SELECT id, chapter_num, type, description, participants_json
                 FROM events
                WHERE chapter_num IS NOT NULL AND chapter_num < ?
                ORDER BY chapter_num DESC, id DESC
                LIMIT ?""",
            (before_num, limit),
        ).fetchall()
    return [dict(r) for r in rows]