import html
import re
import streamlit.components.v1 as components
from collections import deque

NODE_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*$')
EDGE_RE = re.compile(
    r'^\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*-->\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*$'
)


def _wrap_text(text: str, max_chars: int = 18) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _parse_diagram(diagram_definition: str):
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str]] = []

    for raw_line in diagram_definition.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("flowchart ", "graph ", "%%", "classDef ", "class ", "linkStyle ")):
            continue

        edge_match = EDGE_RE.match(line)
        if edge_match:
            src_id, src_label, tgt_id, tgt_label = edge_match.groups()
            nodes[src_id] = src_label
            nodes[tgt_id] = tgt_label
            edges.append((src_id, tgt_id))
            continue

        node_match = NODE_RE.match(line)
        if node_match:
            node_id, label = node_match.groups()
            nodes[node_id] = label

    return list(nodes.items()), edges


def _compute_layout(
    nodes: list[tuple[str, str]],
    edges: list[tuple[str, str]],
    canvas_width: int,
    node_w: int,
    node_h: int,
    gap_y: int,
    gap_x: int,
    top_pad: int,
):
    """
    BFS-based hierarchical layout.
    - Root nodes (no parents) start at level 0.
    - BFS assigns levels downward.
    - Isolated nodes (in_degree=0, out_degree=0) are placed at max_level+1
      as auxiliary infrastructure (monitoring, logging etc).
    - Dynamic canvas width prevents off-screen nodes.
    """
    node_ids = [nid for nid, _ in nodes]
    children: dict[str, list[str]] = {nid: [] for nid in node_ids}
    parents: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for src, tgt in edges:
        if src in children and tgt in children:
            children[src].append(tgt)
            parents[tgt].append(src)

    # Isolated nodes — no incoming AND no outgoing edges
    isolated = {
        nid for nid in node_ids
        if not parents[nid] and not children[nid]
    }

    # Root nodes = no parents, but DO have children (not isolated)
    roots = [nid for nid in node_ids if not parents[nid] and nid not in isolated]
    if not roots and not isolated:
        roots = [node_ids[0]] if node_ids else []

    # BFS — first visit wins (stable for cyclic graphs)
    levels: dict[str, int] = {}
    queue = deque((r, 0) for r in roots)
    while queue:
        nid, lvl = queue.popleft()
        if nid in levels:
            continue
        levels[nid] = lvl
        for child in children[nid]:
            if child not in isolated:
                queue.append((child, lvl + 1))

    # Any non-isolated node not reached by BFS (disconnected subgraph) → level 0
    for nid in node_ids:
        if nid not in levels and nid not in isolated:
            levels[nid] = 0

    # Place isolated nodes one level below the deepest main-flow level
    max_level = max(levels.values()) if levels else 0
    for nid in isolated:
        levels[nid] = max_level + 1

    # Group by level
    level_groups: dict[int, list[str]] = {}
    for nid in node_ids:
        lvl = levels[nid]
        level_groups.setdefault(lvl, []).append(nid)

    # Compute positions
    positions: dict[str, tuple[float, float]] = {}
    for lvl, group in sorted(level_groups.items()):
        count = len(group)
        total_row_width = count * node_w + (count - 1) * gap_x
        start_x = (canvas_width - total_row_width) / 2
        y = top_pad + lvl * (node_h + gap_y)
        for i, nid in enumerate(group):
            x = start_x + i * (node_w + gap_x)
            positions[nid] = (x, y)

    return positions, level_groups, isolated


def _node_color(label: str) -> str:
    l = label.lower()
    if any(x in l for x in ["postgres", "mysql", "database", "db"]):
        return "#FEF3C7"
    if "redis" in l or "cache" in l:
        return "#FDE68A"
    if any(x in l for x in ["rabbit", "kafka", "queue", "message"]):
        return "#FECACA"
    if any(x in l for x in ["gateway", "load balancer", "balancer"]):
        return "#DBEAFE"
    if any(x in l for x in ["monitor", "grafana", "prometheus", "logging", "log", "metric", "tracing"]):
        return "#EDE9FE"
    return "#DCFCE7"


def _build_svg(diagram_definition: str) -> str:
    nodes, edges = _parse_diagram(diagram_definition)
    if not nodes:
        return (
            '<div class="mermaid-error">Diagram failed to render: no nodes found.</div>'
            f'<pre style="white-space:pre-wrap;text-align:left;margin-top:12px;">'
            f'{html.escape(diagram_definition)}</pre>'
        )

    node_w = 220
    node_h = 60
    gap_y = 60
    gap_x = 40
    top_pad = 32

    # First pass to get level groups for width calculation
    _, level_groups_tmp, _ = _compute_layout(nodes, edges, 960, node_w, node_h, gap_y, gap_x, top_pad)

    # Dynamic canvas width — never clip nodes off-screen
    max_nodes_in_level = max(len(g) for g in level_groups_tmp.values()) if level_groups_tmp else 1
    canvas_width = max(960, max_nodes_in_level * (node_w + gap_x) + 80)

    # Final layout with correct width
    positions, level_groups, isolated = _compute_layout(
        nodes, edges, canvas_width, node_w, node_h, gap_y, gap_x, top_pad
    )

    num_levels = max(level_groups.keys()) + 1 if level_groups else 1
    canvas_height = top_pad + num_levels * (node_h + gap_y) + 40

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_width} {canvas_height}" '
        f'width="{canvas_width}" height="{canvas_height}">',
        """<defs>
            <marker id="arr" markerWidth="10" markerHeight="7"
                    refX="9" refY="3.5" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L10,3.5 L0,7 z" fill="#667085"/>
            </marker>
            <filter id="shadow" x="-15%" y="-15%" width="140%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="3"
                              flood-color="#101828" flood-opacity="0.08"/>
            </filter>
        </defs>""",
    ]

    # Separator line above isolated (auxiliary) nodes section
    if isolated and (max(level_groups.keys()) in level_groups):
        aux_level = max(level_groups.keys())
        sep_y = top_pad + aux_level * (node_h + gap_y) - gap_y // 2
        parts.append(
            f'<line x1="40" y1="{sep_y}" x2="{canvas_width - 40}" y2="{sep_y}" '
            f'stroke="#D0D5DD" stroke-width="1" stroke-dasharray="6,4"/>'
        )
        parts.append(
            f'<text x="{canvas_width // 2}" y="{sep_y - 6}" text-anchor="middle" '
            f'font-family="Inter, ui-sans-serif, system-ui, sans-serif" '
            f'font-size="11" fill="#98A2B3">Auxiliary Infrastructure</text>'
        )

    # Edges
    for src_id, tgt_id in edges:
        if src_id not in positions or tgt_id not in positions:
            continue
        sx, sy = positions[src_id]
        tx, ty = positions[tgt_id]
        x1, y1 = sx + node_w / 2, sy + node_h
        x2, y2 = tx + node_w / 2, ty

        if abs(y1 - y2) < 10:
            ctrl_y = y1 - 40
            path = f"M {x1:.1f} {y1:.1f} C {x1:.1f} {ctrl_y:.1f}, {x2:.1f} {ctrl_y:.1f}, {x2:.1f} {y2:.1f}"
        else:
            c1y = y1 + (y2 - y1) * 0.4
            c2y = y1 + (y2 - y1) * 0.6
            path = f"M {x1:.1f} {y1:.1f} C {x1:.1f} {c1y:.1f}, {x2:.1f} {c2y:.1f}, {x2:.1f} {y2:.1f}"

        parts.append(
            f'<path d="{path}" stroke="#667085" stroke-width="2" '
            f'fill="none" marker-end="url(#arr)"/>'
        )

    # Nodes
    for node_id, label in nodes:
        if node_id not in positions:
            continue
        x, y = positions[node_id]
        cx = x + node_w / 2
        fill = _node_color(label)
        # Auxiliary nodes get a lighter border to visually distinguish them
        stroke = "#C0C9D4" if node_id in isolated else "#D0D5DD"
        opacity = 'opacity="0.85"' if node_id in isolated else ''

        text_lines = _wrap_text(label, max_chars=20)
        total_text_h = len(text_lines[:2]) * 18
        text_start_y = y + (node_h - total_text_h) / 2 + 14

        parts.append(
            f'<g filter="url(#shadow)" {opacity}>'
            f'<rect x="{x:.1f}" y="{y:.1f}" rx="12" ry="12" '
            f'width="{node_w}" height="{node_h}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
            f'</g>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{text_start_y:.1f}" text-anchor="middle" '
            f'font-family="Inter, ui-sans-serif, system-ui, sans-serif" '
            f'font-size="13" font-weight="600" fill="#101828">'
        )
        for i, line in enumerate(text_lines[:2]):
            dy = 0 if i == 0 else 18
            parts.append(f'<tspan x="{cx:.1f}" dy="{dy}">{html.escape(line)}</tspan>')
        parts.append("</text>")

    parts.append("</svg>")
    return "".join(parts)


def render_mermaid_chart(mermaid_code: str, height: int = 500):
    svg_markup = _build_svg(mermaid_code)
    html_code = f"""<!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        margin: 0;
        padding: 12px;
        background: transparent;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
    }}

    .diagram-shell {{
        width: 100%;
        overflow-x: auto;
        overflow-y: auto;
        white-space: nowrap;
    }}

    .diagram-shell svg {{
        display: block;
    }}

    .mermaid-error {{
        color: #B42318;
        font-size: .9rem;
        text-align: center;
        margin-bottom: 10px;
        white-space: pre-wrap;
    }}
    </style>
    </head>
    <body>
    <div class="diagram-shell">{svg_markup}</div>
    </body>
    </html>"""
    components.html(html_code, height=max(height, 300), scrolling=True)