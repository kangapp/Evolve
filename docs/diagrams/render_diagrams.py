"""Render documentation-only SVG diagrams using the Python standard library.

Run from any directory: python docs/diagrams/render_diagrams.py
These figures describe a proposed system; this is not the Evolve implementation.
"""

from __future__ import annotations

import html
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

BASELINE = "0.6.2"
ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
COLORS = {
    "ink": "#172b46", "muted": "#52647b", "line": "#bac8d8",
    "blue": "#235da8", "blue_bg": "#eef4fc", "green": "#176c61",
    "green_bg": "#edf8f4", "amber": "#94520b", "amber_bg": "#fff6e8",
    "red": "#a33342", "red_bg": "#fff1f2", "white": "#ffffff",
    "gray_bg": "#f5f7fa",
}


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def wrap(text: str, max_width: float, size: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line, width = "", 0.0
        tokens = re.findall(r"[A-Za-z0-9_./<>-]+|\s+|[^A-Za-z0-9_./<>\s-]", paragraph)
        for token in tokens:
            advance = sum(size * (1.0 if unicodedata.east_asian_width(c) in "WF" else 0.59) for c in token)
            if line and width + advance > max_width:
                carried = ""
                if token in "，。、；：？！)]}）】":
                    tail = re.search(r"[A-Za-z0-9_./<>-]+$", line)
                    carried = tail.group() if tail else line[-1:]
                    line = line[:-len(carried)]
                elif line[-1:] in "（【([":
                    carried, line = line[-1:], line[:-1]
                lines.append(line.rstrip())
                line = carried
                width = sum(size * (1.0 if unicodedata.east_asian_width(c) in "WF" else 0.59) for c in carried)
            if not line and token.isspace():
                continue
            line += token
            width += advance
        lines.append(line.rstrip())
    return lines


class SVG:
    def __init__(self, title: str, subtitle: str, width: int, height: int, number: int):
        self.width, self.height = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{esc(title)}</title><desc id="desc">{esc(subtitle)}</desc>',
            '<defs>',
        ]
        for key in ("blue", "green", "amber", "red", "muted"):
            self.parts.append(
                f'<marker id="arrow-{key}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{COLORS[key]}"/></marker>'
            )
        self.parts.extend([
            '</defs>',
            '<style>text{font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif}'
            'path,line,rect{vector-effect:non-scaling-stroke}</style>',
            f'<rect width="{width}" height="{height}" fill="{COLORS["white"]}"/>',
        ])
        self.text(44, 45, f"EVOLVE / {number:02d}", size=15, color="blue", weight=600)
        self.text(44, 90, title, size=32, weight=600)
        self.text(44, 124, subtitle, size=18, color="muted")
        self.line(44, 146, width - 44, 146, "line", arrow=False)

    def text(self, x, y, value, size=21, color="ink", anchor="start", weight=400):
        self.parts.append(
            f'<text x="{x}" y="{y}" fill="{COLORS[color]}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'
        )

    def multiline(self, x, y, lines, size=21, anchor="start", color="ink", weight=400):
        for index, value in enumerate(lines):
            self.text(x, y + index * (size + 7), value, size, color, anchor, weight)

    def rect(self, x, y, width, height, fill="gray_bg", stroke="line", radius=8):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
            f'fill="{COLORS[fill]}" stroke="{COLORS[stroke]}" stroke-width="1.2"/>'
        )

    def line(self, x1, y1, x2, y2, color="blue", dashed=False, arrow=True):
        dash = ' stroke-dasharray="7 6"' if dashed else ''
        marker = f' marker-end="url(#arrow-{color})"' if arrow else ''
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{COLORS[color]}" '
            f'stroke-width="1.7"{dash}{marker}/>'
        )

    def path(self, points, color="blue", dashed=False):
        path = "M " + " L ".join(f"{x} {y}" for x, y in points)
        dash = ' stroke-dasharray="7 6"' if dashed else ''
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{COLORS[color]}" stroke-width="1.7" '
            f'marker-end="url(#arrow-{color})"{dash}/>'
        )

    def node(self, x, y, width, height, title, body, kind="blue"):
        self.parts.append(f'<g data-box="{x},{y},{width},{height}">')
        self.rect(x, y, width, height, f"{kind}_bg", "line")
        self.text(x + 18, y + 35, title, size=23, weight=600, color=kind)
        self.multiline(x + 18, y + 69, wrap(body, width - 36, 20), size=20)
        self.parts.append('</g>')

    def finish(self, name: str):
        y = self.height - 48
        self.line(44, y - 23, self.width - 44, y - 23, "line", arrow=False)
        self.text(44, y + 4, f"设计 {BASELINE} · Evolve / 八个 Skill / 尚未实现 · 2026-10-31", size=15, color="muted")
        self.text(self.width - 44, y + 4, "实线：请求/操作   虚线：返回/条件路径   编号：图内顺序", size=15, color="muted", anchor="end")
        self.parts.append('</svg>')
        (ROOT / name).write_text("\n".join(self.parts) + "\n", encoding="utf-8")
        return {"file": name, "width": self.width, "height": self.height}


def sequence(number, name, title, subtitle, lanes, events):
    width = 1440
    xs = [112 + index * (width - 224) / (len(lanes) - 1) for index in range(len(lanes))]
    y = 265
    placements = []
    count = 0
    for event in events:
        if "section" in event:
            lines = wrap(event["section"], width - 140, 21)
            height = 32 + len(lines) * 28
            placements.append(("section", y, height, lines, event))
            y += height + 20
        else:
            count += 1
            label = f'{count:02d}  {event[2]}'
            a, b = xs[event[0]], xs[event[1]]
            available = min(abs(b - a) - 28, 720)
            lines = wrap(label, available, 21)
            height = len(lines) * 28 + 39
            placements.append(("message", y, height, lines, event))
            y += height
    height = int(y + 108)
    svg = SVG(title, subtitle, width, height, number)
    for x, label in zip(xs, lanes):
        lines = wrap(label, 174, 21)
        svg.rect(x - 100, 169, 200, 77, "blue_bg")
        svg.multiline(x, 199, lines, size=21, anchor="middle", weight=600)
        svg.line(x, 247, x, height - 91, "line", dashed=True, arrow=False)
    for kind, y, row_height, lines, event in placements:
        if kind == "section":
            svg.parts.append(f'<g data-box="48,{y},{width - 96},{row_height}">')
            svg.rect(48, y, width - 96, row_height, "amber_bg" if event.get("warn") else "gray_bg")
            svg.multiline(68, y + 32, lines, size=21, color="amber" if event.get("warn") else "muted", weight=500)
            svg.parts.append('</g>')
            continue
        a, b = xs[event[0]], xs[event[1]]
        style = event[3] if len(event) > 3 else "blue"
        color = "muted" if style == "return" else style
        center = (a + b) / 2
        label_width = min(abs(b - a) - 28, 720)
        label_height = len(lines) * 28
        svg.parts.append(f'<g data-box="{center-label_width/2},{y},{label_width},{label_height + 9}">')
        svg.rect(center - label_width / 2, y, label_width, label_height + 9, "white", "white", radius=3)
        svg.multiline(center, y + 22, lines, size=21, anchor="middle", color=color)
        svg.parts.append('</g>')
        arrow_y = y + label_height + 16
        svg.line(a, arrow_y, b, arrow_y, color, dashed=style in ("return", "red", "amber"))
    return svg.finish(name)


def main():
    from diagram_sources import SEQUENCES
    manifest = []
    for source in SEQUENCES:
        spec = dict(source)
        section = spec.pop("source")
        result = sequence(**spec)
        result.update(
            title=spec["title"], source=section, baseline=BASELINE,
            source_digest=hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            renderer_digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            svg_digest=hashlib.sha256((ROOT / result["file"]).read_bytes()).hexdigest(),
        )
        manifest.append(result)
    manifest.sort(key=lambda item: item["file"])
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(manifest)} SVG diagrams in {ROOT}")


if __name__ == "__main__":
    main()
