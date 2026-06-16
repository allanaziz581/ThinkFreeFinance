"""ThinkFree - State economic data (Constituent Accountability Layer).

Pulls per-state economics from FRED (St. Louis Fed) and computes ThinkFree
Constituent Prosperity Score + Constituent Pressure Score for all 50 states + DC.
Writes webapp/js/states_data.js (window.STATES_DATA).

FRED_API_KEY read from .env. FRED state series used:
  {ST}UR        unemployment rate
  {ST}STHPI     all-transactions house price index (level + YoY growth)
  MEHOINUS{ST}A672N  real median household income
  {ST}PCPI      per-capita personal income (level + YoY growth)

Run:  ./tf_env/bin/python webapp/build_states.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "states_data.js"

KEY = None
for _l in open(ROOT / ".env", encoding="utf-8"):
    if _l.startswith("FRED_API_KEY="):
        KEY = _l.strip().split("=", 1)[1]

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}


def fred(series, limit=8):
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={series}"
           f"&api_key={KEY}&file_type=json&sort_order=desc&limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("observations", [])
    except Exception:
        return []


def latest(obs):
    for o in obs:
        try:
            return float(o["value"]), o["date"]
        except (ValueError, KeyError):
            continue
    return None, None


def yoy(obs):
    """Year-over-year % change from monthly/quarterly obs (desc order)."""
    vals = []
    for o in obs:
        try:
            vals.append((o["date"], float(o["value"])))
        except (ValueError, KeyError):
            continue
    if len(vals) < 5:
        return None
    cur = vals[0][1]
    # ~4 quarters back (quarterly) or use last available
    prev = vals[min(4, len(vals) - 1)][1]
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def main():
    if not KEY:
        print("ERROR: FRED_API_KEY missing")
        return
    print(f"Fetching FRED economics for {len(STATES)} states...")
    out = {}
    # national medians for relative scoring
    for st, name in STATES.items():
        ur_obs = fred(f"{st}UR", 4)
        hpi_obs = fred(f"{st}STHPI", 8)
        pcpi_obs = fred(f"{st}PCPI", 6)
        inc_obs = fred(f"MEHOINUS{st}A672N", 3)

        unemp, _ = latest(ur_obs)
        hpi, _ = latest(hpi_obs)
        hpi_growth = yoy(hpi_obs)
        pcpi, _ = latest(pcpi_obs)
        pcpi_growth = yoy(pcpi_obs)
        med_income, _ = latest(inc_obs)

        out[st] = {
            "name": name,
            "unemployment": unemp,
            "house_price_index": hpi,
            "house_price_growth": hpi_growth,
            "per_capita_income": pcpi,
            "income_growth": pcpi_growth,
            "median_household_income": med_income,
        }
        print(f"  + {st} {name[:16]:18} unemp {unemp} | HPI {hpi} (+{hpi_growth}%) | inc ${med_income}")
        time.sleep(0.15)

    # ---- compute ThinkFree scores (relative to the 51-jurisdiction set) ----
    def col(k):
        return [v[k] for v in out.values() if isinstance(v.get(k), (int, float))]
    inc_vals, unemp_vals = col("median_household_income"), col("unemployment")
    inc_min, inc_max = (min(inc_vals), max(inc_vals)) if inc_vals else (0, 1)
    for st, v in out.items():
        inc = v.get("median_household_income")
        unemp = v.get("unemployment")
        incg = v.get("income_growth") or 0
        hpg = v.get("house_price_growth") or 0
        # Prosperity: higher income, lower unemployment, positive income growth
        prosperity = 0
        if inc is not None and inc_max > inc_min:
            prosperity += (inc - inc_min) / (inc_max - inc_min) * 45
        if unemp is not None:
            prosperity += clamp((7 - unemp) / 7 * 35, 0, 35)
        prosperity += clamp(incg * 3, -10, 20)
        v["prosperity_score"] = round(clamp(prosperity))
        # Pressure: house prices rising faster than incomes = stress
        pressure = clamp((hpg - incg) * 6, 0, 60)
        if unemp is not None:
            pressure += clamp((unemp - 3.5) * 6, 0, 25)
        pressure += clamp((hpg) * 1.2, 0, 15)
        v["pressure_score"] = round(clamp(pressure))

    data = {"source": "FRED (Federal Reserve Economic Data)", "byState": out, "count": len(out)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_states.py (FRED). No API key stored here.\n")
        f.write("window.STATES_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} states")


if __name__ == "__main__":
    main()
