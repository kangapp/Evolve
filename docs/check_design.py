"""Validate Evolve design documents and SVG atlas; no plugin or business execution.

Run: python docs/check_design.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CURRENT = [ROOT / "AGENTS.md", ROOT / "AGENT.md"] + [DOCS / name for name in (
    "README.md", "design.md", "workflows.md", "runtime.md", "delivery.md", "scenarios.md"
)]
BASELINE = "0.6.2"
EXPECTED_COUNTS = {"G": 13, "NG": 10, "V": 140, "D": 26, "P": 19, "OQ": 10}
ERRORS: list[str] = []
COUNTS = Counter()


def fail(message: str) -> None:
    ERRORS.append(message)


def anchors(text: str) -> set[str]:
    found = re.findall(r'<a\s+id="([^"]+)"', text)
    if len(found) != len(set(found)):
        fail("Duplicate explicit anchor")
    result = set(found)
    used: Counter = Counter()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.M):
        heading = re.sub(r"[*\x60]", "", heading).strip().lower()
        slug = re.sub(r"[^\w\-\s]", "", heading)
        slug = re.sub(r"\s", "-", slug)
        number = used[slug]
        used[slug] += 1
        result.add(slug if not number else f"{slug}-{number}")
    return result


def check_link(source: Path, target: str) -> None:
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return
    target = unquote(target.strip("<>"))
    name, _, fragment = target.partition("#")
    path = (source.parent / name).resolve() if name else source.resolve()
    COUNTS["local_links"] += 1
    if not path.exists():
        fail(f"{source.relative_to(ROOT)} -> missing {target}")
    elif fragment and path.suffix.lower() == ".md":
        if fragment not in anchors(path.read_text(encoding="utf-8")):
            fail(f"{source.relative_to(ROOT)} -> missing anchor {target}")


def numbered(text: str, pattern: str, prefix: str, count: int) -> None:
    ids = re.findall(pattern, text, re.M)
    expected = [f"{prefix}-{n:03d}" for n in range(1, count + 1)]
    if len(ids) != len(set(ids)) or sorted(ids) != expected:
        fail(f"{prefix} definitions mismatch: {ids}")
    COUNTS[prefix + "_definitions"] = len(ids)


def check_markdown() -> None:
    for path in [ROOT / "AGENTS.md", ROOT / "AGENT.md", ROOT / "README.md", ROOT / "CONTRIBUTING.md"] + sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        COUNTS["markdown_files"] += 1
        if text.count("\ufffd"):
            fail(f"{path.name}: replacement characters")
        if len(re.findall(r"^\x60\x60\x60", text, re.M)) % 2:
            fail(f"{path.name}: unclosed code fence")
        anchors(text)
        for target in re.findall(r"!?(?:\[[^\]\n]*\])\(([^)\n]+)\)", text):
            check_link(path, target)
        for kind, block in re.findall(r"^\x60\x60\x60(toml|json)\n(.*?)^\x60\x60\x60", text, re.M | re.S):
            try:
                (tomllib.loads if kind == "toml" else json.loads)(block)
                COUNTS["parsed_config_examples"] += 1
            except Exception as error:
                fail(f"{path.name}: invalid {kind}: {error}")
    for path in CURRENT:
        if BASELINE not in path.read_text(encoding="utf-8").split("\n", 4)[2]:
            fail(f"{path.name}: missing current baseline in opening")
    design = (DOCS / "design.md").read_text(encoding="utf-8")
    delivery = (DOCS / "delivery.md").read_text(encoding="utf-8")
    numbered(design, r"^- \*\*(G-\d{3})\*\*", "G", 13)
    numbered(design, r"^- \*\*(NG-\d{3})\*\*", "NG", 10)
    numbered(delivery, r"^- \*\*(V-\d{3}) ", "V", EXPECTED_COUNTS["V"])
    numbered(delivery, r"^### (D-\d{3})：", "D", EXPECTED_COUNTS["D"])
    numbered(delivery, r"^- \*\*(P-\d{3})\*\*", "P", EXPECTED_COUNTS["P"])
    numbered(delivery, r"^- \*\*(OQ-\d{3}) ", "OQ", 10)
    ac = set(re.findall(r"AC-\d{3}", delivery))
    if ac != {f"AC-{i:03d}" for i in range(1, 15)}:
        fail("Historic AC mapping incomplete")
    owners = re.findall(r"^- \*\*evolve-([a-z]+)\*\*：", design, re.M)
    expected = {"workflow", "init", "propose", "apply", "verify", "archive", "learn", "maintain"}
    if set(owners) != expected or len(owners) != 8:
        fail(f"Skill owners mismatch: {owners}")
    workflows = (DOCS / "workflows.md").read_text(encoding="utf-8")
    commands = []
    for owner, body in re.findall(r"^- \*\*([a-z]+)\*\*：(.*)$", workflows, re.M):
        if owner not in expected:
            fail(f"Unexpected command owner {owner}")
        commands += [command.strip().rstrip("。") for command in body.split("；", 1)[0].split("、")]
    command_set = {"status","next","resume","init","propose","update","analyze","apply","verify","archive","sync","learn","history","maintain"}
    if set(commands) != command_set or len(commands) != 14:
        fail(f"Command mapping mismatch: {commands}")
    for path in CURRENT:
        for prefix, number in re.findall(r"(?<![A-Z-])(V|D|P|OQ|NG|G)-(\d{3})", path.read_text(encoding="utf-8")):
            if not 1 <= int(number) <= EXPECTED_COUNTS[prefix]:
                fail(f"Undefined reference {prefix}-{number} in {path.name}")
    COUNTS["skill_owners"] = len(owners)
    COUNTS["top_level_actions"] = len(commands)


def check_implementation_plan() -> None:
    delivery = (DOCS / "delivery.md").read_text(encoding="utf-8")
    entries = re.findall(r"^#### (IMP-\d{3})：([^\n]+)\n(.*?)(?=^#### |^### |\Z)", delivery, re.M | re.S)
    ids = [entry[0] for entry in entries]
    expected = [f"IMP-{i:03d}" for i in range(1, 15)]
    if ids != expected:
        fail(f"Implementation slice definitions mismatch: {ids}")
    graph: dict[str, list[str]] = {}
    for identifier, title, body in entries:
        dependency = re.search(r"^依赖：(.+)$", body, re.M)
        if dependency is None:
            fail(f"Missing dependency declaration: {identifier}")
            dependencies = []
        else:
            dependencies = re.findall(r"IMP-\d{3}", dependency.group(1))
            if not dependencies and dependency.group(1).strip() != "无。":
                fail(f"Unrecognized dependency declaration: {identifier}")
        if len(dependencies) != len(set(dependencies)):
            fail(f"Duplicate implementation dependency: {identifier}")
        for prerequisite in dependencies:
            if prerequisite not in ids:
                fail(f"Undefined implementation dependency: {identifier} -> {prerequisite}")
        graph[identifier] = dependencies
        if re.search(r"^交付：\S", body, re.M) is None:
            fail(f"Missing deliverable: {identifier}")
        acceptance = re.search(r"^验收：(.+)$", body, re.M)
        if acceptance is None or re.search(r"V-\d{3}", acceptance.group(1)) is None:
            fail(f"Missing acceptance mapping: {identifier}")
    visited: set[str] = set()
    active: set[str] = set()
    def visit(identifier: str) -> None:
        if identifier in active:
            fail(f"Cyclic implementation dependency: {identifier}")
            return
        if identifier in visited or identifier not in graph:
            return
        active.add(identifier)
        for prerequisite in graph[identifier]:
            visit(prerequisite)
        active.remove(identifier)
        visited.add(identifier)
    for identifier in graph:
        visit(identifier)
    for path in CURRENT:
        for reference in re.findall(r"(?<![A-Z-])IMP-\d{3}", path.read_text(encoding="utf-8")):
            if reference not in ids:
                fail(f"Undefined implementation reference {reference} in {path.name}")
    COUNTS["implementation_slices"] = len(entries)
    COUNTS["implementation_dependencies"] = sum(map(len, graph.values()))


def check_diagrams() -> None:
    manifest = json.loads((DOCS / "diagrams/manifest.json").read_text(encoding="utf-8"))
    names = [item["file"] for item in manifest]
    actual = {p.name for p in (DOCS / "diagrams").glob("*.svg")}
    if len(names) != 17 or set(names) != actual or len(set(names)) != len(names):
        fail("Manifest and actual atlas differ")
    current_text = "\n".join(p.read_text(encoding="utf-8") for p in CURRENT)
    module = ast.parse((DOCS / "diagrams/diagram_sources.py").read_text(encoding="utf-8"))
    assignment = next(n for n in module.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SEQUENCES" for t in n.targets))
    sources = json.loads(ast.literal_eval(assignment.value.args[0]))
    by_name = {source["name"]: source for source in sources}
    if len(by_name) != len(sources) or set(by_name) != set(names):
        fail("Diagram source and manifest name sets differ")
    renderer_digest = hashlib.sha256((DOCS / "diagrams/render_diagrams.py").read_bytes()).hexdigest()
    ns = {"s": "http://www.w3.org/2000/svg"}
    for item in manifest:
        name = item["file"]
        source = by_name.get(name)
        if source is not None:
            source_digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if item.get("source_digest") != source_digest or item["source"] != source["source"] or item["title"] != source["title"]:
                fail(f"Stale diagram source: {name}")
        if item.get("renderer_digest") != renderer_digest:
            fail(f"Stale diagram renderer: {name}")
        if item.get("svg_digest") != hashlib.sha256((DOCS / "diagrams" / name).read_bytes()).hexdigest():
            fail(f"SVG bytes differ from manifest: {name}")
        if name not in current_text:
            fail(f"Unreferenced diagram: {name}")
        if item["baseline"] != BASELINE:
            fail(f"Stale diagram baseline: {name}")
        check_link(DOCS / "README.md", item["source"])
        svg = ET.parse(DOCS / "diagrams" / name).getroot()
        width, height = float(svg.attrib["width"]), float(svg.attrib["height"])
        if [width, height] != [item["width"], item["height"]]:
            fail(f"Dimensions mismatch: {name}")
        if svg.find("s:title", ns) is None or svg.find("s:desc", ns) is None:
            fail(f"Missing accessible title or description: {name}")
        for text in svg.findall(".//s:text", ns):
            x, y = float(text.attrib["x"]), float(text.attrib["y"])
            size = float(text.attrib["font-size"])
            value = "".join(text.itertext())
            advance = sum(size * (1.0 if unicodedata.east_asian_width(c) in "WF" else 0.59) for c in value)
            anchor = text.attrib.get("text-anchor", "start")
            left = x - (advance / 2 if anchor == "middle" else advance if anchor == "end" else 0)
            right = left + advance
            if left < -1 or right > width + 1 or y - size < 0 or y > height:
                fail(f"Text outside SVG: {name}: {value}")
            COUNTS["svg_text_nodes"] += 1
        for group in svg.findall(".//s:g", ns):
            if "data-box" not in group.attrib:
                continue
            x,y,w,h = map(float,group.attrib["data-box"].split(","))
            for text in group.findall("s:text",ns):
                tx,ty,size = float(text.attrib["x"]),float(text.attrib["y"]),float(text.attrib["font-size"])
                if not (x <= tx <= x+w and y <= ty-size and ty <= y+h):
                    fail(f"Text baseline outside containing box: {name}")
    COUNTS["svg_diagrams"] = len(manifest)


def check_snapshot() -> None:
    snapshots = {
        "pre-revision-0.5.6-20261031.zip": "dd007b29fc678e2c734bf026821bf025ee0f1927b160927decc655c53277ea2e",
        "pre-review-0.6.0-20261031.zip": "531cc313b76c7359738e4c5afb919e3b771152c0b60293dea83f304383e26a44",
        "pre-matt-revision-0.6.1-20261031.zip": "d6ff4faa048f50446d35e044db9cf7ff253097f7ece2f1ba04785fa2cdf311a4",
    }
    for name, expected in snapshots.items():
        path = DOCS / "archive" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            fail(f"Snapshot checksum changed: {name}")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                fail(f"Snapshot ZIP integrity failure: {name}")
            entries = json.loads(archive.read("snapshot-manifest.json"))
            for entry in entries:
                data = archive.read(entry["path"])
                if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    fail(f"Snapshot entry mismatch: {name}: {entry['path']}")
            COUNTS["snapshot_files"] += len(entries)
            COUNTS["snapshot_archives"] += 1


def main() -> None:
    check_markdown()
    check_implementation_plan()
    check_diagrams()
    check_snapshot()
    for path in [DOCS / "check_design.py", DOCS / "diagrams/diagram_sources.py", DOCS / "diagrams/render_diagrams.py"]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        COUNTS["python_sources_parsed"] += 1
    print(json.dumps({"checks": dict(COUNTS), "errors": ERRORS}, ensure_ascii=False, indent=2))
    sys.exit(bool(ERRORS))


if __name__ == "__main__":
    main()

