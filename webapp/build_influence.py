"""ThinkFree InfluenceWeb - LittleSis relationship extractor.

The full LittleSis dump (entities.json.gz ~73MB, relationships.json.gz ~105MB)
is far too large to ship. This streams both files and extracts ONLY the slice
that connects to companies already in ThinkFree (the tickers in data.js):
real board members, executives, owners, and donors.

Output: webapp/js/influence_data.js  ->  window.IW_DATA = {...}

Run:  ./tf_env/bin/python webapp/build_influence.py
  (expects the two .gz files in ~/Downloads)
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import ijson

ROOT = Path(__file__).resolve().parent.parent
DL = Path.home() / "Downloads"
ENTITIES = DL / "entities.json.gz"
RELATIONSHIPS = DL / "relationships.json.gz"
OUT = Path(__file__).resolve().parent / "js" / "influence_data.js"

# LittleSis category ids
CAT_POSITION = 1
CAT_DONATION = 5
CAT_OWNERSHIP = 10
CAT_LOBBYING = 7


def norm(t: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (t or "").upper())


def our_tickers() -> set:
    txt = open(ROOT / "webapp" / "js" / "data.js", encoding="utf-8").read()
    d = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    tks = set()
    for b in d.get("bills", []):
        tks.update(b.get("tickers", []))
    for t in d.get("recent_trades", []):
        if t.get("ticker"):
            tks.add(t["ticker"])
    for c in (d.get("correlation", {}) or {}).get("top_bills", []):
        tks.update(c.get("tickers", []))
    return tks


def main():
    if not ENTITIES.exists() or not RELATIONSHIPS.exists():
        print(f"ERROR: expected {ENTITIES} and {RELATIONSHIPS}")
        return

    target_norm = {norm(t): t for t in our_tickers()}
    print(f"Matching {len(target_norm)} ThinkFree tickers against LittleSis...")

    # ---- pass 1: entities ----
    id_name = {}            # entity id -> name (all entities, for resolving people)
    ticker_to_id = {}       # our ticker -> entity id
    id_to_ticker = {}       # entity id -> our ticker
    company_meta = {}       # our ticker -> {blurb, website, employees, ...}
    count = 0

    def domain_of(url):
        if not url:
            return ""
        m = re.search(r"https?://(?:www\.)?([^/]+)", url)
        return m.group(1) if m else ""

    with gzip.open(ENTITIES, "rb") as f:
        for e in ijson.items(f, "item"):
            count += 1
            attrs = e.get("attributes", {})
            eid = attrs.get("id")
            nm = attrs.get("name")
            if eid is None:
                continue
            id_name[eid] = nm
            ext = attrs.get("extensions", {}) or {}
            pc = ext.get("PublicCompany", {}) or {}
            org = ext.get("Org", {}) or {}
            tk = pc.get("ticker")
            if tk:
                key = norm(tk)
                if key in target_norm and target_norm[key] not in ticker_to_id:
                    ours = target_norm[key]
                    ticker_to_id[ours] = eid
                    id_to_ticker[eid] = ours
                    company_meta[ours] = {
                        "blurb": attrs.get("blurb") or "",
                        "website": attrs.get("website") or "",
                        "domain": domain_of(attrs.get("website")),
                        "employees": org.get("employees"),
                        "revenue": org.get("revenue"),
                        "fedspending_id": org.get("fedspending_id"),
                        "lda_registrant_id": org.get("lda_registrant_id"),
                    }
            if count % 100000 == 0:
                print(f"  entities scanned: {count:,}  matched companies: {len(ticker_to_id)}")
    print(f"  entities total: {count:,}  matched companies: {len(ticker_to_id)}")

    target_ids = set(id_to_ticker.keys())

    # ---- pass 2: relationships ----
    companies = {}
    for tk, eid in ticker_to_id.items():
        meta = company_meta.get(tk, {})
        companies[tk] = {
            "name": id_name.get(eid, tk), "entity_id": eid,
            "blurb": meta.get("blurb", ""), "website": meta.get("website", ""),
            "domain": meta.get("domain", ""), "employees": meta.get("employees"),
            "revenue": meta.get("revenue"), "fedspending_id": meta.get("fedspending_id"),
            "lda_registrant_id": meta.get("lda_registrant_id"),
            "board": [], "executives": [], "owners": [], "donors_in": [],
        }
    rcount = kept = 0
    with gzip.open(RELATIONSHIPS, "rb") as f:
        for r in ijson.items(f, "item"):
            rcount += 1
            a = r.get("attributes", {})
            e1, e2 = a.get("entity1_id"), a.get("entity2_id")
            cat = a.get("category_id")
            # company is usually entity2 for positions/ownership; check both
            comp_id = e2 if e2 in target_ids else (e1 if e1 in target_ids else None)
            if comp_id is None:
                continue
            person_id = e1 if comp_id == e2 else e2
            tk = id_to_ticker[comp_id]
            ca = a.get("category_attributes", {}) or {}
            person = id_name.get(person_id) or f"Entity {person_id}"
            title = a.get("description1") or a.get("description") or ""
            if cat == CAT_POSITION:
                rec = {"name": person, "title": title[:60], "current": bool(a.get("is_current"))}
                if ca.get("is_board"):
                    if len(companies[tk]["board"]) < 14:
                        companies[tk]["board"].append(rec)
                        kept += 1
                elif ca.get("is_executive"):
                    if len(companies[tk]["executives"]) < 10:
                        companies[tk]["executives"].append(rec)
                        kept += 1
            elif cat == CAT_OWNERSHIP and len(companies[tk]["owners"]) < 8:
                companies[tk]["owners"].append({"name": person, "title": title[:50]})
                kept += 1
            elif cat == CAT_DONATION and len(companies[tk]["donors_in"]) < 8:
                amt = a.get("amount")
                companies[tk]["donors_in"].append({"name": person, "amount": amt})
                kept += 1
            if rcount % 200000 == 0:
                print(f"  relationships scanned: {rcount:,}  kept: {kept}")
    print(f"  relationships total: {rcount:,}  kept: {kept}")

    # keep all matched companies (board data OR company metadata is useful)

    out = {
        "source": "LittleSis (littlesis.org) - aggregate public relationship data",
        "companies": companies,
        "company_count": len(companies),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_influence.py from LittleSis data.\n")
        f.write("window.IW_DATA = ")
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT}  ({OUT.stat().st_size//1024} KB)  companies with data: {len(companies)}")


if __name__ == "__main__":
    main()
