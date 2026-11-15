"""Программные валидаторы стадий. Возвращают список строк-ошибок."""

import re
from typing import Any


# ────────────────────────────────────────────────────────────────
# WORLD_CORE
# ────────────────────────────────────────────────────────────────

def validate_world_core(payload: Any, project: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    cc = payload.get("central_concept") or {}
    if not isinstance(cc, dict) or not cc.get("name") or not cc.get("one_line"):
        e.append("central_concept.name/one_line пусты.")

    rules = payload.get("immutable_rules") or []
    if not isinstance(rules, list) or len(rules) < 2:
        e.append("immutable_rules: нужно ≥2.")
    else:
        for r in rules:
            if not isinstance(r, dict) or not r.get("statement"):
                e.append("immutable_rules: у правила нет statement.")
                break

    if not (payload.get("central_paradox") or "").strip():
        e.append("central_paradox пуст.")

    q = (payload.get("core_question") or "").strip()
    if not q:
        e.append("core_question пуст.")
    elif q.count("?") != 1 or not q.endswith("?"):
        e.append("core_question должен быть ровно одним вопросом (со знаком ? в конце).")

    tags = payload.get("tone_tags") or []
    if not isinstance(tags, list) or not tags:
        e.append("tone_tags: пусто.")

    return e


# ────────────────────────────────────────────────────────────────
# WORLD_RULES
# ────────────────────────────────────────────────────────────────

def validate_world_rules(payload: Any, core: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    tech = payload.get("technology") or {}
    if not isinstance(tech, dict):
        e.append("technology должен быть объектом.")
    else:
        for k in ("energy", "transport", "communication", "medicine", "weapons"):
            if not tech.get(k):
                e.append(f"technology.{k} пусто.")

    cons = payload.get("constraints") or []
    if not isinstance(cons, list) or len(cons) < 3:
        e.append("constraints: нужно ≥3.")
    else:
        for c in cons:
            if not isinstance(c, dict):
                e.append("constraints: элемент не объект.")
                break
            if not c.get("statement"):
                e.append("constraints: у ограничения нет statement.")
                break
            if not isinstance(c.get("implications"), list) or not c["implications"]:
                e.append("constraints: у ограничения пуст implications[].")
                break

    forbidden = payload.get("forbidden_techs") or []
    if not isinstance(forbidden, list) or not forbidden:
        e.append("forbidden_techs: пусто.")

    if not isinstance(core, dict) or not core.get("immutable_rules"):
        e.append("В ядре мира нет immutable_rules — не с чем сверять правила.")

    return e


# ────────────────────────────────────────────────────────────────
# HISTORY
# ────────────────────────────────────────────────────────────────

def validate_history(payload: Any) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект с полем events."]

    events = payload.get("events") or []
    if not isinstance(events, list):
        return ["events должен быть массивом."]

    n = len(events)
    if not (10 <= n <= 20):
        e.append(f"events: нужно 10–20, получено {n}.")

    ids: dict[str, dict] = {}
    for ev in events:
        if not isinstance(ev, dict):
            e.append("events: элемент не объект.")
            return e
        eid = ev.get("id")
        if not eid:
            e.append("events: у события нет id.")
            continue
        if eid in ids:
            e.append(f"events: дубликат id {eid}.")
        ids[eid] = ev

    for eid, ev in ids.items():
        for c in (ev.get("causes") or []):
            if c not in ids:
                e.append(f"{eid}: causes → несуществующий {c}.")
        for c in (ev.get("consequences") or []):
            if c not in ids:
                e.append(f"{eid}: consequences → несуществующий {c}.")

    for eid, ev in ids.items():
        y = ev.get("year")
        for c in (ev.get("causes") or []):
            cy = ids.get(c, {}).get("year")
            if isinstance(y, int) and isinstance(cy, int) and y < cy:
                e.append(f"{eid} (год {y}) не может быть РАНЬШЕ причины {c} (год {cy}).")

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {eid: WHITE for eid in ids}

    def dfs(node: str, stack: list[str]) -> bool:
        if color[node] == GRAY:
            e.append("Цикл в причинах: " + " → ".join(stack + [node]))
            return True
        if color[node] == BLACK:
            return False
        color[node] = GRAY
        for c in (ids[node].get("causes") or []):
            if c in ids and dfs(c, stack + [node]):
                return True
        color[node] = BLACK
        return False

    for eid in ids:
        if color[eid] == WHITE and dfs(eid, []):
            break

    if not any(len(ev.get("consequences") or []) >= 2 for ev in ids.values()):
        e.append("Нет точки бифуркации (события с ≥2 consequences).")

    return e


# ────────────────────────────────────────────────────────────────
# INSTITUTIONS
# ────────────────────────────────────────────────────────────────

ALLOWED_INST_TYPES = {
    "corporation", "government", "army", "religion",
    "crime_syndicate", "research_lab", "resistance_movement",
}


def validate_institutions(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    items = payload.get("institutions") or []
    if not isinstance(items, list):
        return ["institutions должен быть массивом."]

    n = len(items)
    if not (5 <= n <= 6):
        e.append(f"institutions: нужно 5–6, получено {n}.")

    seen_ids: set[str] = set()
    seen_types: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            e.append("institutions: элемент не объект.")
            continue
        iid = it.get("id")
        if not iid:
            e.append("institutions: у институции нет id.")
            continue
        if iid in seen_ids:
            e.append(f"institutions: дубликат id {iid}.")
        seen_ids.add(iid)

        t = it.get("type")
        if t not in ALLOWED_INST_TYPES:
            e.append(f"{iid}: недопустимый type '{t}'.")
        else:
            if t in seen_types:
                e.append(f"{iid}: тип '{t}' уже использован (дубликат типа).")
            seen_types.add(t)

        for k in ("name", "public_role", "real_role"):
            if not it.get(k):
                e.append(f"{iid}: поле {k} пусто.")
        if it.get("public_role") and it.get("real_role") \
                and it["public_role"].strip() == it["real_role"].strip():
            e.append(f"{iid}: public_role совпадает с real_role — нет двойного дна.")
        for k in ("resources", "weaknesses", "goals", "methods"):
            v = it.get(k) or []
            if not isinstance(v, list) or not v:
                e.append(f"{iid}: {k} пуст.")

    return e


# ────────────────────────────────────────────────────────────────
# GEOGRAPHY
# ────────────────────────────────────────────────────────────────

def validate_geography(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    items = payload.get("locations") or []
    if not isinstance(items, list):
        return ["locations должен быть массивом."]

    n = len(items)
    if not (5 <= n <= 8):
        e.append(f"locations: нужно 5–8, получено {n}.")

    inst_ids = {
        i.get("id") for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict)
    }

    loc_ids: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            e.append("locations: элемент не объект.")
            continue
        lid = it.get("id")
        if not lid:
            e.append("locations: у локации нет id.")
            continue
        if lid in loc_ids:
            e.append(f"locations: дубликат id {lid}.")
        loc_ids.add(lid)

        for k in ("name", "type"):
            if not it.get(k):
                e.append(f"{lid}: поле {k} пусто.")

        traits = it.get("traits") or []
        if not isinstance(traits, list) or not traits:
            e.append(f"{lid}: traits пуст.")

    empty_controlled = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        lid = it.get("id", "?")
        cb = it.get("controlled_by") or []
        if not cb:
            empty_controlled += 1
        for iid in cb:
            if inst_ids and iid not in inst_ids:
                e.append(f"{lid}.controlled_by → неизвестная институция {iid}.")

        ct = it.get("connected_to") or []
        if not isinstance(ct, list) or not ct:
            e.append(f"{lid}: connected_to пуст.")
            continue
        for link in ct:
            if not isinstance(link, dict):
                e.append(f"{lid}.connected_to: элемент не объект.")
                continue
            target = link.get("location")
            if target == lid:
                e.append(f"{lid}: ссылка на саму себя в connected_to.")
            elif target and target not in loc_ids:
                e.append(f"{lid}.connected_to → неизвестная локация {target}.")

    if empty_controlled > 2:
        e.append(f"controlled_by пусто у {empty_controlled} локаций (макс 2).")

    return e


# ────────────────────────────────────────────────────────────────
# ECONOMY
# ────────────────────────────────────────────────────────────────

def validate_economy(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    if not payload.get("currency"):
        e.append("currency пусто.")

    major = payload.get("major_resources") or []
    if not isinstance(major, list) or len(major) < 3:
        e.append("major_resources: нужно ≥3.")

    scarce = payload.get("scarce_resources") or []
    if not isinstance(scarce, list) or len(scarce) < 2:
        e.append("scarce_resources: нужно ≥2.")

    inst_ids = {
        i.get("id") for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict)
    }
    pc = payload.get("power_centers") or []
    if not isinstance(pc, list) or not pc:
        e.append("power_centers: пусто.")
    else:
        for iid in pc:
            if inst_ids and iid not in inst_ids:
                e.append(f"power_centers → неизвестная институция {iid}.")

    if not payload.get("wealth_distribution"):
        e.append("wealth_distribution пусто.")

    bm = payload.get("black_markets") or []
    if not isinstance(bm, list) or not bm:
        e.append("black_markets: пусто.")

    return e


# ────────────────────────────────────────────────────────────────
# Хелперы для SOCIETY / CULTURE
# ────────────────────────────────────────────────────────────────

def _nonempty_list(d: dict, key: str) -> bool:
    v = d.get(key)
    return isinstance(v, list) and len(v) > 0


def _nonempty_dict(d: dict, key: str) -> bool:
    v = d.get(key)
    return isinstance(v, dict) and len(v) > 0


# ────────────────────────────────────────────────────────────────
# SOCIETY
# ────────────────────────────────────────────────────────────────

def validate_society(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    s = payload.get("society")
    if not isinstance(s, dict):
        return ["society должен быть объектом."]

    for k in ("class_structure", "family_structure", "social_norms", "taboos",
              "status_symbols", "common_fears", "common_desires"):
        if not _nonempty_list(s, k):
            e.append(f"society.{k}: пусто.")

    for k in ("education", "work", "crime", "healthcare"):
        if not _nonempty_dict(s, k):
            e.append(f"society.{k}: пусто.")

    if not _nonempty_list(s, "entertainment"):
        e.append("society.entertainment: пусто.")

    core = bible.get("world_core") or {}
    paradox = (core.get("central_paradox") or "").lower()
    fears = " ".join(s.get("common_fears") or []).lower()
    if paradox and fears:
        words = [w for w in paradox.replace(",", " ").split() if len(w) > 5]
        if words and not any(w in fears for w in words):
            e.append(
                "WARN: common_fears слабо связаны с central_paradox — "
                "проверьте вручную на этапе APPROVE #1."
            )

    return e


# ────────────────────────────────────────────────────────────────
# CULTURE
# ────────────────────────────────────────────────────────────────

def validate_culture(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    c = payload.get("culture")
    if not isinstance(c, dict):
        return ["culture должен быть объектом."]

    for k in ("values", "religions", "philosophies", "art", "fashion",
              "language_changes", "customs", "holidays", "popular_myths"):
        if not _nonempty_list(c, k):
            e.append(f"culture.{k}: пусто.")

    holidays = c.get("holidays") or []
    if isinstance(holidays, list) and len(holidays) > 3:
        e.append(f"culture.holidays: максимум 3, получено {len(holidays)}.")

    myths = c.get("popular_myths") or []
    if isinstance(myths, list) and len(myths) < 3:
        e.append("culture.popular_myths: нужно ≥3.")

    return e


# ────────────────────────────────────────────────────────────────
# CONFLICTS
# ────────────────────────────────────────────────────────────────

def validate_conflicts(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    inst_ids = {
        i.get("id") for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict)
    }

    pc = payload.get("primary_conflict")
    if not isinstance(pc, dict):
        e.append("primary_conflict: отсутствует или не объект.")
    else:
        f = pc.get("factions") or []
        if not isinstance(f, list) or len(f) != 2:
            e.append("primary_conflict.factions: нужно ровно 2.")
        else:
            for iid in f:
                if inst_ids and iid not in inst_ids:
                    e.append(f"primary_conflict.factions → неизвестная {iid}.")
        for k in ("resource", "stakes", "irreconcilable_issue"):
            if not pc.get(k):
                e.append(f"primary_conflict.{k}: пусто.")

    sc = payload.get("secondary_conflicts") or []
    if not isinstance(sc, list) or not (2 <= len(sc) <= 4):
        e.append(f"secondary_conflicts: нужно 2–4, получено {len(sc) if isinstance(sc, list) else 0}.")
    else:
        for c in sc:
            if not isinstance(c, dict):
                continue
            cid = c.get("id", "?")
            for k in ("resource", "stakes"):
                if not c.get(k):
                    e.append(f"secondary_conflicts[{cid}].{k}: пусто.")
            for iid in (c.get("factions") or []):
                if inst_ids and iid not in inst_ids:
                    e.append(f"secondary_conflicts[{cid}] → неизвестная {iid}.")

    lc = payload.get("latent_conflicts") or []
    if not isinstance(lc, list) or len(lc) < 2:
        e.append("latent_conflicts: нужно ≥2.")
    else:
        for c in lc:
            if not isinstance(c, dict):
                continue
            cid = c.get("id", "?")
            if not c.get("description"):
                e.append(f"latent_conflicts[{cid}].description пуст.")
            ac = c.get("activation_conditions") or []
            if not isinstance(ac, list) or not ac:
                e.append(f"latent_conflicts[{cid}].activation_conditions пуст.")
            if c.get("visibility") != "hidden":
                e.append(f"latent_conflicts[{cid}].visibility должен быть 'hidden'.")

    return e


# ────────────────────────────────────────────────────────────────
# SECRETS
# ────────────────────────────────────────────────────────────────

def max_chapters() -> int:
    """Верхняя граница глав по формату книги проекта.
    Рассказ (1–3 главы) не должен пропускать секреты с earliest_chapter=15."""
    try:
        import db
        project = db.get_project() or {}
        from config import BOOK_FORMATS, DEFAULT_BOOK_FORMAT
        fmt = (BOOK_FORMATS.get(project.get("book_format") or "")
               or BOOK_FORMATS[DEFAULT_BOOK_FORMAT])
        return int(fmt["chapters_max"])
    except Exception:
        return 20


def sanitize_secrets(payload: Any, max_ch: int) -> None:
    """Мягкая нормализация secrets ПЕРЕД валидацией (мутирует payload).

    Модель не знает реального числа глав (в промпте историческое
    «1..20»), поэтому для коротких форматов earliest_chapter стабильно
    выходит за границу. Это безопасно чинить зажимом: earliest_chapter
    — лишь нижняя граница «с какого номера секрет МОЖНО раскрывать»,
    сдвиг вниз ему ничего не противоречит."""
    if not isinstance(payload, dict):
        return
    items = payload.get("secrets")
    if not isinstance(items, list):
        return
    for s in items:
        if not isinstance(s, dict):
            continue
        rules = s.get("reveal_rules")
        if not isinstance(rules, dict):
            continue
        ec = rules.get("earliest_chapter")
        if isinstance(ec, bool):
            continue
        if isinstance(ec, float) and ec.is_integer():
            ec = int(ec)
        if isinstance(ec, int) and not (1 <= ec <= max_ch):
            rules["earliest_chapter"] = min(max(1, ec), max_ch)


def validate_secrets(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    items = payload.get("secrets") or []
    if not isinstance(items, list):
        return ["secrets должен быть массивом."]

    n = len(items)
    if not (3 <= n <= 7):
        e.append(f"secrets: нужно 3–7, получено {n}.")

    max_ch = max_chapters()
    ids: set[str] = set()
    high_priority = 0
    for s in items:
        if not isinstance(s, dict):
            e.append("secrets: элемент не объект.")
            continue
        sid = s.get("id")
        if not sid:
            e.append("secrets: у секрета нет id.")
            continue
        if sid in ids:
            e.append(f"secrets: дубликат id {sid}.")
        ids.add(sid)

        if not s.get("truth"):
            e.append(f"{sid}.truth пуст.")

        rules = s.get("reveal_rules") or {}
        if not isinstance(rules, dict):
            e.append(f"{sid}.reveal_rules: не объект.")
        else:
            ec = rules.get("earliest_chapter")
            if not isinstance(ec, int) or not (1 <= ec <= max_ch):
                e.append(f"{sid}.reveal_rules.earliest_chapter "
                         f"должно быть 1..{max_ch}.")

        rp = s.get("reveal_priority")
        if not isinstance(rp, (int, float)) or not (0.0 <= rp <= 1.0):
            e.append(f"{sid}.reveal_priority должно быть числом 0..1.")
        elif rp > 0.8:
            high_priority += 1

    if high_priority < 1:
        e.append("Нужен хотя бы один секрет с reveal_priority > 0.8 (главная тайна).")

    return e


# ────────────────────────────────────────────────────────────────
# LORE_GRAPH
# ────────────────────────────────────────────────────────────────

def validate_lore_graph(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not nodes:
        e.append("nodes: пусто или не массив.")
    if not isinstance(edges, list):
        e.append("edges: не массив.")

    stats = payload.get("stats") or {}
    if not isinstance(stats, dict):
        e.append("stats: не объект.")

    return e


# ────────────────────────────────────────────────────────────────
# RELEVANCE_MAP
# ────────────────────────────────────────────────────────────────

def validate_relevance_map(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    rel = payload.get("relevance")
    if not isinstance(rel, dict) or not rel:
        e.append("relevance: пусто или не объект.")
        return e

    for k, v in rel.items():
        if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
            e.append(f"relevance[{k}] = {v!r} вне диапазона 0..1.")
            break

    return e


# ────────────────────────────────────────────────────────────────
# CONSISTENCY_AUDIT
# ────────────────────────────────────────────────────────────────

def validate_consistency_audit(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    problems = payload.get("problems")
    if not isinstance(problems, list):
        e.append("problems должен быть массивом.")
        return e

    for i, p in enumerate(problems):
        if not isinstance(p, dict):
            e.append(f"problems[{i}]: не объект.")
            continue
        sev = p.get("severity")
        if sev not in ("low", "medium", "high"):
            e.append(f"problems[{i}]: severity '{sev}' не из списка.")
        if not p.get("layer"):
            e.append(f"problems[{i}]: layer пусто.")
        if not p.get("description"):
            e.append(f"problems[{i}]: description пусто.")

    verdict = payload.get("overall_verdict")
    if verdict not in ("pass", "warn", "fail"):
        e.append("overall_verdict должен быть pass|warn|fail.")

    return e


# ────────────────────────────────────────────────────────────────
# CHARACTERS
# ────────────────────────────────────────────────────────────────

def validate_characters(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    items = payload.get("characters") or []
    if not isinstance(items, list):
        return ["characters должен быть массивом."]

    n = len(items)
    if not (3 <= n <= 7):
        e.append(f"characters: нужно 3–7, получено {n}.")

    conflicts = bible.get("conflicts") or {}
    primary = (conflicts.get("primary_conflict") or {}).get("factions") or []
    inst_ids = {
        i.get("id") for i in (bible.get("institutions") or {}).get("institutions", [])
        if isinstance(i, dict)
    }
    secret_ids = {
        s.get("id") for s in (bible.get("secrets") or {}).get("secrets", [])
        if isinstance(s, dict)
    }

    ids: set[str] = set()
    sides: set[str] = set()

    for c in items:
        if not isinstance(c, dict):
            e.append("characters: элемент не объект.")
            continue
        cid = c.get("id")
        if not cid:
            e.append("characters: у персонажа нет id.")
            continue
        if cid in ids:
            e.append(f"characters: дубликат id {cid}.")
        ids.add(cid)

        if not c.get("name"):
            e.append(f"{cid}.name пусто.")
        if not c.get("personal_stake"):
            e.append(f"{cid}.personal_stake пусто.")
        if not c.get("contradiction"):
            e.append(f"{cid}.contradiction пусто.")

        side = c.get("side")
        if side and side != "neutral":
            if inst_ids and side not in inst_ids:
                e.append(f"{cid}.side → неизвестная институция {side}.")
            else:
                sides.add(side)

        for sid in (c.get("secrets") or []):
            if secret_ids and sid not in secret_ids:
                e.append(f"{cid}.secrets → неизвестный секрет {sid}.")

        # initial_abilities
        init_ab = c.get("initial_abilities") or []
        if not isinstance(init_ab, list):
            e.append(f"{cid}.initial_abilities: должен быть массивом.")
        else:
            if len(init_ab) > 3:
                e.append(f"{cid}.initial_abilities: максимум 3, "
                         f"получено {len(init_ab)}.")
            for i, ab in enumerate(init_ab):
                if not isinstance(ab, dict):
                    e.append(f"{cid}.initial_abilities[{i}]: не объект.")
                    continue
                if not ab.get("name"):
                    e.append(f"{cid}.initial_abilities[{i}]: нет name.")
                if not ab.get("description"):
                    e.append(f"{cid}.initial_abilities[{i}]: нет description.")
                lv = ab.get("level", 1)
                if not isinstance(lv, int) or not (1 <= lv <= 3):
                    e.append(f"{cid}.initial_abilities[{i}]: "
                             f"level должен быть 1..3.")

    if len(sides) < 2 and len(items) >= 3:
        e.append("Персонажи занимают одну сторону — нужно ≥2 разных сторон "
                 "или хотя бы один neutral.")

    return e


# ────────────────────────────────────────────────────────────────
# RELATIONS
# ────────────────────────────────────────────────────────────────

ALLOWED_REL_TYPES = {
    "ally", "enemy", "family", "lover", "rival", "mentor", "stranger",
}


def validate_relations(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    rels = payload.get("relations") or []
    if not isinstance(rels, list):
        return ["relations должен быть массивом."]

    char_ids = {
        c.get("id") for c in (bible.get("characters") or {}).get("characters", [])
        if isinstance(c, dict)
    }

    seen_pairs: set[tuple] = set()
    degree: dict[str, int] = {cid: 0 for cid in char_ids}
    has_enemy = False
    has_ally = False

    for r in rels:
        if not isinstance(r, dict):
            e.append("relations: элемент не объект.")
            continue
        a, b = r.get("from"), r.get("to")
        if not a or not b:
            e.append("relations: отсутствует from/to.")
            continue
        if a == b:
            e.append(f"relations: {a} связан сам с собой.")
            continue
        if char_ids and (a not in char_ids or b not in char_ids):
            e.append(f"relations: неизвестный участник {a}→{b}.")
            continue

        pair = tuple(sorted([a, b]))
        if pair in seen_pairs:
            e.append(f"relations: дубликат пары {a}↔{b}.")
        seen_pairs.add(pair)

        t = r.get("type")
        if t not in ALLOWED_REL_TYPES:
            e.append(f"relations {a}→{b}: недопустимый type '{t}'.")
        elif t == "enemy":
            has_enemy = True
        elif t == "ally":
            has_ally = True

        tension = r.get("tension")
        if not isinstance(tension, int) or not (0 <= tension <= 100):
            e.append(f"relations {a}→{b}: tension должен быть 0..100.")

        if a in degree:
            degree[a] += 1
        if b in degree:
            degree[b] += 1

    for cid, d in degree.items():
        if d < 2:
            e.append(f"relations: у {cid} только {d} связей (нужно ≥2).")

    if not has_enemy:
        e.append("relations: нет ни одной связи enemy.")
    if not has_ally:
        e.append("relations: нет ни одной связи ally.")

    return e


# ────────────────────────────────────────────────────────────────
# STORY_STRUCTURE
# ────────────────────────────────────────────────────────────────

ALLOWED_STORY_BEATS = [
    "opening_image", "theme_stated", "setup", "catalyst", "debate",
    "break_into_two", "b_story", "fun_and_games", "midpoint",
    "bad_guys_close_in", "all_is_lost", "dark_night",
    "break_into_three", "finale", "final_image",
]

# Для коротких форматов (рассказ 1–3, повесть 4–8 глав) полный каркас
# из 15 битов физически не помещается: гэпы ≥2/≥3/≥3 требуют ≥9 глав.
# Короткая книга проходит на ядре из 5 битов.
CORE_STORY_BEATS = (
    "opening_image", "catalyst", "midpoint", "all_is_lost", "final_image",
)


def validate_story_structure(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    n = payload.get("total_chapters")
    if not isinstance(n, int) or not (1 <= n <= 50):
        e.append(f"total_chapters: нужно целое 1..50, получено {n!r}.")
        n = 18

    char_ids = {
        c.get("id") for c in (bible.get("characters") or {}).get("characters", [])
        if isinstance(c, dict)
    }
    secret_ids = {
        s.get("id") for s in (bible.get("secrets") or {}).get("secrets", [])
        if isinstance(s, dict)
    }

    # ─── story_beats: полный или сокращённый каркас ────────
    beats = payload.get("story_beats") or []
    if not isinstance(beats, list):
        e.append("story_beats: должен быть массивом.")
    else:
        keys_found = [b.get("key") for b in beats if isinstance(b, dict)]
        required = ALLOWED_STORY_BEATS if n >= 9 else CORE_STORY_BEATS
        missing = [k for k in required if k not in keys_found]
        extra = [k for k in keys_found if k not in ALLOWED_STORY_BEATS]
        duplicates = [k for k in set(keys_found) if keys_found.count(k) > 1]

        if missing:
            e.append(f"story_beats: отсутствуют обязательные биты: {missing}.")
        if extra:
            e.append(f"story_beats: неизвестные ключи: {extra}.")
        if duplicates:
            e.append(f"story_beats: дубликаты ключей: {duplicates}.")

        chapters_seq = [b.get("chapter") for b in beats
                        if isinstance(b, dict) and isinstance(b.get("chapter"), int)]
        if chapters_seq != sorted(chapters_seq):
            e.append("story_beats: главы должны идти в порядке возрастания.")

        for b in beats:
            if not isinstance(b, dict):
                continue
            c = b.get("chapter")
            if not isinstance(c, int) or not (1 <= c <= n):
                e.append(f"story_beats[{b.get('key')}]: chapter вне 1..{n}.")
            if not b.get("description"):
                e.append(f"story_beats[{b.get('key')}]: пустой description.")

        def ch_of(key: str):
            for b in beats:
                if isinstance(b, dict) and b.get("key") == key:
                    return b.get("chapter")
            return None

        if n >= 9:
            bit_two = ch_of("break_into_two")
            bit_mid = ch_of("midpoint")
            bit_lost = ch_of("all_is_lost")
            bit_final = ch_of("final_image")

            if all(isinstance(x, int) for x in (bit_two, bit_mid)):
                if bit_mid - bit_two < 2:
                    e.append("story_beats: между break_into_two и midpoint "
                             "должно быть минимум 2 главы.")
            if all(isinstance(x, int) for x in (bit_mid, bit_lost)):
                if bit_lost - bit_mid < 3:
                    e.append("story_beats: между midpoint и all_is_lost "
                             "должно быть минимум 3 главы.")
            if all(isinstance(x, int) for x in (bit_lost, bit_final)):
                if bit_final - bit_lost < 3:
                    e.append("story_beats: между all_is_lost и final_image "
                             "должно быть минимум 3 главы.")
        else:
            if ch_of("opening_image") != 1:
                e.append("story_beats: opening_image должен быть в главе 1.")
            if ch_of("final_image") != n:
                e.append(f"story_beats: final_image должен быть в главе {n}.")

    # ─── acts ────────────────────────────────────────────────
    acts = payload.get("acts") or []
    if not isinstance(acts, list) or not acts:
        e.append("acts: пусто.")
    else:
        seen_ch: set[int] = set()
        for a in acts:
            chs = a.get("chapters") or []
            for x in chs:
                if not isinstance(x, int) or not (1 <= x <= n):
                    e.append(f"acts: глава {x} вне 1..{n}.")
                elif x in seen_ch:
                    e.append(f"acts: глава {x} встречается дважды.")
                else:
                    seen_ch.add(x)
        if len(seen_ch) != n:
            e.append(f"acts: покрыто {len(seen_ch)} глав из {n}.")

    # ─── pov_threads ─────────────────────────────────────────
    povs = payload.get("pov_threads") or []
    if not isinstance(povs, list) or not povs:
        e.append("pov_threads: пусто.")
    else:
        covered: set[int] = set()
        for t in povs:
            c = t.get("character")
            if char_ids and c not in char_ids:
                e.append(f"pov_threads: неизвестный персонаж {c}.")
            for x in (t.get("chapters") or []):
                if x in covered:
                    e.append(f"pov_threads: глава {x} назначена двум нитям.")
                covered.add(x)
        missing = set(range(1, n + 1)) - covered
        if missing:
            e.append(f"pov_threads: не покрыты главы {sorted(missing)}.")

    # ─── character_arcs ──────────────────────────────────────
    arcs = payload.get("character_arcs") or []
    if not isinstance(arcs, list) or not arcs:
        e.append("character_arcs: пусто.")
    else:
        for a in arcs:
            c = a.get("char")
            if char_ids and c not in char_ids:
                e.append(f"character_arcs: неизвестный персонаж {c}.")

    # ─── reveal_schedule ─────────────────────────────────────
    rs = payload.get("reveal_schedule") or []
    if not isinstance(rs, list):
        e.append("reveal_schedule: не массив.")
    else:
        sched_secrets = {x.get("secret_id") for x in rs if isinstance(x, dict)}
        for sid in secret_ids:
            if sid not in sched_secrets:
                e.append(f"reveal_schedule: секрет {sid} не запланирован.")
        for x in rs:
            if not isinstance(x, dict):
                continue
            rc = x.get("reveal_at_chapter")
            ff = x.get("foreshadow_from")
            if not isinstance(rc, int) or not (1 <= rc <= n):
                e.append(f"reveal_schedule[{x.get('secret_id')}]: "
                         f"reveal_at_chapter вне 1..{n}.")
            if isinstance(rc, int) and isinstance(ff, int) and ff >= rc:
                e.append(f"reveal_schedule[{x.get('secret_id')}]: "
                         f"foreshadow_from ≥ reveal_at_chapter.")

    # ─── tension_curve ───────────────────────────────────────
    tc = payload.get("tension_curve") or []
    if not isinstance(tc, list) or len(tc) != n:
        e.append(f"tension_curve: длина {len(tc) if isinstance(tc, list) else '?'}, "
                 f"ожидается {n}.")
    else:
        for v in tc:
            if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
                e.append("tension_curve: значения должны быть 0..1.")
                break

    # ─── RPG (ЛитРПГ / РеалРПГ): жанровая механика ───────────
    if payload.get("rpg_mode"):
        e.extend(_validate_rpg_structure(payload, n))

    return e


# ────────────────────────────────────────────────────────────────
# CHAPTER_OUTLINE
# ────────────────────────────────────────────────────────────────

# Сообщение для плана, целиком сгенерированного в старом формате (v1:
# биты — строки). Показывается ОДНОЙ строкой вместо лавины ошибок
# «beats[i]: должен быть объектом» на каждый бит каждой главы.
LEGACY_OUTLINE_MSG = (
    "chapter_outline: план в старом формате (beats — строки). "
    "Перегенерируйте стадию — локально или сильной моделью: формат v2 "
    "требует в каждой главе ровно 5 объектов-сцен "
    "(scene, word_target, action_chain, result)."
)


def _is_legacy_beats(beats: Any) -> bool:
    """Биты старого формата: непустой список строк."""
    return (isinstance(beats, list) and bool(beats)
            and all(isinstance(b, str) for b in beats))


def sanitize_chapter_outline(payload: Any, bible: dict | None = None) -> None:
    """Мягкая нормализация плана глав ПЕРЕД валидацией (мутирует payload).

    word_target сцены — мягкий план для писчего промпта, а не
    художественный факт. Модель распределяет объём «по
    драматургической значимости» и промахивается мимо word_target
    главы; на рассказе (цель 2500) окно ±5% допускает единственную
    сумму из круглых сотен, поэтому план стабильно ловит отказ.
    Чинится переносом разницы в крупнейшую сцену.

    С bible также чинится главная путаница модели: имена вместо
    технических id в полях-ссылках. «Москва» → LOC3, «Виктор» → CH1,
    pov «POV1» → персонаж этой нити (особенно часто на РеалРПГ в
    реальном мире и ЛитРПГ с игровым миром-локацией). Ретрай на такую
    мелочь тратить нельзя — чинится молча, ошибки валидации остаются
    только на действительно чужие id."""
    if not isinstance(payload, dict):
        return
    chs = payload.get("chapters")
    if not isinstance(chs, list):
        return

    # ── имена → id (по bible): локации, персонажи, pov-нити ──
    if bible:
        def _id_map(items: Any) -> dict[str, str]:
            out: dict[str, str] = {}
            for it in items or []:
                if (isinstance(it, dict) and isinstance(it.get("id"), str)
                        and it["id"].strip()):
                    out.setdefault(it["id"].strip().lower(), it["id"])
                    nm = it.get("name")
                    if isinstance(nm, str) and nm.strip():
                        out.setdefault(nm.strip().lower(), it["id"])
            return out

        loc_map = _id_map((bible.get("geography") or {}).get("locations"))
        char_map = _id_map((bible.get("characters") or {}).get("characters"))
        pov_map = {
            th["id"].strip().lower(): th["character"]
            for th in ((bible.get("story_structure") or {})
                       .get("pov_threads") or [])
            if (isinstance(th, dict) and isinstance(th.get("id"), str)
                and th.get("character"))
        }
        # RPG: refs и цели кривых — вычисляемые данные (lookup по
        # ledger/ladder/кривым), а не творчество. Модель их «придумывает»
        # и теряет ретрай на том, что считается одной строкой кода —
        # перезаписываем вычисленной правдой (idempotent, корректные
        # значения не меняются).
        ss = bible.get("story_structure") or {}
        rpg_refs: dict = {}
        rpg_curves: dict = {}
        if ss.get("rpg_mode"):
            ledger_by_ch: dict = {}
            for g in ss.get("progression_ledger") or []:
                if (isinstance(g, dict) and isinstance(g.get("chapter"), int)
                        and isinstance(g.get("id"), str)):
                    ledger_by_ch.setdefault(g["chapter"], []).append(g["id"])
            ladder_by_ch: dict = {}
            for t in ss.get("enemy_ladder") or []:
                if isinstance(t, dict) and isinstance(t.get("id"), str):
                    for cnum in t.get("chapters") or []:
                        if isinstance(cnum, int):
                            ladder_by_ch.setdefault(cnum, []).append(t["id"])
            rpg_refs = {"progression_refs": ledger_by_ch,
                        "enemy_refs": ladder_by_ch}
            rpg_curves = {"tension_target": ss.get("tension_curve"),
                          "power_target": ss.get("power_curve"),
                          "threat_target": ss.get("threat_curve")}

        for c in chs:
            if not isinstance(c, dict):
                continue
            loc = c.get("location")
            if isinstance(loc, str) and loc.strip().lower() in loc_map:
                c["location"] = loc_map[loc.strip().lower()]
            pov = c.get("pov")
            if isinstance(pov, str):
                key = pov.strip().lower()
                if key in pov_map:
                    c["pov"] = pov_map[key]
                elif key in char_map:
                    c["pov"] = char_map[key]
            present = c.get("characters_present")
            if isinstance(present, list):
                c["characters_present"] = [
                    char_map.get(str(x).strip().lower(), x) for x in present
                ]
            num = c.get("num")
            if not isinstance(num, int):
                continue
            for field, by_ch in rpg_refs.items():
                c[field] = sorted(set(by_ch.get(num, [])))
            for field, cur in rpg_curves.items():
                if (isinstance(cur, list) and 1 <= num <= len(cur)
                        and isinstance(cur[num - 1], (int, float))):
                    c[field] = cur[num - 1]

    for c in chs:
        if not isinstance(c, dict):
            continue
        # 500.0 → 500: валидатор требует int
        wt = c.get("word_target")
        if isinstance(wt, float) and wt.is_integer():
            c["word_target"] = int(wt)
        beats = c.get("beats")
        if not isinstance(beats, list) or not beats:
            continue
        for b in beats:
            if isinstance(b, dict):
                bw = b.get("word_target")
                if isinstance(bw, float) and bw.is_integer():
                    b["word_target"] = int(bw)
        ch_wt = c.get("word_target")
        if not isinstance(ch_wt, int) or ch_wt <= 0:
            continue
        # правим сумму только при полностью корректных сценах —
        # структурные проблемы отдаём валидатору как есть
        if not all(isinstance(b, dict)
                   and isinstance(b.get("word_target"), int)
                   and b["word_target"] > 0
                   for b in beats):
            continue
        diff = ch_wt - sum(b["word_target"] for b in beats)
        if diff == 0:
            continue
        # разница делится поровну между сценами, остаток берёт
        # крупнейшая — раскладка остаётся «драматургичной»
        base, rem = divmod(diff, len(beats))
        for b in beats:
            b["word_target"] += base
        big = max(beats, key=lambda b: b["word_target"])
        big["word_target"] += rem
        # страховка: равное деление не должно убить мелкую сцену
        if any(b["word_target"] <= 0 for b in beats):
            for b in beats:
                b["word_target"] -= base
            big["word_target"] = max(1, big["word_target"] + diff)


def validate_chapter_outline(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    chs = payload.get("chapters") or []
    if not isinstance(chs, list):
        return ["chapters должен быть массивом."]

    # План целиком в старом формате — одна понятная ошибка, без деталей.
    dict_chs = [c for c in chs if isinstance(c, dict)]
    if dict_chs and all(_is_legacy_beats(c.get("beats")) for c in dict_chs):
        return [LEGACY_OUTLINE_MSG]

    ss = bible.get("story_structure") or {}
    total_n = ss.get("total_chapters") or len(chs)
    tc = ss.get("tension_curve") or []

    char_ids = {c.get("id") for c in
                (bible.get("characters") or {}).get("characters", [])
                if isinstance(c, dict)}
    loc_ids = {l.get("id") for l in
               (bible.get("geography") or {}).get("locations", [])
               if isinstance(l, dict)}
    event_ids = {ev.get("id") for ev in
                 (bible.get("history") or {}).get("events", [])
                 if isinstance(ev, dict)}
    secret_ids = {s.get("id") for s in
                  (bible.get("secrets") or {}).get("secrets", [])
                  if isinstance(s, dict)}

    if len(chs) != total_n:
        e.append(f"chapters: {len(chs)} глав, ожидалось {total_n}.")

    nums = sorted(c.get("num") for c in chs if isinstance(c, dict))
    if nums != list(range(1, total_n + 1)):
        e.append("chapters: num должны идти 1..N без пропусков.")

    for c in chs:
        if not isinstance(c, dict):
            continue
        cid = c.get("num", "?")

        pov = c.get("pov")
        if char_ids and pov not in char_ids:
            e.append(f"ch.{cid}: pov {pov} не из characters.")

        loc = c.get("location")
        if loc_ids and loc not in loc_ids:
            e.append(f"ch.{cid}: location {loc} не из geography.")

        for x in (c.get("characters_present") or []):
            if char_ids and x not in char_ids:
                e.append(f"ch.{cid}: characters_present → {x} не существует.")

        for x in (c.get("events") or []):
            if event_ids and x not in event_ids:
                e.append(f"ch.{cid}: events → {x} не из history.")

        for x in (c.get("secrets_touched") or []):
            if secret_ids and x not in secret_ids:
                e.append(f"ch.{cid}: secrets_touched → {x} не из secrets.")

        if not c.get("purpose"):
            e.append(f"ch.{cid}: purpose пусто.")

        # ── проверка word_target главы ─────────────────────
        ch_wt = c.get("word_target")
        if not isinstance(ch_wt, int) or ch_wt < 500:
            e.append(f"ch.{cid}: word_target главы должен быть целым ≥ 500.")

        # ── проверка beats ──────────────────────────────────
        beats = c.get("beats")
        if not isinstance(beats, list):
            e.append(f"ch.{cid}: beats должен быть массивом.")
        elif _is_legacy_beats(beats):
            # Смешанный формат: эта глава в старом формате, остальные —
            # в новом. Одна ошибка на главу вместо россыпи.
            e.append(f"ch.{cid}: beats в старом формате (строки) — нужны "
                     f"объекты-сцены v2 (scene, word_target, action_chain, "
                     f"result). Перегенерируйте главу.")
        elif len(beats) != 5:
            e.append(f"ch.{cid}: beats — ровно 5 сцен, получено {len(beats)}.")
        else:
            scene_nums: list = []
            sum_wt = 0
            for i, b in enumerate(beats):
                if not isinstance(b, dict):
                    e.append(f"ch.{cid}.beats[{i}]: должен быть объектом.")
                    continue

                sn = b.get("scene")
                scene_nums.append(sn)
                if not isinstance(sn, int) or not (1 <= sn <= 5):
                    e.append(f"ch.{cid}.beats[{i}].scene должно быть 1..5.")

                wt = b.get("word_target")
                if not isinstance(wt, int) or wt <= 0:
                    e.append(f"ch.{cid}.beats[{i}].word_target: целое > 0.")
                else:
                    sum_wt += wt

                ac = b.get("action_chain")
                if not isinstance(ac, list):
                    e.append(f"ch.{cid}.beats[{i}].action_chain: не массив.")
                elif not (4 <= len(ac) <= 6):
                    e.append(f"ch.{cid}.beats[{i}].action_chain: "
                             f"4–6 микрособытий, получено {len(ac)}.")
                else:
                    for j, item in enumerate(ac):
                        if not isinstance(item, str) or not item.strip():
                            e.append(f"ch.{cid}.beats[{i}].action_chain[{j}]: пусто.")

                res = b.get("result")
                if not isinstance(res, str) or not res.strip():
                    e.append(f"ch.{cid}.beats[{i}].result: пусто.")

            if scene_nums != [1, 2, 3, 4, 5]:
                e.append(f"ch.{cid}: сцены должны идти 1..5 по порядку.")

            if isinstance(ch_wt, int) and sum_wt > 0:
                if abs(sum_wt - ch_wt) / ch_wt > 0.12:
                    e.append(f"ch.{cid}: сумма word_target сцен ({sum_wt}) "
                             f"отклоняется от word_target главы ({ch_wt}) "
                             f"более чем на 12%.")

        # ── tension_target ─────────────────────────────────
        tt = c.get("tension_target")
        if not isinstance(tt, (int, float)) or not (0.0 <= tt <= 1.0):
            e.append(f"ch.{cid}: tension_target вне 0..1.")
        elif tc and c.get("num") and 1 <= c["num"] <= len(tc):
            if abs(tt - tc[c["num"] - 1]) > 0.01:
                e.append(f"ch.{cid}: tension_target не совпадает с tension_curve.")

    # ─── RPG (ЛитРПГ / РеалРПГ): жанровая механика ───────────
    ss_struct = (bible or {}).get("story_structure") or {}
    if ss_struct.get("rpg_mode"):
        e.extend(_validate_rpg_outline(payload, ss_struct))

    return e


# ────────────────────────────────────────────────────────────────
# RPG (ЛитРПГ / РеалРПГ)
# ────────────────────────────────────────────────────────────────
# Жанровые проверки поверх базового скелета. Запускаются только для
# payload с rpg_mode (story_structure) и проектов, чья принятая
# story_structure содержит rpg_mode (chapter_outline); обычные жанры
# проходят только старые проверки. Базовые проверки не дублируются.

RPG_MODES = ("litrpg", "realrpg")

RPG_SOURCES = ("гринд", "тренер", "лут", "контракт", "покупка",
               "инсайт", "перекомбинация")

RPG_ROLES = ("добыча", "тест", "бой", "расплата", "быт", "разбор")

# Цена, целиком сводящаяся к восполнимому за кадром ресурсу, ставок
# не создаёт: «потратил ману» — не цена
RPG_RENEWABLE_WORDS = {
    "мана", "маны", "ману", "выносливость", "выносливости",
    "энергия", "энергии", "стамина", "стамины",
}

_RPG_REF_RE = re.compile(r"\[(G\d{2}|E\d+|R\d{2})\]")


def _rpg_norm(s: Any) -> str:
    """Нижний регистр без пунктуации — для сравнений и стоп-слов."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"[^\wа-яё\s-]+", " ", s.lower(), flags=re.UNICODE).strip()


def _rpg_cost_renewable(cost: Any) -> bool:
    """True, если цена целиком состоит из восполнимых ресурсов."""
    words = {w for w in _rpg_norm(cost).split() if w}
    return bool(words) and words <= RPG_RENEWABLE_WORDS


def _rpg_bit_chapters(beats: Any) -> dict:
    """key бита → номер главы (только валидные int)."""
    out = {}
    if isinstance(beats, list):
        for b in beats:
            if (isinstance(b, dict) and isinstance(b.get("key"), str)
                    and isinstance(b.get("chapter"), int)):
                out[b["key"]] = b["chapter"]
    return out


def _rpg_superiority_window(bit_ch: dict) -> tuple[int | None, int | None]:
    """Окно превосходства (от..до включительно): дуга ложной победы от
    бита fun_and_games до midpoint. Герой блистает весь отрезок
    «жанрового обещания», а не одну главу — одиночные окна делали
    кривую ломаной и провоцировали отказы валидатора."""
    fg = bit_ch.get("fun_and_games")
    mid = bit_ch.get("midpoint")
    if fg is not None and mid is not None:
        return fg, mid
    if fg is not None:
        return fg, fg
    if mid is not None:
        return mid, mid
    return None, None


def sanitize_story_structure(payload: Any) -> None:
    """Зажим кривых силы/угрозы ПЕРЕД валидацией (мутирует payload).

    Арифметический промах модели не должен стоить ретрая — та же
    философия, что word_target в плане глав: threat поднимается до
    power вне окна превосходства и до power + 0.25 на all_is_lost.
    Монотонность power и позицию просадки не трогаем — это
    драматургия, её модель правит по prev_errors. Для не-RPG payload
    — no-op."""
    if not isinstance(payload, dict) or not payload.get("rpg_mode"):
        return
    n = payload.get("total_chapters")
    if not isinstance(n, int):
        return
    pc = payload.get("power_curve")
    thc = payload.get("threat_curve")
    if (not isinstance(pc, list) or not isinstance(thc, list)
            or len(pc) != n or len(thc) != n):
        return
    if not (all(isinstance(v, (int, float)) for v in pc)
            and all(isinstance(v, (int, float)) for v in thc)):
        return
    bit_ch = _rpg_bit_chapters(payload.get("story_beats"))
    w_lo, w_hi = _rpg_superiority_window(bit_ch)
    fin = bit_ch.get("finale")
    lost = bit_ch.get("all_is_lost")

    limit = fin if fin is not None else n
    for i in range(min(limit, n)):
        if w_lo is not None and w_lo <= i + 1 <= w_hi:
            continue
        if thc[i] < pc[i]:
            thc[i] = pc[i]
    if lost is not None and 1 <= lost <= n:
        if thc[lost - 1] - pc[lost - 1] < 0.25:
            thc[lost - 1] = min(1.0, pc[lost - 1] + 0.25)


def _validate_rpg_structure(payload: dict, n: int) -> list[str]:
    """Жанровые поля story_structure: гроссбух прокачки, лестница
    врагов, правила системы, билд-арка, кривые силы и угрозы."""
    e: list[str] = []
    short = n < 9  # сокращённый каркас

    if payload.get("rpg_mode") not in RPG_MODES:
        e.append(f"rpg_mode: должен быть {' или '.join(RPG_MODES)}, "
                 f"получено {payload.get('rpg_mode')!r}.")

    bit_ch = _rpg_bit_chapters(payload.get("story_beats"))

    # ─── system_rules ────────────────────────────────────────
    rules = payload.get("system_rules") or []
    if not isinstance(rules, list) or len(rules) < 3:
        e.append(f"system_rules: минимум 3 записи, получено "
                 f"{len(rules) if isinstance(rules, list) else '?'}.")
    else:
        rule_ids: list = []
        exceptions = 0
        setup_ch = bit_ch.get("setup")
        for i, r in enumerate(rules):
            if not isinstance(r, dict):
                e.append(f"system_rules[{i}]: должен быть объектом.")
                continue
            rid = r.get("id")
            rule_ids.append(rid)
            if not isinstance(rid, str) or not re.fullmatch(r"R\d{2}", rid):
                e.append(f"system_rules[{i}]: id должен быть вида R01.")
            if not r.get("rule"):
                e.append(f"system_rules[{rid}]: пустое правило (rule).")
            if not r.get("limit"):
                e.append(f"system_rules[{rid}]: пустое ограничение (limit).")
            est = r.get("established_at")
            if not isinstance(est, int) or not (1 <= est <= n):
                e.append(f"system_rules[{rid}]: established_at вне 1..{n}.")
            elif setup_ch is not None and est > setup_ch:
                e.append(f"system_rules[{rid}]: established_at ({est}) позже "
                         f"главы setup ({setup_ch}).")
            exc = r.get("exception")
            if exc:
                exceptions += 1
                if not isinstance(exc, dict):
                    e.append(f"system_rules[{rid}]: exception должен быть "
                             f"объектом {{chapter, price, foreshadow_from}}.")
                else:
                    ech = exc.get("chapter")
                    ef = exc.get("foreshadow_from")
                    if not isinstance(ech, int) or not (1 <= ech <= n):
                        e.append(f"system_rules[{rid}]: exception.chapter "
                                 f"вне 1..{n}.")
                    if not isinstance(ef, int) or not isinstance(ech, int) \
                            or ef >= ech:
                        e.append(f"system_rules[{rid}]: "
                                 f"exception.foreshadow_from должен быть "
                                 f"раньше exception.chapter.")
                    if not exc.get("price"):
                        e.append(f"system_rules[{rid}]: exception.price пуст.")
        if len(rule_ids) != len(set(rule_ids)):
            e.append("system_rules: дубликаты id.")
        if exceptions > 1:
            e.append(f"system_rules: не более одной записи с exception, "
                     f"получено {exceptions}.")

    # ─── build_arc ───────────────────────────────────────────
    arc = payload.get("build_arc")
    if not isinstance(arc, dict):
        e.append("build_arc: должен быть объектом.")
    else:
        for f in ("path", "flaw", "kept_limit"):
            if not arc.get(f):
                e.append(f"build_arc.{f}: пусто.")
        # привязка к главам битов (сокращённый каркас — по его правилам)
        expected = {
            "chosen_at":  bit_ch.get("break_into_two") or bit_ch.get("catalyst"),
            "false_win_at": bit_ch.get("midpoint"),
            "punished_at": bit_ch.get("all_is_lost"),
            "respec_at": (bit_ch.get("break_into_three")
                          or bit_ch.get("final_image")),
        }
        for f, want in expected.items():
            got = arc.get(f)
            if want is not None and got != want:
                e.append(f"build_arc.{f}: должен быть {want} (глава бита), "
                         f"получено {got!r}.")

    # ─── progression_ledger ──────────────────────────────────
    bit3 = bit_ch.get("break_into_three")
    ledger = payload.get("progression_ledger")
    if not isinstance(ledger, list):
        e.append("progression_ledger: должен быть массивом.")
        ledger = []
    elif short and len(ledger) < 4:
        e.append(f"progression_ledger: минимум 4 записи (сокращённый "
                 f"каркас), получено {len(ledger)}.")
    ledger_ids: list = []
    records: list = []
    for i, g in enumerate(ledger):
        if not isinstance(g, dict):
            e.append(f"progression_ledger[{i}]: должен быть объектом.")
            continue
        gid = g.get("id")
        ledger_ids.append(gid)
        if not isinstance(gid, str) or not re.fullmatch(r"G\d{2}", gid):
            e.append(f"progression_ledger[{i}]: id должен быть вида G01.")
        ch = g.get("chapter")
        if not isinstance(ch, int) or not (1 <= ch <= n):
            e.append(f"progression_ledger[{gid}]: chapter вне 1..{n}.")
            continue
        records.append(g)
        fu = g.get("first_use")
        po = g.get("payoff")
        if not isinstance(fu, int) or fu < ch:
            e.append(f"progression_ledger[{gid}]: first_use ({fu!r}) должен "
                     f"быть целым ≥ chapter ({ch}).")
        # перекомбинация/инсайт в break_into_three — сборка УЖЕ
        # обученных навыков: правило трёх касаний к ней не применимо.
        # Строгий +2 здесь даёт тупик: payoff ≥ fu+2 > finale, и модель
        # не может ни перечислить запись в описании кульминации
        # (payoff ≤ finale), ни приблизить payoff.
        combo_gap = (1 if (bit3 is not None and ch == bit3
                           and _rpg_norm(g.get("source"))
                           in ("инсайт", "перекомбинация"))
                     else 2)
        if not isinstance(po, int) or (isinstance(fu, int)
                                       and po < fu + combo_gap):
            e.append(f"progression_ledger[{gid}]: payoff ({po!r}) должен быть "
                     f"целым ≥ first_use + {combo_gap}.")
        if isinstance(po, int) and po > n:
            e.append(f"progression_ledger[{gid}]: payoff ({po}) больше "
                     f"total_chapters ({n}).")
        if not g.get("gain"):
            e.append(f"progression_ledger[{gid}]: пустой gain.")
        if not g.get("cost") or _rpg_cost_renewable(g.get("cost")):
            e.append(f"progression_ledger[{gid}]: cost пуст или сводится к "
                     f"восполнимому ресурсу (мана/выносливость/энергия без "
                     f"дополнения) — ставки нет.")
        if not g.get("limit"):
            e.append(f"progression_ledger[{gid}]: пустой limit "
                     f"(отдача/кулдаун/требование).")
        if _rpg_norm(g.get("source")) not in RPG_SOURCES:
            e.append(f"progression_ledger[{gid}]: source {g.get('source')!r} — "
                     f"только из списка: {', '.join(RPG_SOURCES)}.")
    if len(ledger_ids) != len(set(ledger_ids)):
        e.append("progression_ledger: дубликаты id.")

    if records:
        # запись в главе бита fun_and_games
        fg = bit_ch.get("fun_and_games")
        if fg is not None and not any(g.get("chapter") == fg for g in records):
            e.append(f"progression_ledger: нет записи в главе бита "
                     f"fun_and_games ({fg}).")
        # кульминация — только из заранее оплаченного
        for key in ("finale", "final_image"):
            ck = bit_ch.get(key)
            if ck is not None and any(g.get("chapter") == ck for g in records):
                e.append(f"progression_ledger: записи в главе {key} ({ck}) "
                         f"запрещены — кульминация собирается из оплаченного.")
        # break_into_three — только перекомбинация оплаченного
        if bit3 is not None:
            bad = [g.get("id") for g in records
                   if g.get("chapter") == bit3
                   and _rpg_norm(g.get("source")) not in
                   ("инсайт", "перекомбинация")]
            if bad:
                e.append(f"progression_ledger: в главе break_into_three "
                         f"({bit3}) source только «инсайт» или "
                         f"«перекомбинация» — нарушено в {bad}.")

        # в description finale перечислены 2–3 приобретения с payoff ≤ finale
        fin = bit_ch.get("finale")
        if fin is not None:
            fin_desc = next((b.get("description") or ""
                             for b in (payload.get("story_beats") or [])
                             if isinstance(b, dict)
                             and b.get("key") == "finale"), "")
            refs = re.findall(r"\[(G\d{2})\]", fin_desc)
            if not (2 <= len(refs) <= 3):
                e.append(f"description finale: должно перечислять 2–3 ID "
                         f"приобретений вида [Gxx], найдено {len(refs)}.")
            for gid in refs:
                rec = next((g for g in records if g.get("id") == gid), None)
                if rec is None:
                    e.append(f"description finale: {gid} не существует в "
                             f"progression_ledger.")
                elif isinstance(rec.get("payoff"), int) \
                        and rec["payoff"] > fin:
                    e.append(f"description finale: {gid} имеет payoff "
                             f"({rec['payoff']}) позже главы finale ({fin}) — "
                             f"перечислите приобретения, чьё решающее "
                             f"применение не позже финала.")

    # ─── целостность ссылок [Gxx]/[Ex]/[Rxx] в description ───
    known = {
        "G": {g.get("id") for g in ledger
              if isinstance(g, dict) and isinstance(g.get("id"), str)},
        "E": {t.get("id") for t in (payload.get("enemy_ladder") or [])
              if isinstance(t, dict) and isinstance(t.get("id"), str)},
        "R": {r.get("id") for r in rules
              if isinstance(r, dict) and isinstance(r.get("id"), str)},
    }
    for b in (payload.get("story_beats") or []):
        if not isinstance(b, dict):
            continue
        for ref in _RPG_REF_RE.findall(b.get("description") or ""):
            if ref not in known[ref[0]]:
                e.append(f"story_beats[{b.get('key')}]: ссылка [{ref}] "
                         f"не существует.")

    # ─── enemy_ladder ────────────────────────────────────────
    ladder = payload.get("enemy_ladder") or []
    need = 2 if short else 3
    if not isinstance(ladder, list):
        e.append("enemy_ladder: должен быть массивом.")
        ladder = []
    elif len(ladder) < need:
        e.append(f"enemy_ladder: минимум {need} тира, получено {len(ladder)}.")
    tiers = [t for t in ladder if isinstance(t, dict)]
    ladder_ids = [t.get("id") for t in tiers]
    if any(not isinstance(x, str) or not re.fullmatch(r"E\d+", x)
           for x in ladder_ids):
        e.append("enemy_ladder: id должны быть вида E1, E2…")
    if len(ladder_ids) != len(set(ladder_ids)):
        e.append("enemy_ladder: дубликаты id.")

    def _min_ch(t: dict):
        chs = t.get("chapters")
        if isinstance(chs, list) and chs \
                and all(isinstance(c, int) for c in chs):
            return min(chs)
        return None

    mins = [_min_ch(t) for t in tiers]
    if mins and all(isinstance(m, int) for m in mins) and mins != sorted(mins):
        e.append("enemy_ladder: тиры должны идти по возрастанию "
                 "минимальной главы.")
    for i, t in enumerate(tiers):
        if not t.get("threat"):
            e.append(f"enemy_ladder[{t.get('id')}]: пустое threat.")
        br = t.get("breaks")
        if not br:
            e.append(f"enemy_ladder[{t.get('id')}]: пустой breaks — непонятно, "
                     f"какую тактику героя тир обесценивает.")
        elif i > 0 and _rpg_norm(br) == _rpg_norm(tiers[i - 1].get("breaks")):
            e.append(f"enemy_ladder[{t.get('id')}]: breaks дословно повторяет "
                     f"предыдущий тир.")
        chs = t.get("chapters")
        if not isinstance(chs, list) or not chs \
                or not all(isinstance(c, int) and 1 <= c <= n for c in chs):
            e.append(f"enemy_ladder[{t.get('id')}]: chapters — массив глав "
                     f"1..{n}.")
    catalyst_ch = bit_ch.get("catalyst")
    if catalyst_ch is not None and mins and isinstance(mins[0], int) \
            and mins[0] > catalyst_ch + 1:
        e.append(f"enemy_ladder: первый тир появляется позже главы "
                 f"catalyst + 1 ({catalyst_ch + 1}).")
    fin = bit_ch.get("finale")
    if fin is not None and tiers:
        if fin not in (tiers[-1].get("chapters") or []):
            e.append(f"enemy_ladder: последний тир должен присутствовать "
                     f"в главе finale ({fin}).")

    # ─── power_curve / threat_curve ──────────────────────────
    def _curve(key: str):
        cur = payload.get(key)
        if (isinstance(cur, list) and len(cur) == n
                and all(isinstance(v, (int, float)) and 0.0 <= v <= 1.0
                        for v in cur)):
            return cur
        return None

    pc = _curve("power_curve")
    thc = _curve("threat_curve")
    for key, cur in (("power_curve", pc), ("threat_curve", thc)):
        if cur is None:
            e.append(f"{key}: массив ровно {n} чисел 0.0–1.0.")

    if pc is not None:
        lost = bit_ch.get("all_is_lost")
        for i in range(1, len(pc)):
            if pc[i] < pc[i - 1] - 1e-9 and (i + 1) != lost:
                e.append(f"power_curve: просадка в главе {i + 1} — разрешена "
                         f"только в главе all_is_lost.")
                break
    if pc is not None and thc is not None:
        fin = bit_ch.get("finale")
        w_lo, w_hi = _rpg_superiority_window(bit_ch)
        limit_ch = fin if fin is not None else n
        for i in range(limit_ch):
            ch_num = i + 1
            if w_lo is not None and w_lo <= ch_num <= w_hi:
                continue
            if thc[i] < pc[i] - 1e-9:
                e.append(f"кривые: в главе {ch_num} threat ({thc[i]}) ниже "
                         f"power ({pc[i]}) вне окна превосходства "
                         f"(fun_and_games..midpoint).")
                break
        lost = bit_ch.get("all_is_lost")
        if lost is not None and 1 <= lost <= n:
            delta = thc[lost - 1] - pc[lost - 1]
            if delta < 0.25 - 1e-9:
                e.append(f"кривые: в главе all_is_lost ({lost}) "
                         f"threat − power = {delta:.2f}, требуется ≥ 0.25.")

    return e


def _validate_rpg_outline(payload: dict, ss: dict) -> list[str]:
    """Жанровые проверки плана глав: роли сцен (анти гринд-монтаж),
    ссылки на гроссбух/лестницу/правила, копирование кривых, сцены
    под жанровые события главы."""
    e: list[str] = []
    chs = payload.get("chapters") or []

    n = ss.get("total_chapters")
    if not isinstance(n, int):
        n = len(chs)

    bit_ch = _rpg_bit_chapters(ss.get("story_beats"))
    ledger = [g for g in (ss.get("progression_ledger") or [])
              if isinstance(g, dict)]
    ladder = [t for t in (ss.get("enemy_ladder") or [])
              if isinstance(t, dict)]
    rules = [r for r in (ss.get("system_rules") or [])
             if isinstance(r, dict)]
    pc = ss.get("power_curve") if isinstance(ss.get("power_curve"), list) else []
    thc = (ss.get("threat_curve")
           if isinstance(ss.get("threat_curve"), list) else [])

    ledger_by_ch: dict = {}
    for g in ledger:
        if isinstance(g.get("chapter"), int):
            ledger_by_ch.setdefault(g["chapter"], []).append(g)
    # first_use/payoff указывают на чужие главы — индексы по ним,
    # а не по chapter записи
    ledger_by_fu: dict = {}
    ledger_by_po: dict = {}
    for g in ledger:
        if isinstance(g.get("first_use"), int):
            ledger_by_fu.setdefault(g["first_use"], []).append(g)
        if isinstance(g.get("payoff"), int):
            ledger_by_po.setdefault(g["payoff"], []).append(g)
    ladder_ids_by_ch: dict = {}
    for t in ladder:
        for cnum in (t.get("chapters") or []):
            if isinstance(cnum, int):
                ladder_ids_by_ch.setdefault(cnum, []).append(t.get("id"))
    rule_ids = {r.get("id") for r in rules if isinstance(r.get("id"), str)}

    bit3 = bit_ch.get("break_into_three")
    fin = bit_ch.get("finale")
    fim = bit_ch.get("final_image")
    lost = bit_ch.get("all_is_lost")
    setup = bit_ch.get("setup")

    grind_counts: list = []      # (num, число сцен «добыча»)
    human_chapters: set = set()  # главы со сценой «быт»/«расплата»
    rule_first_seen: dict = {}   # rule id → минимальная глава в rules_touched

    for c in chs:
        if not isinstance(c, dict):
            continue
        num = c.get("num")
        if not isinstance(num, int):
            continue
        cid = f"ch.{num}"
        roles: list = []
        for b in (c.get("beats") or []):
            if not isinstance(b, dict):
                continue
            role = b.get("role")
            roles.append(role)
            if role is None:
                e.append(f"{cid}.beats[{b.get('scene')}]: нет role — в "
                         f"RPG-плане каждая сцена обязана иметь тип.")
            elif role not in RPG_ROLES:
                e.append(f"{cid}.beats[{b.get('scene')}]: role {role!r} — "
                         f"только из списка: {', '.join(RPG_ROLES)}.")
        grind = roles.count("добыча")
        grind_counts.append((num, grind))
        if "быт" in roles or "расплата" in roles:
            human_chapters.add(num)

        # ── композиция ролей: ловим гринд-монтаж ──
        if roles.count("бой") > 2:
            e.append(f"{cid}: больше 2 сцен «бой» ({roles.count('бой')}).")
        if grind > 2:
            e.append(f"{cid}: больше 2 сцен «добыча» ({grind}).")
        if not ({"расплата", "быт", "разбор"} & set(roles)):
            e.append(f"{cid}: нет ни одной «человеческой» сцены "
                     f"(расплата, быт, разбор).")
        if num in (bit3, fin, fim) and grind:
            which = ("break_into_three" if num == bit3
                     else "finale" if num == fin else "final_image")
            e.append(f"{cid}: сцены «добыча» запрещены в главе бита {which}.")

        # ── жанровые ссылки главы ──
        refs = c.get("progression_refs")
        want = sorted(g.get("id") for g in ledger_by_ch.get(num, [])
                      if isinstance(g.get("id"), str))
        if not isinstance(refs, list):
            e.append(f"{cid}: progression_refs должен быть массивом.")
            refs = []
        else:
            # мусорные не-строки не должны ронять сортировку (TypeError
            # уводит стадию в слепой ретрай по исключению)
            refs = [x for x in refs if isinstance(x, str)]
        if sorted(refs) != want:
            e.append(f"{cid}: progression_refs ({refs}) не совпадает с "
                     f"записями ledger этой главы ({want}).")
        if len(refs) != len(set(refs)):
            e.append(f"{cid}: progression_refs содержит дубликаты.")

        erefs = c.get("enemy_refs")
        ewant = sorted({x for x in ladder_ids_by_ch.get(num, [])
                        if isinstance(x, str)})
        if not isinstance(erefs, list):
            e.append(f"{cid}: enemy_refs должен быть массивом.")
        else:
            erefs = [x for x in erefs if isinstance(x, str)]
            if sorted(set(erefs)) != ewant:
                e.append(f"{cid}: enemy_refs ({erefs}) не совпадает с "
                         f"активными тирами ladder этой главы ({ewant}).")

        rt = c.get("rules_touched")
        if not isinstance(rt, list):
            e.append(f"{cid}: rules_touched должен быть массивом.")
            rt = []
        else:
            bad = [x for x in rt if x not in rule_ids]
            if bad:
                e.append(f"{cid}: rules_touched → {bad} не из system_rules.")
            for x in rt:
                if isinstance(x, str):
                    rule_first_seen[x] = min(rule_first_seen.get(x, num), num)

        # ── cost_paid ──
        cost = c.get("cost_paid")
        if refs:
            if not isinstance(cost, str) or not cost.strip():
                e.append(f"{cid}: cost_paid пуст, хотя в главе есть "
                         f"приобретения ({refs}).")
            elif _rpg_cost_renewable(cost):
                e.append(f"{cid}: cost_paid сводится к восполнимому ресурсу — "
                         f"ставки нет.")
        for g in ledger_by_ch.get(num, []):
            if not g.get("cost") or _rpg_cost_renewable(g.get("cost")):
                e.append(f"{cid}: запись {g.get('id')} — cost пуст или "
                         f"восполнимый.")

        # ── сцены под жанровые события ──
        if refs and num != bit3 and "добыча" not in roles:
            e.append(f"{cid}: есть приобретения ({refs}), но нет сцены "
                     f"«добыча».")
        for g in ledger_by_fu.get(num, []):
            if (isinstance(g.get("chapter"), int) and g["chapter"] < num
                    and "тест" not in roles):
                e.append(f"{cid}: первое применение {g.get('id')} в этой "
                         f"главе, но нет сцены «тест».")
        for g in ledger_by_po.get(num, []):
            if not ({"бой", "тест"} & set(roles)):
                e.append(f"{cid}: выплата {g.get('id')} "
                         f"({g.get('payoff')}), но нет сцены «бой» "
                         f"или «тест».")
        if bit3 == num and not ({"разбор", "тест"} <= set(roles)):
            e.append(f"{cid}: глава break_into_three обязана содержать "
                     f"«разбор» и «тест».")
        if fin == num and not ({"бой", "расплата"} <= set(roles)):
            e.append(f"{cid}: глава finale обязана содержать «бой» и "
                     f"«расплата».")
        if lost == num:
            if "расплата" not in roles:
                e.append(f"{cid}: глава all_is_lost обязана содержать "
                         f"«расплата».")
            if num >= 2 and len(pc) >= num:
                prev, cur = pc[num - 2], c.get("power_target")
                if (isinstance(prev, (int, float))
                        and isinstance(cur, (int, float)) and cur >= prev):
                    e.append(f"{cid}: power_target ({cur}) не ниже предыдущей "
                             f"главы ({prev}) — в all_is_lost сила проседает.")

        # ── цели кривых ──
        for field, cur, curve in (("power_target", pc, "power_curve"),
                                  ("threat_target", thc, "threat_curve")):
            v = c.get(field)
            if v is None:
                e.append(f"{cid}: нет {field} — в RPG-плане глава несёт цели "
                         f"обеих кривых.")
            elif isinstance(v, (int, float)) and 1 <= num <= len(cur):
                if abs(v - cur[num - 1]) > 0.01:
                    e.append(f"{cid}: {field} не совпадает с "
                             f"{curve}[{num - 1}].")

        if setup == num and len(rt) < 2:
            e.append(f"{cid}: в главе setup rules_touched должен содержать "
                     f"минимум 2 правила, получено {len(rt)}.")

    # ── каждое правило показано не позже established_at ──
    for r in rules:
        rid = r.get("id")
        est = r.get("established_at")
        seen = rule_first_seen.get(rid)
        if isinstance(est, int) and (seen is None or seen > est):
            e.append(f"system_rules[{rid}]: не показано в действии до главы "
                     f"established_at ({est}).")

    # ── анти-монотонность: не более двух глав подряд с ≥2 «добыча» ──
    streak = 0
    for num, cnt in grind_counts:
        streak = streak + 1 if cnt >= 2 else 0
        if streak > 2:
            e.append(f"главы {num - 2}..{num}: три и более главы подряд "
                     f"с двумя и более сценами «добыча» — гринд-монтаж.")
            break

    # ── realrpg: в каждом окне из 3 глав — «человеческая» сцена ──
    if ss.get("rpg_mode") == "realrpg" and len(grind_counts) >= 3:
        nums = [num for num, _ in grind_counts]
        for i in range(len(nums) - 2):
            if not (set(nums[i:i + 3]) & human_chapters):
                e.append(f"realrpg: в главах {nums[i]}..{nums[i + 2]} нет "
                         f"сцены «быт» или «расплата».")
                break

    return e


# ────────────────────────────────────────────────────────────────
# STATE_PATCH
# ────────────────────────────────────────────────────────────────

ALLOWED_CHAR_FIELDS = {
    "suspicion", "resolve", "fear", "hope", "exhaustion", "moral_debt",
}
ALLOWED_REL_FIELDS = {
    "trust", "sympathy", "resentment", "attraction", "tension",
}


def validate_state_patch(patch: Any, bible: dict,
                         chapter_num: int) -> list[str]:
    e: list[str] = []
    if not isinstance(patch, dict):
        return ["patch должен быть объектом."]

    # ─── chapter_summary ─────────────────────────────────────
    summary = patch.get("chapter_summary")
    if not isinstance(summary, str) or not summary.strip():
        e.append("chapter_summary: пусто.")
    else:
        wc = len(summary.split())
        if wc < 15:
            e.append(f"chapter_summary: слишком короткий ({wc} слов, "
                     f"минимум 15).")
        elif wc > 150:
            e.append(f"chapter_summary: слишком длинный ({wc} слов, "
                     f"максимум 150).")

    # ─── abilities_gained ────────────────────────────────────
    gained = patch.get("abilities_gained") or []
    if not isinstance(gained, list):
        e.append("abilities_gained: должен быть массивом.")
    else:
        if len(gained) > 2:
            e.append(f"WARN: abilities_gained: {len(gained)} новых способностей "
                     f"за главу — обычно не больше 2. Проверьте, не раздувается ли.")
        for i, ab in enumerate(gained):
            if not isinstance(ab, dict):
                e.append(f"abilities_gained[{i}]: не объект.")
                continue
            if not ab.get("name"):
                e.append(f"abilities_gained[{i}]: нет name.")
            if not ab.get("description"):
                e.append(f"abilities_gained[{i}]: нет description.")
            if ab.get("level") != 1:
                e.append(f"abilities_gained[{i}]: level должен быть 1.")

    # ─── abilities_upgraded ──────────────────────────────────
    upgraded = patch.get("abilities_upgraded") or []
    if not isinstance(upgraded, list):
        e.append("abilities_upgraded: должен быть массивом.")
    else:
        if len(upgraded) > 1:
            e.append(f"WARN: abilities_upgraded: {len(upgraded)} повышений "
                     f"за главу — обычно не больше 1. Проверьте, не слишком "
                     f"ли быстро растёт сила.")
        for i, ab in enumerate(upgraded):
            if not isinstance(ab, dict):
                e.append(f"abilities_upgraded[{i}]: не объект.")
                continue
            if not ab.get("name"):
                e.append(f"abilities_upgraded[{i}]: нет name.")
            nl = ab.get("new_level")
            if not isinstance(nl, int) or not (2 <= nl <= 5):
                e.append(f"abilities_upgraded[{i}]: "
                         f"new_level должен быть 2..5, получено {nl!r}.")

    # ─── abilities_used ──────────────────────────────────────
    used = patch.get("abilities_used") or []
    if not isinstance(used, list):
        e.append("abilities_used: должен быть массивом.")

    char_ids = {
        c.get("id") for c in (bible.get("characters") or {}).get("characters", [])
        if isinstance(c, dict)
    }
    secret_ids = {
        s.get("id") for s in (bible.get("secrets") or {}).get("secrets", [])
        if isinstance(s, dict)
    }
    schedule = {
        x.get("secret_id"): x
        for x in ((bible.get("story_structure") or {}).get("reveal_schedule") or [])
    }

    # events
    for ev in patch.get("events_created") or []:
        if not isinstance(ev, dict):
            e.append("events_created: элемент не объект.")
            continue
        for pid in (ev.get("participants") or []):
            if char_ids and pid not in char_ids:
                e.append(f"events_created: участник {pid} не из characters.")
        if not ev.get("description"):
            e.append("events_created: пустое description.")

    # character_state_changes
    for c in patch.get("character_state_changes") or []:
        if not isinstance(c, dict):
            e.append("character_state_changes: элемент не объект.")
            continue
        cid = c.get("char_id")
        if char_ids and cid not in char_ids:
            e.append(f"character_state_changes: {cid} не из characters.")
        f = c.get("field")
        if f not in ALLOWED_CHAR_FIELDS:
            e.append(f"character_state_changes: недопустимое field '{f}'.")
        d = c.get("delta")
        if not isinstance(d, int) or not (-30 <= d <= 30):
            e.append(f"character_state_changes[{cid}]: delta {d!r} вне -30..30.")

    # relationship_changes
    for r in patch.get("relationship_changes") or []:
        if not isinstance(r, dict):
            e.append("relationship_changes: элемент не объект.")
            continue
        a, b = r.get("from"), r.get("to")
        if a not in char_ids or b not in char_ids:
            continue
        f = r.get("field")
        if f not in ALLOWED_REL_FIELDS:
            e.append(f"relationship_changes: недопустимое field '{f}'.")
        d = r.get("delta")
        if not isinstance(d, int) or not (-30 <= d <= 30):
            e.append(f"relationship_changes[{a}→{b}]: delta {d!r} вне -30..30.")

    # knowledge_gained
    for k in patch.get("knowledge_gained") or []:
        if not isinstance(k, dict):
            e.append("knowledge_gained: элемент не объект.")
            continue
        cid = k.get("char_id")
        if char_ids and cid not in char_ids:
            e.append(f"knowledge_gained: {cid} не из characters.")
        if not k.get("fact"):
            e.append("knowledge_gained: пустое fact.")

    # secrets_revealed
    for s in patch.get("secrets_revealed") or []:
        if not isinstance(s, dict):
            e.append("secrets_revealed: элемент не объект.")
            continue
        sid = s.get("secret_id")
        if secret_ids and sid not in secret_ids:
            e.append(f"secrets_revealed: {sid} не из secrets.")
            continue
        sch = schedule.get(sid) or {}
        earliest = sch.get("foreshadow_from", 1)
        if chapter_num < earliest:
            e.append(
                f"WARN: секрет {sid} раскрыт в главе {chapter_num}, "
                f"а по плану предвестники начинаются с главы {earliest}. "
                f"Можно оставить — но проверьте, не портит ли это интригу."
            )
        for who in (s.get("to_whom") or []):
            if char_ids and who not in char_ids:
                e.append(f"secrets_revealed[{sid}]: to_whom {who} неизвестен.")

    # new_locations / new_institutions: только структурная проверка
    for key in ("new_locations", "new_institutions"):
        v = patch.get(key)
        if not isinstance(v, list):
            e.append(f"{key} должен быть массивом.")
            continue
        for item in v:
            if not isinstance(item, dict) or not item.get("id"):
                e.append(f"{key}: у элемента нет id.")

    return e