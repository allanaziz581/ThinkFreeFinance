"""ThinkFree - Presidential actions & news feed.

A dedicated feed of presidential activity from official primary sources:
  * Federal Register API (free, no key) - executive orders, proclamations, memos.
  * Federal Register trade/tariff notices (free) - the tariff-action layer.
  * Congress.gov (CONGRESS_API_KEY) - enacted/signed public laws.
  * RSS news filtered for presidential keywords - secondary "color" layer.

Honest freshness: the Federal Register publishes on business days; executive
orders appear there a few days AFTER signing (we surface signing_date when
available). Congress.gov updates ~daily. Daily-cadence feed, not real-time.

Writes webapp/js/presidential_data.js (window.PRESIDENTIAL). CONGRESS_API_KEY is
read from .env and never written to output or logs.
Run: ./tf_env/bin/python webapp/build_presidential.py
Docs: https://www.federalregister.gov/developers/documentation/api/v1
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "presidential_data.js"
FR_BASE = "https://www.federalregister.gov/api/v1/documents.json"
CONGRESS_BASE = "https://api.congress.gov/v3"
MAX_BYTES = 16 * 1024 * 1024
UA = {"User-Agent": "ThinkFree/1.0", "Accept": "application/json"}

CONGRESS_KEY = ""
_env = ROOT / ".env"
if _env.exists():
    for _line in open(_env, encoding="utf-8"):
        if _line.startswith("CONGRESS_API_KEY="):
            CONGRESS_KEY = _line.strip().split("=", 1)[1]
            break
CONGRESS_KEY = CONGRESS_KEY or os.environ.get("CONGRESS_API_KEY", "")

CATEGORY_KEYWORDS = {
    "Trade/Tariffs":   ["tariff", "section 301", "section 232", "trade deficit", "import duty", "customs", "ustr"],
    "Technology":      ["quantum", "artificial intelligence", " ai ", "semiconductor", "chip", "cyber", "cryptograph", "crypto", "broadband"],
    "Defense/Security":["defense", "military", "national security", "nato", "sanction", "missile", "terror", "homeland"],
    "Energy":          ["energy", "oil", "gas", "drilling", "nuclear", "pipeline", "power grid", "electric"],
    "Healthcare":      ["health", "drug pric", "medicare", "medicaid", "fda", "pharma", "hospital"],
    "Immigration":     ["immigration", "border", "visa", "asylum", "migrant", "refugee"],
    "Economy/Finance": ["bank", "financial", "inflation", " tax", "budget", "deficit", "small business", "labor"],
    "Environment":     ["climate", "environment", "emission", " epa ", "wildlife", "fishing", "clean water"],
}
SECTOR_KEYWORDS = {
    "Technology":  ["quantum", "semiconductor", "chip", "artificial intelligence", "cyber", "broadband", "crypto"],
    "Energy":      ["energy", "oil", "gas", "nuclear", "pipeline", "electric", "grid"],
    "Financials":  ["bank", "financial", "tax", "lending", "credit"],
    "Healthcare":  ["health", "drug", "medicare", "medicaid", "pharma", "fda"],
    "Defense":     ["defense", "military", "missile", "weapon", "homeland"],
    "Industrials": ["manufactur", "infrastructure", "steel", "aluminum", "construction"],
    "Consumer":    ["consumer", "retail", "grocery", "housing", "auto"],
}


def classify(text: str) -> tuple[str, list[str]]:
    t = f" {text.lower()} "
    category = "General"
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in t for k in kws):
            category = cat
            break
    sectors = [s for s, kws in SECTOR_KEYWORDS.items() if any(k in t for k in kws)]
    return category, sectors[:4]


def safe_url(u: str) -> str:
    u = (u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def http_json(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("response too large")
        return json.loads(body.decode())


_FR_FIELDS = ("&fields[]=title&fields[]=type&fields[]=publication_date&fields[]=signing_date"
              "&fields[]=html_url&fields[]=document_number&fields[]=executive_order_number&fields[]=abstract")


def fetch_fr(pdtype: str, label: str, per_page: int) -> list[dict]:
    url = (f"{FR_BASE}?conditions[presidential_document_type][]={pdtype}"
           f"&order=newest&per_page={per_page}{_FR_FIELDS}")
    try:
        d = http_json(url)
    except Exception as e:
        print(f"[presidential] FR {label} fetch failed: {type(e).__name__}: {str(e)[:90]}")
        return []
    items = []
    for it in d.get("results", []):
        title = (it.get("title") or "").strip()
        url_o = safe_url(it.get("html_url") or "")
        if not title or not url_o:
            continue
        abstract = (it.get("abstract") or "").strip()
        category, sectors = classify(title + " " + abstract)
        items.append({
            "id": f"fr-{it.get('document_number','')}", "type": label, "title": title,
            "date": (it.get("signing_date") or it.get("publication_date") or ""),
            "summary": abstract[:400], "url": url_o, "source": "Federal Register",
            "category": category, "sectors": sectors, "eo_number": it.get("executive_order_number"),
        })
    return items


def fetch_tariffs(per_page: int) -> list[dict]:
    url = (f"{FR_BASE}?conditions[term]={urllib.parse.quote('tariff')}"
           f"&conditions[type][]=NOTICE&conditions[type][]=RULE&order=newest&per_page={per_page}{_FR_FIELDS}")
    try:
        d = http_json(url)
    except Exception as e:
        print(f"[presidential] FR tariff fetch failed: {type(e).__name__}: {str(e)[:90]}")
        return []
    items = []
    for it in d.get("results", []):
        title = (it.get("title") or "").strip()
        url_o = safe_url(it.get("html_url") or "")
        if not title or not url_o:
            continue
        abstract = (it.get("abstract") or "").strip()
        _, sectors = classify(title + " " + abstract)
        items.append({
            "id": f"fr-{it.get('document_number','')}", "type": "tariff_action", "title": title,
            "date": (it.get("publication_date") or ""), "summary": abstract[:400], "url": url_o,
            "source": "Federal Register", "category": "Trade/Tariffs",
            "sectors": sectors or ["Industrials"], "eo_number": None,
        })
    return items


def fetch_laws(per_page: int) -> list[dict]:
    if not CONGRESS_KEY:
        print("[presidential] CONGRESS_API_KEY not set - skipping signed laws.")
        return []
    url = f"{CONGRESS_BASE}/law/119?format=json&limit={per_page}&api_key={CONGRESS_KEY}"
    try:
        d = http_json(url)
    except Exception as e:
        print(f"[presidential] Congress laws fetch failed: {type(e).__name__}: {str(e)[:90]}")
        return []
    items = []
    for b in d.get("bills", []):
        title = (b.get("title") or "").strip()
        laws = b.get("laws") or [{}]
        lawnum = laws[0].get("number", "") if laws else ""
        latest = b.get("latestAction", {}) or {}
        num = b.get("number", "")
        btype = (b.get("type") or "").lower()
        congress = b.get("congress", 119)
        url_o = safe_url(f"https://www.congress.gov/bill/{congress}th-congress/{'house-bill' if btype=='hr' else 'senate-bill'}/{num}") if num else ""
        if not title or not url_o:
            continue
        category, sectors = classify(title)
        items.append({
            "id": f"law-{lawnum or num}", "type": "signed_law", "title": title,
            "date": latest.get("actionDate", ""),
            "summary": (f"Public Law {lawnum}. " if lawnum else "") + (latest.get("text", "") or "")[:300],
            "url": url_o, "source": "Congress.gov", "category": category, "sectors": sectors, "eo_number": None,
        })
    return items


def fetch_news(limit: int) -> list[dict]:
    try:
        import feedparser
    except Exception:
        return []
    q = urllib.parse.quote('president OR "White House" OR "executive order" OR tariff OR veto')
    feed_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    KW = ("president", "white house", "executive order", "tariff", "veto", "proclamation", "signs bill", "memorandum")
    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "ThinkFree/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return []
        f = feedparser.parse(body)
    except Exception:
        return []
    items = []
    for e in f.entries[:limit * 3]:
        title = (e.get("title") or "").strip()[:300]
        link = safe_url(e.get("link") or "")
        if not title or not link or not any(k in title.lower() for k in KW):
            continue
        category, sectors = classify(title)
        src = (e.get("source", {}) or {}).get("title", "News") if isinstance(e.get("source"), dict) else "News"
        items.append({
            "id": "news-" + hashlib.sha1(link.encode()).hexdigest()[:12], "type": "news", "title": title,
            "date": (e.get("published", "")[:16] or ""), "summary": "", "url": link,
            "source": str(src)[:80], "category": category, "sectors": sectors, "eo_number": None,
        })
        if len(items) >= limit:
            break
    return items


def main() -> int:
    items: list[dict] = []
    items += fetch_fr("executive_order", "executive_order", 40)
    items += fetch_fr("proclamation", "proclamation", 30)
    items += fetch_fr("memorandum", "memo", 20)
    items += fetch_tariffs(20)
    items += fetch_laws(20)
    # RSS news layer intentionally dropped: it pulled in irrelevant "president"
    # items (foreign presidents, church news, op-eds). The official Federal
    # Register documents and signed laws above are the accurate US-executive feed.
    # items += fetch_news(15)

    seen, deduped = set(), []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        deduped.append(it)
    deduped.sort(key=lambda x: x.get("date") or "", reverse=True)

    counts: dict[str, int] = {}
    for it in deduped:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    if not deduped:
        print("[presidential] no items fetched - leaving existing data unchanged.")
        return 1

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": ("Official actions are sourced from the Federal Register and Congress.gov. "
                       "News items are third-party reports included for context, not official records."),
        "counts": counts, "items": deduped,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".js.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_presidential.py - do not edit by hand.\n")
        f.write("window.PRESIDENTIAL = ")
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    tmp.replace(OUT)
    print(f"[presidential] wrote {len(deduped)} items ({', '.join(f'{k}:{v}' for k, v in counts.items())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
