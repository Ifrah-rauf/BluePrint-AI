import json
import html
import math
import re
import streamlit.components.v1 as components


NODE_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*$')
EDGE_RE = re.compile(
    r'^\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*-->\s*([A-Za-z0-9_]+)\s*\[\s*"?(.*?)"?\s*\]\s*$'
)


def _wrap_text(text: str, max_chars: int = 18) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _parse_diagram(diagram_definition: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str]] = []

    for raw_line in diagram_definition.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("flowchart ") or line.startswith("graph "):
            continue
        if line.startswith("%%") or line.startswith("classDef ") or line.startswith("class ") or line.startswith("linkStyle "):
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


def _build_svg(diagram_definition: str) -> str:
    nodes, edges = _parse_diagram(diagram_definition)
    if not nodes:
        return f"""
        <div class="mermaid-error">Diagram failed to render: no nodes were found.</div>
        <pre style="white-space:pre-wrap; text-align:left; margin-top:12px;">{html.escape(diagram_definition)}</pre>
        """

    order = [node_id for node_id, _ in nodes]
    index_map = {node_id: idx for idx, node_id in enumerate(order)}

    width = 920
    node_w = 300
    node_h = 74
    gap_y = 36
    top_pad = 24
    left_x = (width - node_w) / 2
    text_x = width / 2
    height = top_pad + len(order) * (node_h + gap_y) + 24

    positions = {}
    for idx, node_id in enumerate(order):
        y = top_pad + idx * (node_h + gap_y)
        positions[node_id] = (left_x, y)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}">',
        """
        <defs>
            <marker id="arrowhead" markerWidth="12" markerHeight="8" refX="10" refY="4" orient="auto" markerUnits="strokeWidth">
                <path d="M 0 0 L 12 4 L 0 8 z" fill="#667085"></path>
            </marker>
            <filter id="shadow" x="-10%" y="-10%" width="130%" height="130%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#101828" flood-opacity="0.10"/>
            </filter>
        </defs>
        """,
    ]

    for src_id, tgt_id in edges:
        if src_id not in positions or tgt_id not in positions:
            continue
        sx, sy = positions[src_id]
        tx, ty = positions[tgt_id]
        x1 = sx + node_w / 2
        y1 = sy + node_h
        x2 = tx + node_w / 2
        y2 = ty
        parts.append(
            f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" '
            f'stroke="#667085" stroke-width="2.5" fill="none" marker-end="url(#arrowhead)"/>'
        )

    for node_id, label in nodes:
        x, y = positions[node_id]
        lines = _wrap_text(label, max_chars=24)
        text_y = y + 26
        parts.append(
            f'<g filter="url(#shadow)">'
            f'<rect x="{x:.1f}" y="{y:.1f}" rx="14" ry="14" width="{node_w}" height="{node_h}" '
            f'fill="#FFFFFF" stroke="#D0D5DD" stroke-width="1.8"/>'
            f'</g>'
        )
        parts.append(
            f'<text x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="middle" '
            f'font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="16" '
            f'font-weight="600" fill="#101828">'
        )
        for i, line in enumerate(lines[:3]):
            dy = 0 if i == 0 else 20
            safe_line = html.escape(line)
            parts.append(f'<tspan x="{text_x:.1f}" dy="{dy}">{safe_line}</tspan>')
        parts.append("</text>")

    parts.append("</svg>")
    return "".join(parts)


def render_mermaid_chart(mermaid_code: str, height: int = 400):
    """
    Renders a diagram string into a local SVG chart.

    The app still stores Mermaid-style text in state, but the display path no longer
    depends on browser-side CDN imports or iframe module loading.
    """
    svg_markup = _build_svg(mermaid_code)
    html_code = f"""
    <!DOCTYPE html>
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
            }}
            .mermaid-error {{
                color: #B42318;
                font-size: 0.9rem;
                text-align: center;
                margin-bottom: 10px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div class="diagram-shell">
            {svg_markup}
        </div>
    </body>
    </html>
    """
    components.html(html_code, height=max(height, 260), scrolling=True)
