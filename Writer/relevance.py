"""Relevance scoring. Программно, без LLM.
Формула (по ТЗ):
  raw = 0.4 * mentions_in_history
      + 0.4 * graph_degree
      + 0.2 * in_primary_conflict
  relevance = raw / max_raw
"""

import json
from typing import Any


def compute(bible: dict, graph: dict) -> dict:
    degree = graph.get("degree") or {}

    # mentions: сколько раз id встречается в строковом представлении
    # history и conflicts (то, где id чаще всего цитируются)
    haystack = json.dumps(
        {"history": bible.get("history"), "conflicts": bible.get("conflicts")},
        ensure_ascii=False,
    )

    primary = set(
        ((bible.get("conflicts") or {}).get("primary_conflict") or {}).get("factions")
        or []
    )

    raw: dict[str, float] = {}
    for node in graph.get("nodes") or []:
        nid = node.get("id")
        if not nid:
            continue
        ntype = node.get("type")
        if ntype not in ("institution", "location"):
            continue

        mentions = haystack.count(nid)
        deg = degree.get(nid, 0)
        in_primary = 1 if nid in primary else 0

        raw[nid] = 0.4 * mentions + 0.4 * deg + 0.2 * in_primary

    max_raw = max(raw.values()) if raw else 0.0
    if max_raw <= 0:
        relevance = {nid: 0.0 for nid in raw}
    else:
        relevance = {nid: round(v / max_raw, 4) for nid, v in raw.items()}

    return {
        "relevance": relevance,
        "raw": raw,
        "max_raw": max_raw,
    }