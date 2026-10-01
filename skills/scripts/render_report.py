#!/usr/bin/env python3
"""Render a business-flow report.md into one self-contained HTML file (stdlib only).

Usage:
  render_report.py REPORT.md --output REPORT.html [--lang en|id] [--mermaid-url URL]

Each level-2 heading becomes a tab; each level-3 heading a section (with a
side index when a tab has two or more). ```mermaid blocks become diagrams
(rendered in the browser by Mermaid loaded from a CDN, so viewing them needs
internet; without it the diagram source is shown instead). [FACT], [INFERRED]
and [UNKNOWN] become colour-coded badges.

Supported Markdown: headings, paragraphs, bullet/numbered lists (nested),
tables, fenced code, blockquotes, rules, `code`, **bold**, *italic*, links.

Options:
  --output FILE      HTML file to write (required).
  --lang en|id       Language of the badge legend and html lang (default en).
  --mermaid-url URL  Mermaid script URL (default: pinned jsDelivr build).

Exit codes: 0 ok, 2 bad arguments or unreadable input.
"""
import argparse
import html
import os
import re
import sys

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
LEGEND = {
    "en": {"label": "How to read the tags", "tabs": "Report sections", "fallback": "Diagram could not load (needs internet). Diagram source:",
           "FACT": "Verified in code", "INFERRED": "Inferred, not enforced in code read", "UNKNOWN": "Needs confirmation"},
    "id": {"label": "Cara membaca tag", "tabs": "Bagian laporan", "fallback": "Diagram tidak dapat dimuat (perlu internet). Sumber diagram:",
           "FACT": "Terbukti di kode", "INFERRED": "Disimpulkan, tidak ditegakkan di kode yang dibaca", "UNKNOWN": "Perlu konfirmasi"},
}
REF = re.compile(r"^[^\s:]+\.[A-Za-z0-9]+:\d+(?:-\d+)?$")
ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def esc(s):
    return html.escape(s, quote=True)


def inline(text):
    text = esc(text)
    codes = []

    def stash(m):
        body = m.group(1)
        cls = ' class="ref"' if REF.match(html.unescape(body)) else ""
        codes.append(f"<code{cls}>{body}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = re.sub(r"\[(FACT|INFERRED|UNKNOWN)\]", lambda m: f'<span class="badge {m.group(1).lower()}">{m.group(1)}</span>', text)

    def link(m):
        url = html.unescape(m.group(2))
        if not re.match(r"^(https?://|#|[\w./-]+$)", url):
            return m.group(0)
        return f'<a href="{esc(url)}">{m.group(1)}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def parse_blocks(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.split("\n")
    blocks, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^\s*```\s*([\w-]*)\s*$", line)
        if m:
            i += 1
            body = []
            while i < n and lines[i].strip() != "```":
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", m.group(1), "\n".join(body)))
            continue
        m = re.match(r"^(#{1,4})\s+(.+?)\s*#*\s*$", line)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2)))
            i += 1
            continue
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            blocks.append(("hr",))
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < n and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            header = split_row(line)
            i += 2
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            blocks.append(("table", header, rows))
            continue
        if line.lstrip().startswith(">"):
            body = []
            while i < n and lines[i].lstrip().startswith(">"):
                body.append(lines[i].lstrip()[1:].strip())
                i += 1
            blocks.append(("quote", " ".join(body)))
            continue
        if ITEM.match(line):
            root, stack = [], []
            while i < n and lines[i].strip():
                im = ITEM.match(lines[i])
                if im:
                    node = {"indent": len(im.group(1)), "ordered": im.group(2)[0].isdigit(), "text": im.group(3), "children": []}
                    while stack and stack[-1]["indent"] >= node["indent"]:
                        stack.pop()
                    (stack[-1]["children"] if stack else root).append(node)
                    stack.append(node)
                elif stack and lines[i].startswith(" "):
                    stack[-1]["text"] += " " + lines[i].strip()
                else:
                    break
                i += 1
            blocks.append(("list", root))
            continue
        para = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,4}\s|\s*```|\s*>|\s*\|)", lines[i]) and not ITEM.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            blocks.append(("p", " ".join(para)))
        else:
            i += 1  # defensive: never loop forever on odd input
    return blocks


def render_list(nodes):
    out, k = [], 0
    while k < len(nodes):
        ordered = nodes[k]["ordered"]
        group = []
        while k < len(nodes) and nodes[k]["ordered"] == ordered:
            group.append(nodes[k])
            k += 1
        tag = "ol" if ordered else "ul"
        items = "".join(f"<li>{inline(g['text'])}{render_list(g['children']) if g['children'] else ''}</li>" for g in group)
        out.append(f"<{tag}>{items}</{tag}>")
    return "".join(out)


def render_block(b, fallback):
    kind = b[0]
    if kind == "p":
        return f"<p>{inline(b[1])}</p>"
    if kind == "list":
        return render_list(b[1])
    if kind == "quote":
        return f"<blockquote>{inline(b[1])}</blockquote>"
    if kind == "hr":
        return "<hr>"
    if kind == "h":
        lvl = min(b[1], 4)
        return f"<h{lvl}>{inline(b[2])}</h{lvl}>"
    if kind == "table":
        head = "".join(f"<th scope='col'>{inline(c)}</th>" for c in b[1])
        body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in b[2])
        return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    if kind == "code":
        if b[1] == "mermaid":
            return f'<figure class="diagram" data-fallback="{esc(fallback)}"><pre class="mermaid">{esc(b[2])}</pre></figure>'
        cls = f' class="language-{esc(b[1])}"' if b[1] else ""
        return f"<pre><code{cls}>{esc(b[2])}</code></pre>"
    return ""


def slugify(text, seen):
    base = re.sub(r"[^\w]+", "-", re.sub(r"`", "", text).lower(), flags=re.U).strip("-") or "section"
    slug, k = base, 2
    while slug in seen:
        slug, k = f"{base}-{k}", k + 1
    seen.add(slug)
    return slug


def build(blocks, labels):
    title, intro, panels, seen = "Business flow report", [], [], set()
    cur = None
    for b in blocks:
        if b[0] == "h" and b[1] == 1 and cur is None and title == "Business flow report":
            title = re.sub(r"[`*]", "", b[2])
        elif b[0] == "h" and b[1] == 2:
            cur = {"title": b[2], "id": "tab-" + slugify(b[2], seen), "items": []}
            panels.append(cur)
        elif cur is None:
            intro.append(b)
        else:
            cur["items"].append(b)
    return title, intro, panels


def render_panel(p, idx, labels, seen):
    parts, toc, open_section = [], [], False
    parts.append(f"<h2>{inline(p['title'])}</h2>")
    for b in p["items"]:
        if b[0] == "h" and b[1] == 3:
            if open_section:
                parts.append("</section>")
            sid = slugify(b[2], seen)
            toc.append((sid, b[2]))
            parts.append(f'<section class="flow" id="{sid}"><h3>{inline(b[2])}</h3>')
            open_section = True
        else:
            parts.append(render_block(b, labels["fallback"]))
    if open_section:
        parts.append("</section>")
    has_toc = len(toc) >= 2
    toc_html = ""
    if has_toc:
        toc_html = '<aside class="toc"><ol>' + "".join(f'<li><a href="#{sid}">{inline(t)}</a></li>' for sid, t in toc) + "</ol></aside>"
    cls = "panel" + ("" if has_toc else " no-toc") + (" active" if idx == 0 else "")
    return f'<div class="{cls}" role="tabpanel" id="{p["id"]}" aria-labelledby="{p["id"]}-btn"><div class="content">{"".join(parts)}</div>{toc_html}</div>'


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a business-flow report to HTML.", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--output", required=True)
    ap.add_argument("--lang", choices=sorted(LEGEND), default="en")
    ap.add_argument("--mermaid-url", default=MERMAID_URL)
    args = ap.parse_args(argv)
    try:
        with open(args.report, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"Error: cannot read report: {e}", file=sys.stderr)
        return 2
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "report-template.html")
    try:
        with open(tpl_path, encoding="utf-8") as fh:
            tpl = fh.read()
    except OSError as e:
        print(f"Error: cannot read HTML template at {tpl_path}: {e}", file=sys.stderr)
        return 2

    labels = LEGEND[args.lang]
    title, intro, panels = build(parse_blocks(text), labels)
    if not panels:
        print("Error: report has no level-2 headings (## ...); nothing to turn into tabs. Run validate_report.py for details.", file=sys.stderr)
        return 2
    seen = {p["id"] for p in panels}
    panel_html = "\n".join(render_panel(p, i, labels, seen) for i, p in enumerate(panels))
    tabs_html = "".join(
        f'<button role="tab" id="{p["id"]}-btn" aria-controls="{p["id"]}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{inline(p["title"])}</button>'
        for i, p in enumerate(panels)
    )
    legend_html = "".join(f'<li><span class="badge {k.lower()}">{k}</span>{esc(labels[k])}</li>' for k in ("FACT", "INFERRED", "UNKNOWN"))
    intro_html = f'<div class="lede">{"".join(render_block(b, labels["fallback"]) for b in intro)}</div>' if intro else ""

    out = tpl
    for key, val in {
        "__LANG__": args.lang, "__TITLE__": esc(title), "__INTRO__": intro_html, "__LEGEND_LABEL__": esc(labels["label"]),
        "__LEGEND__": legend_html, "__TABS_LABEL__": esc(labels["tabs"]), "__TABS__": tabs_html, "__PANELS__": panel_html,
        "__MERMAID_URL__": esc(args.mermaid_url),
    }.items():
        out = out.replace(key, val)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"Wrote {args.output}: {len(panels)} tabs, {len(re.findall(r'class=.mermaid.', out))} diagrams.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
