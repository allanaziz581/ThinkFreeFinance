#!/usr/bin/env python3
"""Assemble the ThinkFree architecture sections into one styled HTML document.

Stdlib only. Converts a practical subset of GitHub-flavored Markdown
(headings, fenced code, inline code, bold/italic, links, pipe tables,
ordered/unordered lists with one level of nesting, blockquotes, hr) into HTML,
builds a cover page and an auto-generated clickable table of contents, then
writes a single HTML file ready for Chrome headless --print-to-pdf.
"""

import html
import os
import re
import sys

SECTIONS_DIR = os.path.join(os.path.dirname(__file__), "sections")
OUT_HTML = os.path.join(os.path.dirname(__file__), "ThinkFree_Architecture.html")

_slug_seen = {}


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    n = _slug_seen.get(s, 0)
    _slug_seen[s] = n + 1
    return s if n == 0 else f"{s}-{n}"


def inline(text):
    """Inline markdown -> HTML on a single line. Escapes HTML first, protecting
    code spans from emphasis/link processing."""
    # Protect code spans
    spans = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)
    # Links [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
                  text)
    # Bold then italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\*])\*([^*\n]+)\*(?![\*])", r"<em>\1</em>", text)
    # Restore code spans (escaped)
    def unstash(m):
        return f"<code>{html.escape(spans[int(m.group(1))], quote=False)}</code>"
    text = re.sub(r"\x00(\d+)\x00", unstash, text)
    return text


def convert(md, toc):
    out = []
    lines = md.split("\n")
    i = 0
    n = len(lines)
    in_code = False
    code_buf = []

    def close_lists(stack):
        while stack:
            out.append(f"</{stack.pop()}>")

    list_stack = []  # list of (tag, indent)

    while i < n:
        line = lines[i]

        # Fenced code
        if line.lstrip().startswith("```"):
            if not in_code:
                close_lists([t for t, _ in list_stack]); list_stack = []
                in_code = True
                code_buf = []
            else:
                in_code = False
                code = html.escape("\n".join(code_buf), quote=False)
                out.append(f"<pre><code>{code}</code></pre>")
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Blank line
        if not stripped:
            close_lists([t for t, _ in list_stack]); list_stack = []
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(---+|\*\*\*+)$", stripped):
            close_lists([t for t, _ in list_stack]); list_stack = []
            out.append("<hr/>")
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_lists([t for t, _ in list_stack]); list_stack = []
            level = len(m.group(1))
            txt = m.group(2).strip()
            sid = slug(txt)
            if level in (1, 2):
                toc.append((level, txt, sid))
            out.append(f'<h{level} id="{sid}">{inline(txt)}</h{level}>')
            i += 1
            continue

        # Table: header line with | then a separator line
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            close_lists([t for t, _ in list_stack]); list_stack = []
            def cells(row):
                row = row.strip()
                if row.startswith("|"):
                    row = row[1:]
                if row.endswith("|"):
                    row = row[:-1]
                return [c.strip() for c in row.split("|")]
            header = cells(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            t = ['<table><thead><tr>']
            t += [f"<th>{inline(c)}</th>" for c in header]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        # Blockquote
        if stripped.startswith(">"):
            close_lists([t for t, _ in list_stack]); list_stack = []
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
            continue

        # Lists (one level of nesting via indentation)
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            indent = len(m.group(1))
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            tag = "ol" if ordered else "ul"
            if not list_stack:
                list_stack.append((tag, indent))
                out.append(f"<{tag}>")
            else:
                cur_tag, cur_indent = list_stack[-1]
                if indent > cur_indent + 1:
                    list_stack.append((tag, indent))
                    out.append(f"<{tag}>")
                elif indent < cur_indent:
                    while list_stack and list_stack[-1][1] > indent:
                        out.append(f"</{list_stack.pop()[0]}>")
                    if not list_stack:
                        list_stack.append((tag, indent))
                        out.append(f"<{tag}>")
            out.append(f"<li>{inline(m.group(3))}</li>")
            i += 1
            continue

        # Paragraph (gather consecutive plain lines)
        close_lists([t for t, _ in list_stack]); list_stack = []
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|\s*[-*]\s|\s*\d+\.\s|>)", lines[i]) and "|" not in lines[i]:
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")

    close_lists([t for t, _ in list_stack])
    if in_code and code_buf:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>")
    return "\n".join(out)


def main():
    files = sorted(f for f in os.listdir(SECTIONS_DIR) if f.endswith(".md"))
    toc = []
    body_parts = []
    for f in files:
        with open(os.path.join(SECTIONS_DIR, f), encoding="utf-8") as fh:
            md = fh.read()
        body_parts.append('<section class="part">' + convert(md, toc) + "</section>")
    body = "\n".join(body_parts)

    # Build TOC HTML
    toc_html = ['<nav class="toc"><h1 class="toc-title">Table of Contents</h1>']
    for level, txt, sid in toc:
        cls = "toc-l1" if level == 1 else "toc-l2"
        toc_html.append(f'<div class="{cls}"><a href="#{sid}">{html.escape(txt)}</a></div>')
    toc_html.append("</nav>")
    toc_html = "\n".join(toc_html)

    css = """
    @page { size: A4; margin: 18mm 15mm 20mm 15mm; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
           font-size: 10.5pt; line-height: 1.5; color: #1a1a1a; margin: 0; }
    .cover { height: 247mm; display: flex; flex-direction: column; justify-content: center;
             page-break-after: always; text-align: center; }
    .cover .brand { font-size: 13pt; letter-spacing: 3px; color: #2563eb; font-weight: 700; text-transform: uppercase; }
    .cover h1 { font-size: 30pt; margin: 14px 40px; border: none; color: #0f172a; line-height: 1.2; }
    .cover .sub { font-size: 13pt; color: #475569; margin: 6px 0 28px; }
    .cover .meta { font-size: 10pt; color: #64748b; margin-top: 30px; }
    .cover .rule { width: 120px; height: 3px; background: #2563eb; margin: 20px auto; }
    .cover .conf { margin-top: 40px; font-size: 9pt; color: #94a3b8; }
    .toc { page-break-after: always; }
    .toc-title { font-size: 20pt; }
    .toc-l1 { font-weight: 700; margin: 9px 0 3px; font-size: 11pt; }
    .toc-l2 { margin: 2px 0 2px 18px; font-size: 9.5pt; color: #334155; }
    .toc a { color: #1e3a8a; text-decoration: none; }
    h1 { font-size: 19pt; color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 5px;
         margin-top: 8px; page-break-before: always; page-break-after: avoid; }
    .toc h1, .cover h1 { page-break-before: avoid; }
    h2 { font-size: 14pt; color: #1d4ed8; margin-top: 18px; page-break-after: avoid; border-bottom: 1px solid #dbeafe; padding-bottom: 3px; }
    h3 { font-size: 11.5pt; color: #1e293b; margin-top: 13px; page-break-after: avoid; }
    h4 { font-size: 10.5pt; color: #334155; margin-top: 10px; }
    p { margin: 6px 0; }
    a { color: #1d4ed8; }
    code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 9pt;
           background: #f1f5f9; padding: 1px 4px; border-radius: 3px; color: #b91c1c; }
    pre { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 6px;
          overflow-x: auto; font-size: 8.5pt; line-height: 1.45; white-space: pre-wrap;
          word-wrap: break-word; page-break-inside: auto; }
    pre code { background: none; color: #e2e8f0; padding: 0; font-size: 8.5pt; }
    table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9pt; }
    th, td { border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; vertical-align: top; }
    th { background: #eff6ff; color: #1e3a8a; font-weight: 700; }
    tr { page-break-inside: avoid; }
    tr:nth-child(even) td { background: #f8fafc; }
    blockquote { border-left: 4px solid #2563eb; margin: 8px 0; padding: 4px 12px;
                 background: #f8fafc; color: #334155; font-style: italic; }
    ul, ol { margin: 6px 0 6px 0; padding-left: 22px; }
    li { margin: 2px 0; }
    hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
    .part { }
    """

    cover = """
    <div class="cover">
      <div class="brand">ThinkFree Finance</div>
      <h1>Architecture &amp; Engineering Methodology</h1>
      <div class="rule"></div>
      <div class="sub">A complete technical reference of the platform,<br/>its pipeline, sub-agents, and data architecture</div>
      <div class="meta">
        Prepared for engineering review &middot; Generated from a direct reading of the source tree<br/>
        AI Financial Intelligence Platform &mdash; research analyst, not a trading bot
      </div>
      <div class="conf">CONFIDENTIAL &mdash; for prospective engineers and collaborators</div>
    </div>
    """

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>ThinkFree Finance — Architecture & Methodology</title>
<style>{css}</style></head>
<body>{cover}{toc_html}{body}</body></html>"""

    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Wrote {OUT_HTML} ({len(doc)} bytes, {len(toc)} TOC entries)")


if __name__ == "__main__":
    main()
