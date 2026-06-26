#!/usr/bin/env python3
"""Build the standalone ThinkFree Hosting and Deployment Guide HTML.

Reuses the Markdown->HTML converter from build_pdf.py (DRY) and assembles a
hosting-specific cover + table of contents, then writes one HTML file ready for
Chrome headless --print-to-pdf. Run from the docs_build directory so `import
build_pdf` resolves.
"""
import html
import os

import build_pdf   # reuse convert(), inline(), slug()

build_pdf._slug_seen = {}   # fresh slug counter for this document

SRC = os.path.join(os.path.dirname(__file__), "hosting_sections")
OUT = os.path.join(os.path.dirname(__file__), "ThinkFree_Hosting_Guide.html")


def main():
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".md"))
    toc = []
    parts = []
    for f in files:
        with open(os.path.join(SRC, f), encoding="utf-8") as fh:
            parts.append('<section class="part">' + build_pdf.convert(fh.read(), toc) + "</section>")
    body = "\n".join(parts)

    toc_html = ['<nav class="toc"><h1 class="toc-title">Contents</h1>']
    for level, txt, sid in toc:
        cls = "toc-l1" if level == 1 else "toc-l2"
        toc_html.append(f'<div class="{cls}"><a href="#{sid}">{html.escape(txt)}</a></div>')
    toc_html.append("</nav>")
    toc_html = "\n".join(toc_html)

    css = """
    @page { size: A4; margin: 18mm 15mm 20mm 15mm; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
           font-size: 10.7pt; line-height: 1.55; color: #1a1a1a; margin: 0; }
    .cover { height: 247mm; display: flex; flex-direction: column; justify-content: center;
             page-break-after: always; text-align: center; }
    .cover .brand { font-size: 13pt; letter-spacing: 3px; color: #2563eb; font-weight: 700; text-transform: uppercase; }
    .cover h1 { font-size: 30pt; margin: 14px 40px; border: none; color: #0f172a; line-height: 1.2; }
    .cover .sub { font-size: 13pt; color: #475569; margin: 6px 0 28px; }
    .cover .rule { width: 120px; height: 3px; background: #2563eb; margin: 20px auto; }
    .cover .meta { font-size: 10pt; color: #64748b; margin-top: 30px; }
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
    p { margin: 6px 0; }
    a { color: #1d4ed8; }
    code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 9pt;
           background: #f1f5f9; padding: 1px 4px; border-radius: 3px; color: #b91c1c; }
    pre { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 6px;
          font-size: 8.7pt; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; page-break-inside: auto; }
    pre code { background: none; color: #e2e8f0; padding: 0; font-size: 8.7pt; }
    table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9pt; }
    th, td { border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; vertical-align: top; }
    th { background: #eff6ff; color: #1e3a8a; font-weight: 700; }
    tr { page-break-inside: avoid; }
    ul, ol { margin: 6px 0; padding-left: 22px; }
    li { margin: 2px 0; }
    hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
    """

    cover = """
    <div class="cover">
      <div class="brand">ThinkFree Finance</div>
      <h1>Hosting &amp; Deployment Guide</h1>
      <div class="rule"></div>
      <div class="sub">Step by step: host the app, connect it to a server,<br/>and run it from the GitHub repo as the backend</div>
      <div class="meta">Covers local run, data build, GitHub deploy (Render / Railway),<br/>Cloudflare, scheduled data refresh, and the pre launch security checklist</div>
    </div>
    """

    doc = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>'
        '<title>ThinkFree Finance Hosting and Deployment Guide</title>'
        f"<style>{css}</style></head><body>{cover}{toc_html}{body}</body></html>"
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Wrote {OUT} ({len(doc)} bytes, {len(toc)} TOC entries)")


if __name__ == "__main__":
    main()
