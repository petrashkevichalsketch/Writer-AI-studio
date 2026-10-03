"""Построение LORE_GRAPH. Программно, без LLM."""

from typing import Any


def _add_node(nodes: dict, nid: str, ntype: str, label: str) -> None:
    if not nid:
        return
    if nid in nodes:
        return
    nodes[nid] = {"id": nid, "type": ntype, "label": (label or nid)[:120]}


def _add_edge(edges: list, a: str, b: str, rel: str) -> None:
    if not a or not b or a == b:
        return
    edges.append({"from": a, "to": b, "relation": rel})


def build(bible: dict) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    # ── Институции
    for it in (bible.get("institutions") or {}).get("institutions", []) or []:
        _add_node(nodes, it.get("id"), "institution", it.get("name"))

    # ── Локации + рёбра controls / connected_to
    for it in (bible.get("geography") or {}).get("locations", []) or []:
        lid = it.get("id")
        _add_node(nodes, lid, "location", it.get("name"))
        for iid in (it.get("controlled_by") or []):
            _add_edge(edges, iid, lid, "controls")
        for link in (it.get("connected_to") or []):
            if isinstance(link, dict):
                _add_edge(edges, lid, link.get("location"), "connected_to")

    # ── События + рёбра causes
    for ev in (bible.get("history") or {}).get("events", []) or []:
        eid = ev.get("id")
        _add_node(nodes, eid, "event", ev.get("description"))
        for c in (ev.get("causes") or []):
            _add_edge(edges, c, eid, "causes")

    # ── Секреты + рёбра knows
    for s in (bible.get("secrets") or {}).get("secrets", []) or []:
        sid = s.get("id")
        _add_node(nodes, sid, "secret", s.get("truth"))
        for who in (s.get("known_by") or []):
            if who == "public":
                continue
            _add_edge(edges, who, sid, "knows")

    # ── Конфликты: factions → институции
    conflicts = bible.get("conflicts") or {}
    pc = conflicts.get("primary_conflict") or {}
    for iid in (pc.get("factions") or []):
        _add_edge(edges, iid, iid, "in_primary")   # self-loop отсекается _add_edge
    for c in (conflicts.get("secondary_conflicts") or []):
        for iid in (c.get("factions") or []):
            if isinstance(iid, str):
                _add_node(nodes, iid, "institution", iid)

    # ── Фильтр рёбер: обе вершины существуют
    node_ids = set(nodes.keys())
    edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]

    # ── Степени
    degree = {nid: 0 for nid in node_ids}
    for e in edges:
        degree[e["from"]] += 1
        degree[e["to"]] += 1

    isolated = [nid for nid, d in degree.items() if d == 0]
    high_degree = [nid for nid, d in degree.items() if d > 10]

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "degree": degree,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "isolated_nodes": isolated,
            "isolated_count": len(isolated),
            "max_degree": max(degree.values()) if degree else 0,
            "high_degree_nodes": high_degree,
        },
    }