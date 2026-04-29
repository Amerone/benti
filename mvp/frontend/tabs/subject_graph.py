"""主体关系网 SVG 展示模型。"""

from __future__ import annotations

import html
import math
from typing import Any

WIDTH = 1120
HEIGHT = 680
CENTER_X = WIDTH / 2
CENTER_Y = HEIGHT / 2
CLASS_RADIUS = 245
INDIVIDUAL_RADIUS = 305


def build_subject_graph_model(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """从主体 API 响应构建节点和边。"""

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for item in list(data.get("classes") or []):
        _upsert_node(nodes_by_id, item, kind="class")

    for item in list(data.get("individuals") or []):
        node = _upsert_node(nodes_by_id, item, kind="individual")
        for type_item in list(item.get("types") or []):
            target = _upsert_node(nodes_by_id, type_item, kind="class")
            edges.append({"source": node["id"], "target": target["id"], "label": "type", "kind": "type"})

    for item in list(data.get("object_properties") or []):
        label = _label(item)
        for domain in list(item.get("domain") or []):
            source = _upsert_node(nodes_by_id, domain, kind="class")
            for range_item in list(item.get("range") or []):
                target = _upsert_node(nodes_by_id, range_item, kind="class")
                edges.append({"source": source["id"], "target": target["id"], "label": label, "kind": "object"})

    for item in list(data.get("data_properties") or []):
        label = _label(item)
        for domain in list(item.get("domain") or []):
            source = _upsert_node(nodes_by_id, domain, kind="class")
            for range_item in list(item.get("range") or []):
                target = _upsert_node(nodes_by_id, range_item, kind="datatype")
                edges.append({"source": source["id"], "target": target["id"], "label": label, "kind": "data"})

    return {"nodes": list(nodes_by_id.values()), "edges": _dedupe_edges(edges)}


def render_subject_graph_html(data: dict[str, Any]) -> str:
    """渲染主体关系 SVG。"""

    model = build_subject_graph_model(data)
    if not model["nodes"]:
        return ""

    positions = _layout_positions(model["nodes"])
    edge_svg = "".join(_render_edge(edge, positions) for edge in model["edges"] if _edge_visible(edge, positions))
    node_svg = "".join(_render_node(node, positions[node["id"]]) for node in model["nodes"] if node["id"] in positions)

    return f"""
    <style>
    .subject-graph-shell {{
        margin: 0.85rem 0 1rem;
        border: 1px solid rgba(16, 36, 63, 0.10);
        border-radius: 8px;
        background:
            linear-gradient(180deg, rgba(255,255,255,0.76), rgba(255,255,255,0.58)),
            radial-gradient(circle at 28% 20%, rgba(255,106,61,0.10), transparent 28%),
            radial-gradient(circle at 78% 28%, rgba(19,181,200,0.10), transparent 28%);
        overflow: auto;
        box-shadow: 0 16px 36px rgba(16, 36, 63, 0.06);
    }}
    .subject-graph-edge {{
        stroke: rgba(16, 36, 63, 0.34);
        stroke-width: 1.6;
        marker-end: url(#subject-graph-arrow);
    }}
    .subject-graph-edge.data {{
        stroke-dasharray: 7 5;
        stroke: rgba(19, 181, 200, 0.58);
    }}
    .subject-graph-edge.type {{
        stroke: rgba(255, 106, 61, 0.46);
    }}
    .subject-graph-label {{
        fill: #344863;
        font-size: 13px;
        font-weight: 700;
        paint-order: stroke;
        stroke: rgba(255,255,255,0.88);
        stroke-width: 5px;
        stroke-linejoin: round;
    }}
    .subject-graph-node circle {{
        stroke-width: 2;
        filter: drop-shadow(0 8px 14px rgba(16, 36, 63, 0.12));
    }}
    .subject-graph-node.class circle {{
        fill: #10243f;
        stroke: rgba(255,255,255,0.92);
    }}
    .subject-graph-node.individual circle {{
        fill: #ff6a3d;
        stroke: rgba(255,255,255,0.92);
    }}
    .subject-graph-node.datatype circle {{
        fill: #13b5c8;
        stroke: rgba(255,255,255,0.92);
    }}
    .subject-graph-node text {{
        fill: #10243f;
        font-size: 14px;
        font-weight: 800;
        paint-order: stroke;
        stroke: rgba(255,255,255,0.92);
        stroke-width: 5px;
        stroke-linejoin: round;
    }}
    </style>
    <section class="subject-graph-shell">
      <svg viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" height="{HEIGHT}" role="img">
        <defs>
          <marker id="subject-graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(16, 36, 63, 0.44)"></path>
          </marker>
        </defs>
        {edge_svg}
        {node_svg}
      </svg>
    </section>
    """


def _upsert_node(nodes_by_id: dict[str, dict[str, Any]], item: dict[str, Any], *, kind: str) -> dict[str, Any]:
    node_id = str(item.get("iri") or item.get("name") or item.get("label") or "")
    if not node_id:
        node_id = f"{kind}:{len(nodes_by_id)}"
    node = nodes_by_id.get(node_id)
    if node is None:
        node = {"id": node_id, "label": _label(item), "kind": kind}
        nodes_by_id[node_id] = node
        return node
    if node["kind"] == "datatype" and kind == "class":
        node["kind"] = "class"
    return node


def _label(item: dict[str, Any]) -> str:
    return str(item.get("label") or item.get("name") or _local_name(str(item.get("iri") or "")) or "-")


def _local_name(iri: str) -> str:
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    return iri.rstrip("/").rsplit("/", 1)[-1]


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    result = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["label"], edge["kind"])
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    order = {"object": 0, "data": 1, "type": 2}
    result.sort(key=lambda item: (order.get(str(item["kind"]), 9), item["label"], item["source"], item["target"]))
    return result


def _layout_positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    class_nodes = [node for node in nodes if node["kind"] == "class"]
    individual_nodes = [node for node in nodes if node["kind"] == "individual"]
    datatype_nodes = [node for node in nodes if node["kind"] == "datatype"]

    positions: dict[str, tuple[float, float]] = {}
    _place_ring(positions, class_nodes, CLASS_RADIUS, offset=-math.pi / 2)
    _place_ring(positions, individual_nodes, INDIVIDUAL_RADIUS, offset=math.pi / 8)
    _place_ring(positions, datatype_nodes, INDIVIDUAL_RADIUS, offset=math.pi)
    return positions


def _place_ring(
    positions: dict[str, tuple[float, float]],
    nodes: list[dict[str, Any]],
    radius: float,
    *,
    offset: float,
) -> None:
    if not nodes:
        return
    if len(nodes) == 1 and radius == CLASS_RADIUS:
        positions[nodes[0]["id"]] = (CENTER_X, CENTER_Y)
        return
    for index, node in enumerate(nodes):
        angle = offset + (2 * math.pi * index / len(nodes))
        positions[node["id"]] = (CENTER_X + math.cos(angle) * radius, CENTER_Y + math.sin(angle) * radius)


def _edge_visible(edge: dict[str, Any], positions: dict[str, tuple[float, float]]) -> bool:
    return edge["source"] in positions and edge["target"] in positions


def _render_edge(edge: dict[str, Any], positions: dict[str, tuple[float, float]]) -> str:
    x1, y1 = positions[edge["source"]]
    x2, y2 = positions[edge["target"]]
    label_x = (x1 + x2) / 2
    label_y = (y1 + y2) / 2 - 8
    kind = html.escape(str(edge["kind"]))
    label = html.escape(str(edge["label"]))
    return (
        f'<line class="subject-graph-edge {kind}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"></line>'
        f'<text class="subject-graph-label" x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle">{label}</text>'
    )


def _render_node(node: dict[str, Any], position: tuple[float, float]) -> str:
    x, y = position
    kind = html.escape(str(node["kind"]))
    label = html.escape(str(node["label"]))
    return (
        f'<g class="subject-graph-node {kind}">'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="31"></circle>'
        f'<text x="{x:.1f}" y="{y + 49:.1f}" text-anchor="middle">{label}</text>'
        "</g>"
    )
