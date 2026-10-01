#!/usr/bin/env python3
"""Validate a business-flow report.md against the analysed repo (stdlib only).

Usage:
  validate_report.py REPORT.md --root REPO_ROOT

Checks (errors fail the run, warnings do not):
  - structure: at least three level-2 sections; the first has a mermaid diagram;
    every level-3 flow in the second has one
  - evidence: every [FACT] line carries a `path:line` or `path:start-end`
    reference, and every reference resolves to a real file and line range
  - rule rows (first cell BR-<n>) carry exactly one of [FACT] [INFERRED] [UNKNOWN]
  - mermaid blocks start with a known diagram type
  - leftover template placeholders ({{...}})
  Heuristic warnings: Mermaid label patterns that often fail to compile, no
  [UNKNOWN] anywhere, flows without rule rows. It does NOT compile Mermaid and
  cannot judge whether the analysis is right.

Output: JSON on stdout {ok, errors[], warnings[], stats}.
Exit codes: 0 no errors, 1 validation errors, 2 bad arguments or unreadable file.
"""
import argparse
import json
import os
import re
import sys

DIAGRAMS = (
    "flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram", "classDiagram",
    "erDiagram", "journey", "gantt", "pie", "mindmap", "timeline", "gitGraph", "quadrantChart",
    "requirementDiagram", "C4Context", "block-beta", "sankey-beta",
)
REF = re.compile(r"`([^`\s:]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?`")
TAG = re.compile(r"\[(FACT|INFERRED|UNKNOWN)\]")
FENCE = re.compile(r"^\s*```\s*(\w[\w-]*)?\s*$")


def blank_comments(text):
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", "", m.group()), text, flags=re.S)


def parse(text):
    """Return lines, h2/h3 headings, mermaid blocks, with fenced code excluded from prose."""
    lines = text.split("\n")
    prose, mermaid, headings = {}, [], []
    fence_lang, block_start, block = None, 0, []
    for i, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m and fence_lang is None:
            fence_lang, block_start, block = (m.group(1) or ""), i, []
            continue
        if fence_lang is not None:
            if line.strip() == "```":
                if fence_lang == "mermaid":
                    mermaid.append({"start": block_start, "end": i, "lines": block})
                fence_lang = None
            else:
                block.append(line)
            continue
        prose[i] = line
        h = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
        if h:
            headings.append((i, len(h.group(1)), h.group(2)))
    return lines, prose, headings, mermaid


def mermaid_issues(block):
    """Yield (level, message) for one mermaid block's lines."""
    body = [l for l in block["lines"] if l.strip() and not l.strip().startswith("%%")]
    if body and body[0].strip() == "---":  # optional mermaid frontmatter
        rest = [b.strip() for b in body[1:]]
        if "---" in rest:
            body = body[rest.index("---") + 2:]
    if not body:
        yield "error", "empty mermaid block"
        return
    first = body[0].strip()
    kind = next((d for d in DIAGRAMS if first == d or first.startswith(d + " ")), None)
    if kind is None:
        yield "error", f"unknown mermaid diagram type: {first[:40]!r}. Start with one of: flowchart, sequenceDiagram, stateDiagram-v2, erDiagram, ..."
        return
    if kind in ("flowchart", "graph"):
        for l in body[1:]:
            if re.search(r"(-->|---|==>|-\.->|\|)\s*end\b(?![\w\"])|(^|\s)end\s*(-->|---|==>)", l):
                yield "warning", f"lowercase 'end' used as a node id/label: {l.strip()[:60]!r}; Mermaid reads it as a block end"
            for lab in re.findall(r"(?<![\[(])\[([^\[\]\"]+)\](?![\])])", l):
                if re.search(r"[()]", lab) and not (lab.startswith("(") and lab.endswith(")")):
                    yield "warning", f"unquoted label with parentheses will likely break: [{lab[:40]}]. Wrap it in double quotes."
            for lab in re.findall(r"\{([^{}\"]+)\}", l):
                if re.search(r"[()]", lab):
                    yield "warning", f"unquoted decision label with parentheses will likely break: {{{lab[:40]}}}. Wrap it in double quotes."


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a business-flow report.", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--root", required=True, help="root of the analysed repository (to resolve path:line references)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"Error: --root must be an existing directory. Received: {args.root!r}", file=sys.stderr)
        return 2
    try:
        with open(args.report, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as e:
        print(f"Error: cannot read report: {e}", file=sys.stderr)
        return 2

    root = os.path.realpath(args.root)
    errors, warnings = [], []
    err = lambda ln, msg: errors.append({"line": ln, "message": msg})
    warn = lambda ln, msg: warnings.append({"line": ln, "message": msg})

    text = blank_comments(raw)
    lines, prose, headings, mermaid = parse(text)

    for i, l in enumerate(lines, 1):
        if "{{" in l:
            err(i, "unresolved template placeholder {{...}}")

    if not any(level == 1 for _, level, _ in headings):
        warn(1, "no level-1 title")
    h2 = [(ln, t) for ln, lvl, t in headings if lvl == 2]
    if len(h2) < 3:
        err(1, f"need at least 3 level-2 sections (summary, flows, technical detail); found {len(h2)}")

    def section_end(start_line, level):
        for ln, lvl, _ in headings:
            if ln > start_line and lvl <= level:
                return ln
        return len(lines) + 1

    def blocks_in(a, b):
        return [m for m in mermaid if a < m["start"] < b]

    flows = []
    if len(h2) >= 1:
        a, b = h2[0][0], section_end(h2[0][0], 2)
        if not blocks_in(a, b):
            err(a, "first section (summary) has no mermaid diagram")
    if len(h2) >= 2:
        a, b = h2[1][0], section_end(h2[1][0], 2)
        flows = [(ln, t) for ln, lvl, t in headings if lvl == 3 and a < ln < b]
        if not flows:
            err(a, "second section (flows) has no level-3 flow headings")
        for ln, t in flows:
            end = section_end(ln, 3)
            if not blocks_in(ln, end):
                err(ln, f"flow {t!r} has no mermaid diagram")
            if not any(re.match(r"^\|\s*BR-\d+\s*\|", prose.get(k, "")) for k in range(ln, end)):
                warn(ln, f"flow {t!r} has no business-rule rows (BR-<n>)")

    for m in mermaid:
        for level, msg in mermaid_issues(m):
            (err if level == "error" else warn)(m["start"], msg)

    stats = {"flows": len(flows), "mermaid_blocks": len(mermaid), "rules": 0, "FACT": 0, "INFERRED": 0, "UNKNOWN": 0, "references": 0}
    line_counts = {}

    def line_count(path):
        if path not in line_counts:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                line_counts[path] = sum(1 for _ in fh)
        return line_counts[path]

    for i, l in prose.items():
        tags = TAG.findall(l)
        for t in tags:
            stats[t] += 1
        refs = REF.findall(l)
        for path, a, b in refs:
            stats["references"] += 1
            full = os.path.realpath(os.path.join(root, path))
            if not full.startswith(root + os.sep):
                err(i, f"reference escapes the repo root: {path}")
            elif not os.path.isfile(full):
                err(i, f"referenced file not found: {path}")
            else:
                n, lo = line_count(full), int(a)
                hi = int(b) if b else lo
                if lo < 1 or hi < lo or hi > n:
                    err(i, f"bad line range {path}:{a}{'-' + b if b else ''} (file has {n} lines)")
        if "[FACT]" in l and not refs:
            err(i, "[FACT] without a `path:line` reference; add one or downgrade to [INFERRED]")
        cells = [c.strip() for c in l.strip().strip("|").split("|")] if l.lstrip().startswith("|") else []
        if cells and re.fullmatch(r"BR-\d+", cells[0]):
            stats["rules"] += 1
            if len(tags) != 1:
                err(i, f"rule {cells[0]} must carry exactly one of [FACT] [INFERRED] [UNKNOWN]; found {len(tags)}")
            elif tags[0] == "INFERRED" and (len(cells) < 4 or cells[-1].lower() in ("", "none", "-", "n/a")):
                err(i, f"rule {cells[0]} is [INFERRED] but the evidence column does not say what it rests on")
            elif tags[0] == "UNKNOWN" and "?" not in l:
                warn(i, f"rule {cells[0]} is [UNKNOWN]; phrase it as a question")

    if stats["UNKNOWN"] == 0:
        warn(1, "no [UNKNOWN] items anywhere; a real analysis from code alone nearly always has open questions")
    if stats["rules"] and stats["FACT"] == 0:
        warn(1, "no [FACT] items; check that rules are tied to code lines")

    result = {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
