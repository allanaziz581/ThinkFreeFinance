"""ThinkFree Web Front-End — Politician Photo Fetcher.

The front-end looks for headshots at:  webapp/assets/politicians/{bioguide}.jpg

The bioguide IDs come from politician_parties.json. This script pulls official,
public-domain congressional portraits from the @unitedstates project image
collection (https://github.com/unitedstates/images), which is keyed by the same
bioguide IDs we already have — far cleaner than cropping the GPO PDF grid.

Run:  python webapp/fetch_politician_photos.py

(Offline fallback: if you must use the GPO-PICTDIR-118 PDFs in PoliticianImages.zip,
those have several members per page and need a PDF renderer + face crop step —
install `pip install pymupdf` and render pages, then crop. The bioguide route below
is recommended and requires no extra dependencies.)
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "assets" / "politicians"

# Source: @unitedstates/images — public-domain official portraits, by bioguide id.
SOURCES = [
    "https://unitedstates.github.io/images/congress/450x550/{bg}.jpg",
    "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/450x550/{bg}.jpg",
]


def bioguide_ids():
    parties = json.load(open(ROOT / "politician_parties.json", encoding="utf-8"))
    ids = {}
    for name, meta in parties.items():
        if isinstance(meta, dict) and meta.get("bioguide"):
            ids[meta["bioguide"]] = name
    return ids


def fetch(bg: str) -> bytes | None:
    for tmpl in SOURCES:
        url = tmpl.format(bg=bg)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    data = r.read()
                    if data and len(data) > 1000:
                        return data
        except Exception:
            continue
    return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = bioguide_ids()
    print(f"Fetching {len(ids)} politician photos -> {OUT_DIR}")
    ok = miss = skip = 0
    for bg, name in ids.items():
        dest = OUT_DIR / f"{bg}.jpg"
        if dest.exists() and dest.stat().st_size > 1000:
            skip += 1
            continue
        data = fetch(bg)
        if data:
            dest.write_bytes(data)
            ok += 1
            print(f"  ✓ {name} ({bg})")
        else:
            miss += 1
            print(f"  ✗ {name} ({bg}) — not found")
        time.sleep(0.15)
    print(f"\nDone. downloaded={ok} cached={skip} missing={miss}")
    if miss and ok == 0:
        print("No photos fetched — likely offline. Front-end will show initials placeholders.")


if __name__ == "__main__":
    main()
