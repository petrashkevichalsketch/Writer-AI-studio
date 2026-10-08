"""Программные валидаторы стадий. Возвращают список строк-ошибок."""

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

    # Ссылки controlled_by / connected_to на существующие id
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

    # мягкая проверка — WARN, не блокирует стадию
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
            if not isinstance(ec, int) or not (1 <= ec <= 20):
                e.append(f"{sid}.reveal_rules.earliest_chapter должно быть 1..20.")

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

        if a in degree: degree[a] += 1
        if b in degree: degree[b] += 1

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

def validate_story_structure(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    import config
    proj = bible.get("_project") or {}
    # bible не содержит project — берём формат через глобальный хук
    # (передаётся снаружи через validator) — но у нас проще: смотрим
    # на длину tension_curve, если total_chapters нет.
    fmt_min, fmt_max = 15, 20
    n = payload.get("total_chapters")
    if not isinstance(n, int) or not (fmt_min <= n <= fmt_max):
        # Разрешаем любой диапазон 1..50 — для рассказов и повестей
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

    # acts
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

    # pov_threads
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

    # character_arcs
    arcs = payload.get("character_arcs") or []
    if not isinstance(arcs, list) or not arcs:
        e.append("character_arcs: пусто.")
    else:
        for a in arcs:
            c = a.get("char")
            if char_ids and c not in char_ids:
                e.append(f"character_arcs: неизвестный персонаж {c}.")

    # reveal_schedule
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
                e.append(f"reveal_schedule[{x.get('secret_id')}].reveal_at_chapter вне 1..{n}.")
            if isinstance(rc, int) and isinstance(ff, int) and ff >= rc:
                e.append(f"reveal_schedule[{x.get('secret_id')}]: foreshadow_from ≥ reveal_at_chapter.")

    # tension_curve
    tc = payload.get("tension_curve") or []
    if not isinstance(tc, list) or len(tc) != n:
        e.append(f"tension_curve: длина {len(tc) if isinstance(tc, list) else '?'}, ожидается {n}.")
    else:
        for v in tc:
            if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
                e.append("tension_curve: значения должны быть 0..1.")
                break

    return e


# ────────────────────────────────────────────────────────────────
# CHAPTER_OUTLINE
# ────────────────────────────────────────────────────────────────

def validate_chapter_outline(payload: Any, bible: dict) -> list[str]:
    e: list[str] = []
    if not isinstance(payload, dict):
        return ["Ожидался JSON-объект."]

    chs = payload.get("chapters") or []
    if not isinstance(chs, list):
        return ["chapters должен быть массивом."]

    ss = bible.get("story_structure") or {}
    total_n = ss.get("total_chapters") or len(chs)
    tc = ss.get("tension_curve") or []

    char_ids = {
        c.get("id") for c in (bible.get("characters") or {}).get("characters", [])
        if isinstance(c, dict)
    }
    loc_ids = {
        l.get("id") for l in (bible.get("geography") or {}).get("locations", [])
        if isinstance(l, dict)
    }
    event_ids = {
        ev.get("id") for ev in (bible.get("history") or {}).get("events", [])
        if isinstance(ev, dict)
    }

    if len(chs) != total_n:
        e.append(f"chapters: {len(chs)} глав, ожидалось {total_n}.")

    nums = sorted(c.get("num") for c in chs if isinstance(c, dict))
    if nums != list(range(1, total_n + 1)):
        e.append("chapters: num должны идти 1..N без пропусков.")

    total_words = 0
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
                e.append(f"ch.{cid}: events → {x} не из history (новые события не указывать).")
        if not c.get("purpose"):
            e.append(f"ch.{cid}: purpose пусто.")
        beats = c.get("beats")
        if not isinstance(beats, list):
            e.append(f"ch.{cid}: beats должен быть массивом.")
        elif not (3 <= len(beats) <= 5):
            e.append(f"ch.{cid}: beats — 3–5 сцен, получено {len(beats)}.")
        else:
            for i, b in enumerate(beats):
                if not isinstance(b, str) or not b.strip():
                    e.append(f"ch.{cid}.beats[{i}]: пусто.")
                elif len(b.split()) > 35:
                    e.append(f"ch.{cid}.beats[{i}]: слишком длинный "
                             f"({len(b.split())} слов, максимум 35).")
        tt = c.get("tension_target")
        if not isinstance(tt, (int, float)) or not (0.0 <= tt <= 1.0):
            e.append(f"ch.{cid}: tension_target вне 0..1.")
        elif tc and c.get("num") and 1 <= c["num"] <= len(tc):
            if abs(tt - tc[c["num"] - 1]) > 0.01:
                e.append(f"ch.{cid}: tension_target не совпадает с tension_curve.")
        wt = c.get("word_target")
        if isinstance(wt, int) and wt > 0:
            total_words += wt

    # Проверка суммы убрана: поле word_target хранит слова на главу,
    # а не знаки. Длина главы при генерации берётся из настроек
    # (chapter_words), поэтому сумма здесь не важна.

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
            continue  # sanitize уже должен был это убрать; игнорируем молча
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