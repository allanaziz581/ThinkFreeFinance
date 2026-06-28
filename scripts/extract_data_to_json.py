"""extract_data_to_json.py

One-time / repeatable migration step. Converts the public webapp/js/*_data.js
bundles (each of the form `window.NAME = {...};`) into plain JSON files under
private_data/, which the server serves only to authenticated users.

It writes:
  private_data/<GLOBAL_NAME>.json   for each dataset
  private_data/manifest.json        classifying datasets as core / lazy / live

It does NOT delete the originals from webapp/js (so the current static app keeps
working during the transition). Once the front-end fetches from /api/data/*, you
can remove the *_data.js files from webapp/js; the server already refuses to
serve them either way.

Run with any working Python 3 (only the standard library is used):
  python3 scripts/extract_data_to_json.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "webapp" / "js"
OUT_DIR = ROOT / "private_data"

# Source files grouped by how the front-end uses them:
#   core  - needed to render the app right after login (sent in one bundle)
#   lazy  - large; fetched only when the State Legislature view is opened
#   live  - refreshed on the user's tier cadence (prices + news)
CATEGORIES = {
    "core": [
        "data.js", "influence_data.js", "relationships_data.js", "nonprofit_data.js",
        "fec_data.js", "sec_data.js", "secbulk_data.js", "usaspending_data.js",
        "states_data.js", "sp500_data.js", "quant_data.js", "member_bills.js",
        "presidential_data.js",
    ],
    "lazy": ["legiscan_data.js", "openstates_data.js"],
    "live": ["prices_data.js", "news_intel.js"],
}

# Use search (not match) so a leading `// AUTO-GENERATED ...` comment line that
# the builders prepend doesn't break parsing. (\w+) keeps the captured global
# name to [A-Za-z0-9_], so it can never produce a path-traversing output name.
ASSIGN_RE = re.compile(r"window\.(\w+)\s*=\s*(.*);\s*$", re.S)


def extract_one(js_path: Path) -> tuple[str, object]:
    """Return (global_name, parsed_value) for a `window.NAME = <json>;` file."""
    text = js_path.read_text(encoding="utf-8")
    m = ASSIGN_RE.search(text)
    if not m:
        raise ValueError(f"{js_path.name}: not a 'window.NAME = {{...}};' file")
    name, value = m.group(1), m.group(2)
    return name, json.loads(value)   # json.loads validates it is real JSON


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    manifest: dict[str, list[str]] = {"core": [], "lazy": [], "live": []}

    for category, files in CATEGORIES.items():
        for fname in files:
            src = JS_DIR / fname
            if not src.exists():
                print(f"  SKIP (missing): {fname}")
                continue
            name, value = extract_one(src)
            out = OUT_DIR / f"{name}.json"
            out.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
            manifest[category].append(name)
            print(f"  {category:5} {fname:24} -> private_data/{name}.json")

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(len(v) for v in manifest.values())
    print(f"\nWrote {total} datasets + manifest.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
