"""ThinkFree - OFR Hedge Fund Monitor (systemic-risk positioning).

Pulls hedge-fund positioning from the U.S. Office of Financial Research (OFR)
"Hedge Fund Monitor" API. The data is sourced from SEC/CFTC Form PF filings and
aggregated by OFR; it is FREE, requires NO API key, and updates ~daily as the
underlying quarterly filings are processed.

It surfaces what hedge funds are doing in aggregate - how big they are, how much
leverage they carry, where their gross notional exposure sits by asset class, how
much each strategy borrows, and how their credit (CDS) book is tilted. This is a
genuine systemic-risk read that "refines" ThinkFree's macro/intelligence context:
rising leverage + crowded one-sided positioning is a classic late-cycle stress
signal.

Writes webapp/js/hedgefund_data.js  (window.HEDGEFUND).
No secrets are read or written - this API needs none.

Run:  ./tf_env/bin/python webapp/build_hedgefund.py
Docs: https://www.financialresearch.gov/hedge-fund-monitor/api-specs/api-use/
"""
from __future__ import annotations

import gzip
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "hedgefund_data.js"
BASE = "https://data.financialresearch.gov/hf/v1/"
DATASET = "fpf"  # Form PF - the all-qualifying-hedge-funds aggregate dataset

# Curated set of OFR mnemonics -> human label + grouping for the UI. Every series
# here is documented in the OFR Hedge Fund Monitor; labels are plain-English so
# the front-end never has to interpret a raw mnemonic. Units: USD unless noted.
SERIES = {
    # --- Size & leverage (headline) ---
    "FPF-ALLQHF_GAV_SUM": {"label": "Gross Asset Value (total)", "group": "size", "unit": "usd"},
    "FPF-ALLQHF_NAV_SUM": {"label": "Net Asset Value (total)", "group": "size", "unit": "usd"},
    "FPF-ALLQHF_COUNT": {"label": "Qualifying hedge funds", "group": "size", "unit": "count"},
    "FPF-ALLQHF_GAVN10_LEVERAGERATIO_AVERAGE":
        {"label": "Leverage ratio (largest funds, avg)", "group": "size", "unit": "ratio"},
    # --- Gross notional exposure by asset class (the positioning view) ---
    "FPF-ASSETCLASS_EQUITIES_GNE_SUM": {"label": "Equities", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_CREDIT_GNE_SUM": {"label": "Credit", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_IRD_GNE_SUM": {"label": "Interest-rate derivatives", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_FX_GNE_SUM": {"label": "Foreign exchange", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_SOVEREIGN_GNE_SUM": {"label": "Sovereign (ex-US)", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_USGOV_GNE_SUM": {"label": "U.S. government", "group": "gne", "unit": "usd"},
    "FPF-ASSETCLASS_OTHER_GNE_SUM": {"label": "Other / commodities", "group": "gne", "unit": "usd"},
    # --- Borrowing by strategy ---
    "FPF-STRATEGY_CREDIT_BORROWING_SUM": {"label": "Credit", "group": "borrow", "unit": "usd"},
    "FPF-STRATEGY_EQUITY_BORROWING_SUM": {"label": "Equity", "group": "borrow", "unit": "usd"},
    "FPF-STRATEGY_MACRO_BORROWING_SUM": {"label": "Macro", "group": "borrow", "unit": "usd"},
    "FPF-STRATEGY_RV_BORROWING_SUM": {"label": "Relative value", "group": "borrow", "unit": "usd"},
    "FPF-STRATEGY_MULTI_BORROWING_SUM": {"label": "Multi-strategy", "group": "borrow", "unit": "usd"},
    # --- Credit (CDS) stress sensitivity: median P&L to a +/-250bps CDS move ---
    "FPF-ALLQHF_CDSUP250BPS_P50": {"label": "CDS spreads +250bps (median P&L)", "group": "cds", "unit": "usd"},
    "FPF-ALLQHF_CDSDOWN250BPS_P50": {"label": "CDS spreads -250bps (median P&L)", "group": "cds", "unit": "usd"},
}


def fetch_json(path: str, **params):
    """GET an OFR endpoint and parse JSON. Handles gzip; HTTPS only; no auth."""
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if not url.startswith("https://data.financialresearch.gov/"):
        raise ValueError("refusing non-OFR URL")
    req = urllib.request.Request(
        url, headers={"User-Agent": "ThinkFree/1.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return json.loads(raw.decode("utf-8"))


def timeseries(mnemonic: str):
    """Return [[YYYY-MM-DD, float], ...] sorted ascending, or [] on failure."""
    try:
        rows = fetch_json("series/timeseries", mnemonic=mnemonic)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
        print(f"  x {mnemonic}: {e}")
        return []
    out = []
    for pair in rows or []:
        try:
            date, val = pair[0], pair[1]
            if val is None:
                continue
            out.append([str(date), float(val)])
        except (ValueError, TypeError, IndexError):
            continue
    out.sort(key=lambda p: p[0])
    return out


def pct_change(series):
    """Quarter-over-quarter % change of the last two points, or None."""
    if len(series) < 2:
        return None
    prev, cur = series[-2][1], series[-1][1]
    if not prev:
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def latest(series):
    return series[-1][1] if series else None


def main():
    print("Fetching OFR Hedge Fund Monitor (Form PF aggregates)...")
    # sanity-check the dataset exists / API is reachable
    try:
        datasets = fetch_json("series/dataset")
        print(f"  datasets available: {', '.join(sorted(datasets))}")
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: OFR API unreachable: {e}")
        return

    series_out = {}
    for mn, meta in SERIES.items():
        s = timeseries(mn)
        if s:
            series_out[mn] = {**meta, "data": s, "latest": latest(s), "qoq_pct": pct_change(s)}
            print(f"  + {meta['label'][:34]:36} {len(s):3} pts  latest={latest(s)}")
        time.sleep(0.2)

    # ---- computed summary for the macro / intelligence / recession context ----
    def lat(mn):
        return series_out.get(mn, {}).get("latest")

    gne_total = sum(v["latest"] for k, v in series_out.items()
                    if v["group"] == "gne" and v.get("latest")) or None
    nav = lat("FPF-ALLQHF_NAV_SUM")
    gav = lat("FPF-ALLQHF_GAV_SUM")
    lev = lat("FPF-ALLQHF_GAVN10_LEVERAGERATIO_AVERAGE")
    cds_up = lat("FPF-ALLQHF_CDSUP250BPS_P50")
    cds_dn = lat("FPF-ALLQHF_CDSDOWN250BPS_P50")
    lev_trend = series_out.get("FPF-ALLQHF_GAVN10_LEVERAGERATIO_AVERAGE", {}).get("qoq_pct")

    # Plain-English systemic-risk read (transparent, no alarmism): rising leverage
    # with a one-sided credit book is the late-cycle pattern to watch.
    read = "Hedge-fund leverage and positioning are within normal historical ranges."
    if lev_trend is not None and lev_trend > 2:
        read = ("Aggregate hedge-fund leverage rose quarter-over-quarter - a factor "
                "that can amplify market moves if positions unwind together.")
    elif lev_trend is not None and lev_trend < -2:
        read = ("Aggregate hedge-fund leverage fell quarter-over-quarter - consistent "
                "with reduced risk appetite / de-grossing.")

    as_of = max((v["data"][-1][0] for v in series_out.values() if v.get("data")),
                default=None)
    summary = {
        "as_of": as_of,
        "gross_asset_value": gav,
        "net_asset_value": nav,
        "gross_notional_exposure": gne_total,
        "leverage_ratio_largest": lev,
        "leverage_qoq_pct": lev_trend,
        "cds_up250_p50": cds_up,
        "cds_down250_p50": cds_dn,
        "systemic_read": read,
    }

    data = {
        "source": "U.S. Office of Financial Research - Hedge Fund Monitor (Form PF)",
        "source_url": "https://www.financialresearch.gov/hedge-fund-monitor/",
        "dataset": DATASET,
        "as_of": as_of,
        "summary": summary,
        "series": series_out,
        "count": len(series_out),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_hedgefund.py (OFR Hedge Fund Monitor). "
                "Public data, no API key.\n")
        f.write("window.HEDGEFUND = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) - {len(series_out)} series, as of {as_of}")


if __name__ == "__main__":
    main()
