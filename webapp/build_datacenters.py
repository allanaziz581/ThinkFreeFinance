"""ThinkFree - Data Centers & cost-of-living pressure.

Tracks the U.S. data-center buildout and its documented link to higher LOCAL cost
of living. Hyperscale data centers compete with households for two scarce local
resources, electricity and water, and for land near transmission, which can push
up electricity rates, water costs, and home/rent prices in the host county.

DATA SOURCES
------------
  * Cost-of-living side  -> LIVE from the U.S. Census ACS (county rent / income /
                            population). Reuses the CENSUS_API_KEY already in .env.
  * Power / electricity  -> U.S. EIA. LIVE if EIA_API_KEY is set in .env; otherwise
                            falls back to EIA-published state averages bundled below
                            (clearly attributed). Set EIA_API_KEY to go live.
  * Data-center locations-> TWO layers, merged by county FIPS:
       (a) a curated, source-attributed SEED list of major U.S. data-center
           counties (accurate counts for the marquee markets), and
       (b) a LIVE pull from OpenStreetMap (Overpass API) of every feature tagged
           telecom=data_center / man_made=data_center in the U.S., each mapped to
           its county via the FCC area API. The lat/lon -> county lookups are
           cached on disk (datacenters_geo_cache.json) so re-runs are fast.
    The OSM layer is best-effort: if Overpass or the FCC API is unreachable, the
    curated layer alone still ships. OSM is community-tagged and under-counts dense
    markets, so where both layers see a county the larger (curated) count wins.

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
      https://wiki.openstreetmap.org/wiki/Tag:telecom%3Ddata_center
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "datacenters_data.js"
GEO_CACHE = ROOT / "datacenters_geo_cache.json"   # lat/lon -> county FIPS (committed; speeds the cron)
ACS_YEAR = 2023  # latest ACS 5-year vintage (reliable at county level)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
FCC_BLOCK = "https://geo.fcc.gov/api/census/block/find"


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

# --- EIA published average RESIDENTIAL retail price (cents/kWh), ~2024 --------
# Offline reference used when EIA_API_KEY is absent. Source: EIA Electric Power
# Monthly / State Electricity Profiles. Curated approximations, attributed in the
# output. Set EIA_API_KEY in .env to fetch the keyed states live instead.
EIA_PRICE_CENTS = {
    "AL": 15.5, "AK": 24.5, "AZ": 14.6, "AR": 12.8, "CA": 31.8, "CO": 15.0,
    "CT": 28.5, "DE": 16.5, "DC": 17.0, "FL": 15.0, "GA": 14.2, "HI": 41.0,
    "ID": 11.5, "IL": 16.2, "IN": 15.5, "IA": 14.0, "KS": 14.0, "KY": 12.5,
    "LA": 12.0, "ME": 23.0, "MD": 17.5, "MA": 29.0, "MI": 18.5, "MN": 14.5,
    "MS": 13.0, "MO": 12.5, "MT": 12.5, "NE": 11.5, "NV": 15.1, "NH": 23.0,
    "NJ": 18.0, "NM": 14.0, "NY": 24.6, "NC": 13.5, "ND": 11.0, "OH": 16.0,
    "OK": 12.0, "OR": 12.4, "PA": 17.5, "RI": 27.0, "SC": 14.5, "SD": 13.0,
    "TN": 12.5, "TX": 15.3, "UT": 11.6, "VT": 21.0, "VA": 14.1, "WA": 11.3,
    "WV": 14.5, "WI": 17.0, "WY": 12.5, "US": 16.4,
}
# EIA net electricity generation (TWh, all sources, ~2023). Coarse "power
# availability" proxy: more in-state generation = more headroom for new load.
EIA_GEN_TWH = {
    "AL": 150, "AK": 6, "AZ": 119, "AR": 65, "CA": 197, "CO": 60, "CT": 42,
    "DE": 7, "DC": 1, "FL": 263, "GA": 134, "HI": 9, "ID": 17, "IL": 184,
    "IN": 96, "IA": 75, "KS": 50, "KY": 70, "LA": 110, "ME": 12, "MD": 37,
    "MA": 28, "MI": 117, "MN": 60, "MS": 75, "MO": 78, "MT": 30, "NE": 42,
    "NV": 44, "NH": 19, "NJ": 70, "NM": 38, "NY": 132, "NC": 137, "ND": 45,
    "OH": 154, "OK": 90, "OR": 64, "PA": 240, "RI": 8, "SC": 100, "SD": 17,
    "TN": 90, "TX": 564, "UT": 41, "VT": 2, "VA": 96, "WA": 109, "WV": 60,
    "WI": 65, "WY": 45, "US": 80,
}
# Curated state water-availability index (0-100; higher = more available), a
# documented proxy from USGS water-use + WRI Aqueduct baseline water-stress.
WATER_AVAILABILITY = {
    "AL": 78, "AK": 95, "AZ": 12, "AR": 75, "CA": 25, "CO": 30, "CT": 85,
    "DE": 80, "DC": 78, "FL": 60, "GA": 70, "HI": 70, "ID": 45, "IL": 80,
    "IN": 80, "IA": 72, "KS": 35, "KY": 82, "LA": 80, "ME": 90, "MD": 82,
    "MA": 85, "MI": 88, "MN": 82, "MS": 80, "MO": 75, "MT": 55, "NE": 50,
    "NV": 10, "NH": 88, "NJ": 78, "NM": 12, "NY": 84, "NC": 76, "ND": 55,
    "OH": 82, "OK": 40, "OR": 80, "PA": 82, "RI": 85, "SC": 75, "SD": 55,
    "TN": 80, "TX": 40, "UT": 18, "VT": 88, "VA": 78, "WA": 88, "WV": 82,
    "WI": 84, "WY": 40, "US": 50,
}
STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

# --- Curated SEED list of major U.S. data-center counties --------------------
# Counts are approximate, curated from public sources (Data Center Map, Baxtel,
# county economic-development records) as of early 2026. fips = state+county FIPS
# (joins Census ACS). land_area_sqmi drives the land/density input; where it is
# null the land input falls back to a neutral 50.
SEED_DATA_CENTERS = [
    {"county": "Loudoun County", "state": "VA", "fips": "51107", "dc_count": 115, "land_area_sqmi": 516, "hub": "Data Center Alley"},
    {"county": "Prince William County", "state": "VA", "fips": "51153", "dc_count": 42, "land_area_sqmi": 336, "hub": "Northern Virginia"},
    {"county": "Fairfax County", "state": "VA", "fips": "51059", "dc_count": 38, "land_area_sqmi": 391, "hub": "Northern Virginia"},
    {"county": "Henrico County", "state": "VA", "fips": "51087", "dc_count": 12, "land_area_sqmi": 234, "hub": "Richmond"},
    {"county": "Chesterfield County", "state": "VA", "fips": "51041", "dc_count": 6, "land_area_sqmi": 423, "hub": "Richmond"},
    {"county": "Santa Clara County", "state": "CA", "fips": "06085", "dc_count": 55, "land_area_sqmi": 1291, "hub": "Silicon Valley"},
    {"county": "Los Angeles County", "state": "CA", "fips": "06037", "dc_count": 35, "land_area_sqmi": 4058, "hub": "Los Angeles"},
    {"county": "San Bernardino County", "state": "CA", "fips": "06071", "dc_count": 14, "land_area_sqmi": 20057, "hub": "Inland Empire"},
    {"county": "Sacramento County", "state": "CA", "fips": "06067", "dc_count": 10, "land_area_sqmi": 965, "hub": "Sacramento"},
    {"county": "Alameda County", "state": "CA", "fips": "06001", "dc_count": 12, "land_area_sqmi": 739, "hub": "Bay Area"},
    {"county": "San Diego County", "state": "CA", "fips": "06073", "dc_count": 12, "land_area_sqmi": 4207, "hub": "San Diego"},
    {"county": "Maricopa County", "state": "AZ", "fips": "04013", "dc_count": 48, "land_area_sqmi": 9224, "hub": "Phoenix"},
    {"county": "Pinal County", "state": "AZ", "fips": "04021", "dc_count": 6, "land_area_sqmi": 5374, "hub": "Phoenix"},
    {"county": "Dallas County", "state": "TX", "fips": "48113", "dc_count": 40, "land_area_sqmi": 871, "hub": "Dallas-Fort Worth"},
    {"county": "Tarrant County", "state": "TX", "fips": "48439", "dc_count": 22, "land_area_sqmi": 864, "hub": "Dallas-Fort Worth"},
    {"county": "Harris County", "state": "TX", "fips": "48201", "dc_count": 30, "land_area_sqmi": 1703, "hub": "Houston"},
    {"county": "Travis County", "state": "TX", "fips": "48453", "dc_count": 14, "land_area_sqmi": 989, "hub": "Austin"},
    {"county": "Bexar County", "state": "TX", "fips": "48029", "dc_count": 12, "land_area_sqmi": 1240, "hub": "San Antonio"},
    {"county": "Collin County", "state": "TX", "fips": "48085", "dc_count": 8, "land_area_sqmi": 841, "hub": "Dallas-Fort Worth"},
    {"county": "Cook County", "state": "IL", "fips": "17031", "dc_count": 45, "land_area_sqmi": 945, "hub": "Chicago"},
    {"county": "DuPage County", "state": "IL", "fips": "17043", "dc_count": 12, "land_area_sqmi": 327, "hub": "Chicago"},
    {"county": "Will County", "state": "IL", "fips": "17197", "dc_count": 8, "land_area_sqmi": 837, "hub": "Chicago"},
    {"county": "King County", "state": "WA", "fips": "53033", "dc_count": 28, "land_area_sqmi": 2116, "hub": "Seattle"},
    {"county": "Grant County", "state": "WA", "fips": "53025", "dc_count": 12, "land_area_sqmi": 2680, "hub": "Quincy"},
    {"county": "Douglas County", "state": "WA", "fips": "53017", "dc_count": 4, "land_area_sqmi": 1819, "hub": "East Washington"},
    {"county": "Franklin County", "state": "OH", "fips": "39049", "dc_count": 24, "land_area_sqmi": 532, "hub": "Columbus / New Albany"},
    {"county": "Licking County", "state": "OH", "fips": "39089", "dc_count": 6, "land_area_sqmi": 687, "hub": "New Albany"},
    {"county": "Hamilton County", "state": "OH", "fips": "39061", "dc_count": 8, "land_area_sqmi": 407, "hub": "Cincinnati"},
    {"county": "Fulton County", "state": "GA", "fips": "13121", "dc_count": 26, "land_area_sqmi": 528, "hub": "Atlanta"},
    {"county": "Gwinnett County", "state": "GA", "fips": "13135", "dc_count": 8, "land_area_sqmi": 430, "hub": "Atlanta"},
    {"county": "Douglas County", "state": "GA", "fips": "13097", "dc_count": 8, "land_area_sqmi": 200, "hub": "Atlanta"},
    {"county": "Umatilla County", "state": "OR", "fips": "41059", "dc_count": 12, "land_area_sqmi": 3215, "hub": "Eastern Oregon"},
    {"county": "Morrow County", "state": "OR", "fips": "41049", "dc_count": 8, "land_area_sqmi": 2049, "hub": "Boardman"},
    {"county": "Crook County", "state": "OR", "fips": "41013", "dc_count": 6, "land_area_sqmi": 2980, "hub": "Prineville"},
    {"county": "Wasco County", "state": "OR", "fips": "41065", "dc_count": 4, "land_area_sqmi": 2381, "hub": "The Dalles"},
    {"county": "Washington County", "state": "OR", "fips": "41067", "dc_count": 10, "land_area_sqmi": 727, "hub": "Hillsboro"},
    {"county": "Clark County", "state": "NV", "fips": "32003", "dc_count": 20, "land_area_sqmi": 7891, "hub": "Las Vegas"},
    {"county": "Washoe County", "state": "NV", "fips": "32031", "dc_count": 10, "land_area_sqmi": 6342, "hub": "Reno"},
    {"county": "Storey County", "state": "NV", "fips": "32029", "dc_count": 8, "land_area_sqmi": 264, "hub": "Tahoe Reno"},
    {"county": "Salt Lake County", "state": "UT", "fips": "49035", "dc_count": 14, "land_area_sqmi": 742, "hub": "Salt Lake City"},
    {"county": "Utah County", "state": "UT", "fips": "49049", "dc_count": 6, "land_area_sqmi": 2003, "hub": "Provo"},
    {"county": "Mecklenburg County", "state": "NC", "fips": "37119", "dc_count": 16, "land_area_sqmi": 524, "hub": "Charlotte"},
    {"county": "Wake County", "state": "NC", "fips": "37183", "dc_count": 8, "land_area_sqmi": 835, "hub": "Raleigh"},
    {"county": "Catawba County", "state": "NC", "fips": "37035", "dc_count": 6, "land_area_sqmi": 400, "hub": "Hickory"},
    {"county": "Pottawattamie County", "state": "IA", "fips": "19155", "dc_count": 8, "land_area_sqmi": 954, "hub": "Council Bluffs"},
    {"county": "Polk County", "state": "IA", "fips": "19153", "dc_count": 6, "land_area_sqmi": 573, "hub": "Des Moines"},
    {"county": "Sarpy County", "state": "NE", "fips": "31153", "dc_count": 10, "land_area_sqmi": 240, "hub": "Omaha"},
    {"county": "Douglas County", "state": "NE", "fips": "31055", "dc_count": 6, "land_area_sqmi": 328, "hub": "Omaha"},
    {"county": "New York County", "state": "NY", "fips": "36061", "dc_count": 12, "land_area_sqmi": 23, "hub": "New York City"},
    {"county": "Hudson County", "state": "NJ", "fips": "34017", "dc_count": 10, "land_area_sqmi": 47, "hub": "Northern New Jersey"},
    {"county": "Bergen County", "state": "NJ", "fips": "34003", "dc_count": 8, "land_area_sqmi": 234, "hub": "Northern New Jersey"},
    {"county": "Middlesex County", "state": "NJ", "fips": "34023", "dc_count": 7, "land_area_sqmi": 309, "hub": "Central New Jersey"},
    {"county": "Miami-Dade County", "state": "FL", "fips": "12086", "dc_count": 18, "land_area_sqmi": 1898, "hub": "Miami"},
    {"county": "Hillsborough County", "state": "FL", "fips": "12057", "dc_count": 8, "land_area_sqmi": 1020, "hub": "Tampa"},
    {"county": "Orange County", "state": "FL", "fips": "12095", "dc_count": 8, "land_area_sqmi": 903, "hub": "Orlando"},
    {"county": "Broward County", "state": "FL", "fips": "12011", "dc_count": 8, "land_area_sqmi": 1210, "hub": "Fort Lauderdale"},
    {"county": "Denver County", "state": "CO", "fips": "08031", "dc_count": 10, "land_area_sqmi": 153, "hub": "Denver"},
    {"county": "Arapahoe County", "state": "CO", "fips": "08005", "dc_count": 6, "land_area_sqmi": 798, "hub": "Denver"},
    {"county": "Hennepin County", "state": "MN", "fips": "27053", "dc_count": 8, "land_area_sqmi": 554, "hub": "Minneapolis"},
    {"county": "Middlesex County", "state": "MA", "fips": "25017", "dc_count": 8, "land_area_sqmi": 818, "hub": "Boston"},
    {"county": "Suffolk County", "state": "MA", "fips": "25025", "dc_count": 6, "land_area_sqmi": 58, "hub": "Boston"},
    {"county": "Montgomery County", "state": "MD", "fips": "24031", "dc_count": 8, "land_area_sqmi": 491, "hub": "Washington DC Metro"},
    {"county": "Prince George's County", "state": "MD", "fips": "24033", "dc_count": 6, "land_area_sqmi": 483, "hub": "Washington DC Metro"},
    {"county": "Allegheny County", "state": "PA", "fips": "42003", "dc_count": 8, "land_area_sqmi": 730, "hub": "Pittsburgh"},
    {"county": "Davidson County", "state": "TN", "fips": "47037", "dc_count": 8, "land_area_sqmi": 504, "hub": "Nashville"},
    {"county": "Jackson County", "state": "MO", "fips": "29095", "dc_count": 6, "land_area_sqmi": 605, "hub": "Kansas City"},
    {"county": "Marion County", "state": "IN", "fips": "18097", "dc_count": 8, "land_area_sqmi": 396, "hub": "Indianapolis"},
    {"county": "Dane County", "state": "WI", "fips": "55025", "dc_count": 6, "land_area_sqmi": 1197, "hub": "Madison"},
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
            rows = json.loads(r.read(8 * 1024 * 1024).decode()).get("response", {}).get("data", [])
        return round(float(rows[0]["price"]), 2) if rows else None
    except (urllib.error.URLError, KeyError, ValueError, IndexError, OSError):
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
            rows = json.loads(r.read(24 * 1024 * 1024).decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
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


# ----------------------------- OSM layer -------------------------------------
def _load_geo_cache() -> dict:
    try:
        return json.loads(GEO_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_geo_cache(cache: dict) -> None:
    try:
        GEO_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def fetch_osm_sites() -> list[dict]:
    """Every US feature tagged as a data center, as [{lat, lon, name}]. Best
    effort: returns [] if Overpass is unreachable."""
    query = (
        "[out:json][timeout:180];"
        'area["ISO3166-1"="US"][admin_level=2]->.us;'
        '(nwr["telecom"="data_center"](area.us);'
        'nwr["man_made"="data_center"](area.us););'
        "out center 3000;"
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": "ThinkFree/1.0"})
            with urllib.request.urlopen(req, timeout=190) as r:
                doc = json.loads(r.read(48 * 1024 * 1024).decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError, ValueError) as e:
            print(f"  WARN: Overpass {url.split('/')[2]} failed: {type(e).__name__}; trying next")
            continue
        sites = []
        for el in doc.get("elements", []):
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            name = (el.get("tags", {}) or {}).get("name", "")
            sites.append({"lat": float(lat), "lon": float(lon), "name": str(name)[:80]})
        if sites:
            print(f"  OSM: {len(sites)} data-center features from {url.split('/')[2]}")
            return sites
    print("  WARN: no OSM sites (Overpass unreachable); curated layer only")
    return []


def fcc_county(lat: float, lon: float, cache: dict) -> dict | None:
    """Map lat/lon -> {fips, county, state} via the FCC area API, cached on disk
    keyed by coordinates rounded to ~110m."""
    key = f"{round(lat, 3)},{round(lon, 3)}"
    if key in cache:
        return cache[key] or None
    url = f"{FCC_BLOCK}?" + urllib.parse.urlencode({"latitude": lat, "longitude": lon, "format": "json", "showall": "false"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read(1024 * 1024).decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError, ValueError):
        return None
    county = d.get("County", {}) or {}
    state = d.get("State", {}) or {}
    fips = county.get("FIPS")
    sc = state.get("code")
    if not fips or len(str(fips)) < 5 or not sc:
        cache[key] = None
        return None
    rec = {"fips": str(fips)[:5], "county": county.get("name", ""), "state": sc}
    cache[key] = rec
    return rec


def osm_counts_by_county() -> dict:
    """Aggregate OSM data-center sites into {fips: {county, state, dc_count}}."""
    sites = fetch_osm_sites()
    if not sites:
        return {}
    cache = _load_geo_cache()
    before = len(cache)
    counts: dict[str, dict] = {}
    lookups = 0
    for s in sites:
        rec = fcc_county(s["lat"], s["lon"], cache)
        lookups += 1
        if lookups % 200 == 0:
            _save_geo_cache(cache)   # checkpoint so a long run is not lost
        if not rec:
            continue
        c = counts.setdefault(rec["fips"], {"county": rec["county"], "state": rec["state"], "dc_count": 0})
        c["dc_count"] += 1
    _save_geo_cache(cache)
    print(f"  OSM: mapped to {len(counts)} counties (geo-cache {before} -> {len(cache)} entries)")
    return counts


def _county_label(name: str) -> str:
    """Normalize a bare county name to '<Name> County' style."""
    name = (name or "").strip()
    if not name:
        return "Unknown County"
    if any(name.endswith(s) for s in (" County", " Parish", " Borough", " Census Area", " Municipality", " City")):
        return name
    return name + " County"


def merge_locations() -> tuple[list[dict], dict]:
    """Union the curated seed with the OSM-discovered counties, keyed by FIPS.
    Where both layers see a county, keep the larger (curated) count, since OSM
    under-counts dense markets. Returns (rows, stats)."""
    by_fips = {r["fips"]: dict(r) for r in SEED_DATA_CENTERS}
    osm = osm_counts_by_county()
    discovered = 0
    for fips, rec in osm.items():
        st = rec["state"]
        if st not in STATE_NAME:   # territories etc. without support tables
            continue
        if fips in by_fips:
            # curated count is authoritative for marquee markets; do not shrink it
            by_fips[fips]["dc_count"] = max(by_fips[fips]["dc_count"], rec["dc_count"])
            by_fips[fips].setdefault("osm_seen", True)
        else:
            by_fips[fips] = {
                "county": _county_label(rec["county"]), "state": st, "fips": fips,
                "dc_count": max(1, rec["dc_count"]), "land_area_sqmi": None,
                "hub": STATE_NAME.get(st, st), "osm_seen": True,
            }
            discovered += 1
    stats = {"curated": len(SEED_DATA_CENTERS), "osm_counties": len(osm),
             "discovered": discovered, "osm_sites": sum(c["dc_count"] for c in osm.values())}
    return list(by_fips.values()), stats


def main():
    print("Building Data Centers dataset (Census ACS + EIA + curated + OSM locations)...")
    census = fetch_census_counties()
    print(f"  Census counties fetched: {len(census)}")

    locations, stats = merge_locations()
    print(f"  locations: {stats['curated']} curated + {stats['discovered']} new from OSM "
          f"= {len(locations)} counties")

    eia_live = bool(EIA_KEY)
    price_src = "EIA live API" if eia_live else "EIA published averages (offline ref)"
    state_price = {}
    seen_states = {r["state"] for r in locations}
    for st in seen_states:
        p = eia_price_live(st) if eia_live else None
        state_price[st] = p if p is not None else EIA_PRICE_CENTS.get(st, EIA_PRICE_CENTS["US"])

    max_dc = max((r["dc_count"] for r in locations), default=1) or 1

    regions = []
    for r in locations:
        st = r["state"]
        acs = census.get(r["fips"], {})
        pop = acs.get("population")
        rent = acs.get("median_rent")
        inc = acs.get("median_household_income")

        gen = EIA_GEN_TWH.get(st, EIA_GEN_TWH["US"])
        power = clamp(gen / 564 * 100)                 # TX (564 TWh) anchors the top
        water = float(WATER_AVAILABILITY.get(st, WATER_AVAILABILITY["US"]))
        land_area = r.get("land_area_sqmi")
        density = (pop / land_area) if (pop and land_area) else None
        land = clamp(100 - (density / 2000 * 100)) if density is not None else 50.0
        exposure = clamp(r["dc_count"] / max_dc * 100)

        risk = round(power * WEIGHTS["power"] + water * WEIGHTS["water"]
                     + land * WEIGHTS["land"] + exposure * WEIGHTS["exposure"], 1)

        rent_burden = round(rent * 12 / inc * 100, 1) if (rent and inc) else None
        regions.append({
            "county": r["county"], "state": st, "state_name": STATE_NAME.get(st, st),
            "fips": r["fips"], "hub": r["hub"], "dc_count": r["dc_count"],
            "source": "curated + OSM" if r.get("osm_seen") else "curated",
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
            "land_availability": "Inverse of county population density (Census ACS population / county land area); neutral 50 where land area is unknown.",
            "datacenter_exposure": "Data-center count in the county, normalized to the most-saturated county in the set.",
        },
        "cost_of_living_link": ("Electricity rate (EIA) and rent burden (Census ACS "
                                "median rent / median household income) are shown per "
                                "county so the cost-of-living side is directly visible."),
    }

    data = {
        "sources": [
            "U.S. Census Bureau ACS 5-year " + str(ACS_YEAR),
            price_src,
            "Data-center locations: curated public records (Data Center Map, Baxtel, "
            "county economic-development filings) plus OpenStreetMap (Overpass) features "
            "tagged telecom=data_center / man_made=data_center, geocoded to county via the FCC area API",
            "Water: USGS water-use + WRI Aqueduct (curated index)",
        ],
        "source_urls": [
            "https://www.census.gov/programs-surveys/acs",
            "https://www.eia.gov/electricity/",
            "https://wiki.openstreetmap.org/wiki/Tag:telecom%3Ddata_center",
        ],
        "disclaimer": ("Informational, compiled from public records. Estimates and "
                       "curated figures, not a substitute for official filings. Does "
                       "not allege wrongdoing by any company or jurisdiction."),
        "eia_live": eia_live,
        "acs_year": ACS_YEAR,
        "location_stats": stats,
        "methodology": methodology,
        "regions": regions,
        "count": len(regions),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_datacenters.py "
                "(Census ACS + EIA + curated + OSM locations). No API key stored here.\n")
        f.write("window.DATACENTERS = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) - {len(regions)} counties "
          f"(curated {stats['curated']}, OSM sites {stats['osm_sites']}, new counties {stats['discovered']}), "
          f"electricity src: {price_src}")


if __name__ == "__main__":
    main()
