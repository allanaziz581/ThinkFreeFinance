"""ThinkFree - minify generated data files for production.

The build scripts emit pretty-printed JSON for readability. For a fast-loading
hosted site, run this once before deploy to strip the whitespace from every
window.*_DATA file (~30-40% smaller raw, faster to parse). Code files are left
alone. Safe + idempotent: it only recompacts JSON values, never changes data.

Run:  ./tf_env/bin/python webapp/minify_data.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"
# code files (not data) - never touch
CODE = {"app.js", "scores.js", "genimpact.js", "scoreinfo.js", "predictions.js",
        "glossary.js", "congress.js", "influenceweb.js"}
_ASSIGN = re.compile(r"window\.\w+\s*=\s*")


def compact(txt):
    dec = json.JSONDecoder()
    out, idx = [], 0
    for m in _ASSIGN.finditer(txt):
        try:
            val, end = dec.raw_decode(txt, m.end())
        except ValueError:
            continue
        out.append(txt[idx:m.end()])
        out.append(json.dumps(val, separators=(",", ":"), ensure_ascii=False))
        idx = end
    out.append(txt[idx:])
    return "".join(out)


def main():
    total_before = total_after = 0
    for f in sorted(JS.glob("*.js")):
        if f.name in CODE:
            continue
        txt = f.read_text(encoding="utf-8")
        if "window." not in txt:
            continue
        new = compact(txt)
        before, after = len(txt), len(new)
        if after < before:
            f.write_text(new, encoding="utf-8")
            total_before += before; total_after += after
            print(f"  {f.name:26} {before//1024:>5}KB -> {after//1024:>5}KB")
    if total_before:
        print(f"\nminified data: {total_before//1024} KB -> {total_after//1024} KB "
              f"({100 - total_after * 100 // total_before}% smaller raw)")
    else:
        print("nothing to minify (already compact)")


if __name__ == "__main__":
    main()
