"""ThinkFree - Data Centers & cost-of-living pressure.

Tracks the U.S. data-center buildout and its documented link to higher LOCAL cost
of living. Hyperscale data centers compete with households for two scarce local
resources - electricity and water - and for land near transmission, which can push
up electricity rates, water costs, and home/rent prices in the host county.

HONEST DATA NOTE
----------------
There is no clean single public API for per-project hyperscale data-center
proposals - that information lives in county zoning filings and local news and is
manually curated. So this builder ships the AUTOMATABLE national version:

  * Cost-of-living side  -> LIVE from the U.S. Census ACS (county rent / income /
                            population). Reuses the CENSUS_API_KEY already in .env.
  * Power / electricity  -> U.S. EIA. LIVE if EIA_API_KEY is set in .env; otherwise
                            falls back to EIA-published 2024 state averages bundled
                            below (clearly attributed). Set EIA_API_KEY to go live.
  * Data-center locations-> a curated, source-attributed SEED list of major U.S.
                            data-center counties. The schema is extensible: drop in
                            more counties (e.g. a per-Florida-county curation) by
                            adding rows to SEED_DATA_CENTERS - nothing else changes.

RISK SCORE (every input + weight is visible; see METHODOLOGY in the output)
  buildout_risk = power_availability*0.30 + water_capacity*0.15
                + land_availability*0.15 + datacenter_exposure*0.40
Each input is normalized to 0-100. A higher score = more attractive to further
data-center buildout = more upward pressure on local cost of living.

This is INFORMATIONAL and sourced from public records. It does not allege
wrongdoing by any company or jurisdiction.

Writes webapp/js/datacenters_data.js  (window.DATACENTERS).

Run:  ./tf_env/bin/python webapp/build_datacenters.py
Docs: https://www.eia.gov/opendata/  |  https://www.census.gov/data/developers.html
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "datacenters_data.js"
ACS_YEAR = 2023  # latest ACS 5-year vintage (reliable at county level)


def _env(name: str):
    try:
        for _l in open(ROOT / ".env", encoding="utf-8"):
            if _l.startswith(name + "="):
                return _l.strip().split("=", 1)[1] or None
    except OSError:
        pass
    return None


CENSUS_KEY = _env("CENSUS_API_KEY")
EIA_KEY = _env("EIA_API_KEY")

# --- ACS variables: median rent, median household income, population ---------
ACS_VARS = {
    "B25064_001E": "median_rent",
    "B19013_001E": "median_household_income",
    "B01003_001E": "population",
}

# --- EIA published 2024 average RESIDENTIAL retail price (cents/kWh) ----------
# Offline reference used only when EIA_API_KEY is absent. Source: EIA Electric
# Power Monthly / State Electricity Profiles (2024 averages). Clearly attributed
# in the output as such; set EIA_API_KEY in .env to fetch these live instead.
EIA_2024_PRICE_CENTS = {
    "CA": 31.8, "VA": 14.1, "TX": 15.3, "AZ": 14.6, "IL": 16.2, "WA": 11.3,
    "OH": 16.0, "GA": 14.2, "OR": 12.4, "NV": 15.1, "UT": 11.6, "NC": 13.5,
    "NY": 24.6, "FL": 15.0, "US": 16.4,
}
# EIA 2024 total net electricity generation (TWh, all sources). Used as a coarse
# "power availability" proxy (more in-state generation = more headroom to host
# new load). Source: EIA State Electricity Profiles 2024.
EIA_2024_GEN_TWH = {
    "CA": 197, "VA": 96, "TX": 564, "AZ": 119, "IL": 184, "WA": 109,
    "OH": 154, "GA": 134, "OR": 64, "NV": 44, "UT": 41, "NC": 137,
    "NY": 132, "FL": 263,
}

# --- Curated state water-availability index (0-100; higher = more available) -
# A coarse, documented proxy derived from USGS water-use and WRI Aqueduct
# baseline water-stress categories (low stress -> high availability). This is the
# one input with no clean per-county API; it is intentionally transparent and
# easy to refine. Higher = less water-constrained.
WATER_AVAILABILITY = {
    "CA": 25, "VA": 78, "TX": 40, "AZ": 12, "IL": 80, "WA": 88,
    "OH": 82, "GA": 70, "OR": 80, "NV": 10, "UT": 18, "NC": 76,
    "NY": 84, "FL": 60,
}

STATE_NAME = {
    "CA": "California", "VA": "Virginia", "TX": "Texas", "AZ": "Arizona",
    "IL": "Illinois", "WA": "Washington", "OH": "Ohio", "GA": "Georgia",
    "OR": "Oregon", "NV": "Nevada", "UT": "Utah", "NC": "North Carolina",
    "NY": "New York", "FL": "Florida",
}

# --- Curated SEED list of major U.S. data-center counties --------------------
# Counts are approximate, curated from public sources (Data Center Map, Baxtel,
# county economic-development records) as of early 2026. The schema is the
# extension point: add counties (incl. a future per-Florida-county curation) by
# appending rows. fips = state+county FIPS (used to join Census ACS).
SEED_DATA_CENTERS = [
    {"county": "Loudoun County", "state": "VA", "fips": "51107", "dc_count": 115,
     "land_area_sqmi": 516, "hub": "Data Center Alley"},
    {"county": "Prince William County", "state": "VA", "fips": "51153", "dc_count": 42,
     "land_area_sqmi": 336, "hub": "Northern Virginia"},
    {"county": "Fairfax County", "state": "VA", "fips": "51059", "dc_count": 38,
     "land_area_sqmi": 391, "hub": "Northern Virginia"},
    {"county": "Santa Clara County", "state": "CA", "fips": "06085", "dc_count": 55,
     "land_area_sqmi": 1291, "hub": "Silicon Valley"},
    {"county": "Maricopa County", "state": "AZ", "fips": "04013", "dc_count": 48,
     "land_area_sqmi": 9224, "hub": "Phoenix"},
    {"county": "Dallas County", "state": "TX", "fips": "48113", "dc_count": 40,
     "land_area_sqmi": 871, "hub": "Dallas-Fort Worth"},
    {"county": "Tarrant County", "state": "TX", "fips": "48439", "dc_count": 22,
     "land_area_sqmi": 864, "hub": "Dallas-Fort Worth"},
    {"county": "Cook County", "state": "IL", "fips": "17031", "dc_count": 45,
     "land_area_sqmi": 945, "hub": "Chicago"},
    {"county": "King County", "state": "WA", "fips": "53033", "dc_count": 28,
     "land_area_sqmi": 2116, "hub": "Seattle"},
    {"county": "Franklin County", "state": "OH", "fips": "39049", "dc_count": 24,
     "land_area_sqmi": 532, "hub": "Columbus / New Albany"},
    {"county": "Fulton County", "state": "GA", "fips": "13121", "dc_count": 26,
     "land_area_sqmi": 528, "hub": "Atlanta"},
    {"county": "Umatilla County", "state": "OR", "fips": "41059", "dc_count": 12,
     "land_area_sqmi": 3215, "hub": "Eastern Oregon"},
    {"county": "Clark County", "state": "NV", "fips": "32003", "dc_count": 20,
     "land_area_sqmi": 7891, "hub": "Las Vegas"},
    {"county": "Salt Lake County", "state": "UT", "fips": "49035", "dc_count": 14,
     "land_area_sqmi": 742, "hub": "Salt Lake City"},
    {"county": "Mecklenburg County", "state": "NC", "fips": "37119", "dc_count": 16,
     "land_area_sqmi": 524, "hub": "Charlotte"},
]

# Risk-score weights (sum to 1.0). Surfaced verbatim in the methodology panel.
WEIGHTS = {"power": 0.30, "water": 0.15, "land": 0.15, "exposure": 0.40}


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def eia_price_live(state: str):
    """Live residential retail price (cents/kWh) for a state, or None."""
    if not EIA_KEY:
        return None
    url = ("https://api.eia.gov/v2/electricity/retail-sales/data/?"
           + urllib.parse.urlencode({
               "api_key": EIA_KEY, "frequency": "annual", "data[0]": "price",
               "facets[sectorid][]": "RES", "facets[stateid][]": state,
               "sort[0][column]": "period", "sort[0][direction]": "desc", "length": 1}))
    if not url.startswith("https://api.eia.gov/"):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            rows = json.load(r).get("response", {}).get("data", [])
        return round(float(rows[0]["price"]), 2) if rows else None
    except (urllib.error.URLError, KeyError, ValueError, IndexError):
        return None


def fetch_census_counties():
    """One ACS5 call for all counties; returns {fips: {field: value}}."""
    if not CENSUS_KEY:
        print("  WARN: CENSUS_API_KEY missing - cost-of-living fields will be null")
        return {}
    cols = ",".join(ACS_VARS)
    url = (f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get=NAME,{cols}"
           f"&for=county:*&in=state:*&key={CENSUS_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            rows = json.load(r)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  WARN: Census ACS fetch failed: {e}")
        return {}
    header = rows[0]
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for row in rows[1:]:
        fips = row[idx["state"]] + row[idx["county"]]
        rec = {}
        for var, field in ACS_VARS.items():
            try:
                rec[field] = float(row[idx[var]])
            except (ValueError, KeyError, TypeError):
                rec[field] = None
        out[fips] = rec
    return out


def main():
    print("Building Data Centers dataset (Census ACS + EIA + curated locations)...")
    census = fetch_census_counties()
    print(f"  Census counties fetched: {len(census)}")

    # resolve electricity price per state (live EIA if keyed, else 2024 table)
    eia_live = bool(EIA_KEY)
    price_src = "EIA live API" if eia_live else "EIA 2024 published averages (offline ref)"
    state_price = {}
    for st in STATE_NAME:
        p = eia_price_live(st) if eia_live else None
        state_price[st] = p if p is not None else EIA_2024_PRICE_CENTS.get(st)

    max_dc = max(r["dc_count"] for r in SEED_DATA_CENTERS) or 1

    regions = []
    for r in SEED_DATA_CENTERS:
        st = r["state"]
        acs = census.get(r["fips"], {})
        pop = acs.get("population")
        rent = acs.get("median_rent")
        inc = acs.get("median_household_income")

        # ---- risk inputs (each normalized 0-100) ----
        gen = EIA_2024_GEN_TWH.get(st, 0)
        power = clamp(gen / 564 * 100)                 # TX (564 TWh) anchors the top
        water = float(WATER_AVAILABILITY.get(st, 50))
        density = (pop / r["land_area_sqmi"]) if (pop and r["land_area_sqmi"]) else None
        # land availability: lower density = more land. ~2000/sq mi -> 0; rural -> 100
        land = clamp(100 - (density / 2000 * 100)) if density is not None else 50.0
        exposure = clamp(r["dc_count"] / max_dc * 100)

        risk = round(power * WEIGHTS["power"] + water * WEIGHTS["water"]
                     + land * WEIGHTS["land"] + exposure * WEIGHTS["exposure"], 1)

        rent_burden = round(rent * 12 / inc * 100, 1) if (rent and inc) else None
        regions.append({
            "county": r["county"], "state": st, "state_name": STATE_NAME.get(st, st),
            "fips": r["fips"], "hub": r["hub"], "dc_count": r["dc_count"],
            "population": pop, "median_rent": rent, "median_household_income": inc,
            "rent_burden_pct": rent_burden,
            "electricity_cents_kwh": state_price.get(st),
            "inputs": {
                "power_availability": round(power, 1),
                "water_capacity": round(water, 1),
                "land_availability": round(land, 1),
                "datacenter_exposure": round(exposure, 1),
                "pop_density_sqmi": round(density, 1) if density is not None else None,
            },
            "buildout_risk": risk,
        })
        print(f"  + {r['county'][:22]:24} {st}  risk {risk:5}  DCs {r['dc_count']:3}  "
              f"{state_price.get(st)}c/kWh  rent ${rent or 0:.0f}")

    regions.sort(key=lambda x: x["buildout_risk"], reverse=True)

    methodology = {
        "summary": ("Buildout risk estimates how attractive a county is to further "
                    "data-center development, and therefore how much upward pressure "
                    "that buildout could place on local electricity, water, and "
                    "housing costs. Higher = more pressure."),
        "formula": "risk = 0.30*power + 0.15*water + 0.15*land + 0.40*exposure",
        "weights": WEIGHTS,
        "inputs": {
            "power_availability": "In-state net electricity generation (EIA), normalized 0-100.",
            "water_capacity": "Curated state water-availability index from USGS water-use + WRI Aqueduct baseline stress (0-100, higher = less constrained).",
            "land_availability": "Inverse of county population density (Census ACS population / county land area).",
            "datacenter_exposure": "Existing data-center count in the county, normalized to the most-saturated county in the set.",
        },
        "cost_of_living_link": ("Electricity rate (EIA) and rent burden (Census ACS "
                                "median rent / median household income) are shown per "
                                "county so the cost-of-living side is directly visible."),
    }

    data = {
        "sources": [
            "U.S. Census Bureau ACS 5-year " + str(ACS_YEAR),
            price_src,
            "Data-center locations: curated from public records (Data Center Map, "
            "Baxtel, county economic-development filings)",
            "Water: USGS water-use + WRI Aqueduct (curated index)",
        ],
        "source_urls": [
            "https://www.census.gov/programs-surveys/acs",
            "https://www.eia.gov/electricity/",
        ],
        "disclaimer": ("Informational, compiled from public records. Estimates and "
                       "curated figures - not a substitute for official filings. Does "
                       "not allege wrongdoing by any company or jurisdiction."),
        "eia_live": eia_live,
        "acs_year": ACS_YEAR,
        "methodology": methodology,
        "regions": regions,
        "count": len(regions),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_datacenters.py "
                "(Census ACS + EIA + curated locations). No API key stored here.\n")
        f.write("window.DATACENTERS = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) - {len(regions)} regions, "
          f"electricity src: {price_src}")


if __name__ == "__main__":
    main()
