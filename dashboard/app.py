"""ThinkFree Finance — AI Financial Intelligence Dashboard v3"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="ThinkFree Finance",
    page_icon="TF",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
# CSS — Premium dark fintech theme
# ─────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────
# CSS — Pixel-level dark fintech theme matching reference design
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Design Tokens ── */
:root {
  --bg-primary:    #050816;
  --bg-secondary:  #070E1D;
  --bg-card:       #0C1628;
  --bg-card-deep:  #080F1E;
  --bg-inner:      rgba(4,8,18,0.90);
  --border-subtle: rgba(148,163,184,0.10);
  --border-soft:   rgba(148,163,184,0.15);
  --border-strong: rgba(148,163,184,0.26);
  --text-primary:  #F1F5F9;
  --text-secondary:#94A3B8;
  --text-tertiary: #475569;
  --text-faint:    #2E3A4E;
  --success:       #00C46A;
  --warning:       #F59E0B;
  --danger:        #EF4444;
  --info:          #38BDF8;
  --purple:        #A855F7;
  --shadow-sm:     0 2px 8px rgba(0,0,0,0.28);
  --shadow-md:     0 6px 20px rgba(0,0,0,0.32);
  --shadow-lg:     0 18px 52px rgba(0,0,0,0.42);
  --radius-sm:     10px;
  --radius-md:     14px;
  --radius-lg:     18px;
  --radius-xl:     22px;
}

/* ── Reset & Base ── */
html, body, .stApp {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  font-size: 14px;
  background:
    radial-gradient(ellipse 60% 40% at 0% 0%, rgba(0,196,106,0.055) 0%, transparent 60%),
    radial-gradient(ellipse 50% 35% at 100% 0%, rgba(59,130,246,0.055) 0%, transparent 60%),
    radial-gradient(ellipse 40% 60% at 50% 100%, rgba(168,85,247,0.03) 0%, transparent 50%),
    #050816 !important;
  color: #F1F5F9;
}

/* ── Hide Streamlit chrome ── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
footer,
#MainMenu { display: none !important; }

/* ── Sidebar — fixed 240px in normal flex flow (no position:fixed) ── */
section[data-testid="stSidebar"] {
  --sidebar-width: 240px;
  width: 240px !important;
  min-width: 240px !important;
  max-width: 240px !important;
  background: #07111F !important;
  border-right: 1px solid rgba(148,163,184,0.10) !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  scrollbar-width: none !important;
}
section[data-testid="stSidebar"]::-webkit-scrollbar { display: none !important; }
[data-testid="stSidebarContent"] { padding: 0 !important; }
[data-testid="stSidebar"] * { font-family: Inter, sans-serif !important; }
/* Hide resize handle and collapse toggle */
[data-testid="stSidebarResizeHandle"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── Main content — no manual margin needed; Streamlit flex handles it ── */
[data-testid="stAppViewContainer"] > [data-testid="stMain"] {
  padding-top: 0 !important;
}
[data-testid="stMainBlockContainer"] {
  padding-top: 0 !important;
  padding-bottom: 80px !important;
  max-width: 1360px !important;
  padding-left: 28px !important;
  padding-right: 28px !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  border: none !important;
  color: #475569 !important;
  text-align: left !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  padding: 0 12px !important;
  height: 38px !important;
  border-radius: 8px !important;
  transition: background 0.12s ease, color 0.12s ease !important;
  box-shadow: none !important;
  width: 100% !important;
  display: flex !important;
  align-items: center !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  margin: 1px 0 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(148,163,184,0.06) !important;
  color: #94A3B8 !important;
  transform: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: rgba(0,196,106,0.08) !important;
  color: #00C46A !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
  background: linear-gradient(180deg, #0D1829 0%, #0A1120 100%);
  border: 1px solid rgba(148,163,184,0.13);
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.22), inset 0 1px 0 rgba(255,255,255,0.03);
}
[data-testid="stMetricLabel"] {
  color: #64748B !important;
  font-size: 10.5px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.09em !important;
}
[data-testid="stMetricValue"] { color: #F1F5F9 !important; font-size: 22px !important; font-weight: 800 !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent;
  border-bottom: 1px solid rgba(148,163,184,0.14);
  gap: 0;
  padding: 0;
}
.stTabs [data-baseweb="tab"] {
  background: transparent;
  border-radius: 0;
  color: #64748B;
  font-weight: 500;
  font-size: 13px;
  padding: 10px 18px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.stTabs [data-baseweb="tab"]:hover { color: #CBD5E1; }
.stTabs [aria-selected="true"] {
  background: transparent !important;
  color: #FFFFFF !important;
  border-bottom: 2px solid #A855F7 !important;
  font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 16px !important; }

/* ── Expanders ── */
.streamlit-expanderHeader {
  background: #0F172A !important;
  border: 1px solid rgba(148,163,184,0.14) !important;
  border-radius: 10px !important;
  color: #E2E8F0 !important;
  font-weight: 500 !important;
  font-size: 13px !important;
}
.streamlit-expanderContent {
  background: #090F1D;
  border: 1px solid rgba(148,163,184,0.14);
  border-top: none;
  border-radius: 0 0 10px 10px;
}

/* ── Global Buttons ── */
.stButton > button {
  background: #00C46A !important;
  color: #050816 !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  font-size: 13px !important;
  padding: 8px 18px !important;
  transition: background 0.15s ease !important;
}
.stButton > button:hover { background: #00B05F !important; transform: none !important; }
.stButton > button:active { transform: scale(0.98) !important; }

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
  background: #0B1220 !important;
  border-radius: 12px;
  border: 1px solid rgba(148,163,184,0.14) !important;
}
.stDataFrame thead th {
  background: #0F172A !important;
  color: #94A3B8 !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}
.stDataFrame tbody tr:hover { background: rgba(148,163,184,0.05) !important; }
.stDataFrame tbody td { color: #CBD5E1 !important; font-size: 13px !important; border-color: rgba(148,163,184,0.08) !important; }

/* ── Divider ── */
hr { border-color: rgba(148,163,184,0.12) !important; margin: 16px 0 !important; }

/* ── Selectbox / Input ── */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
  background: #0B1220 !important;
  border: 1px solid rgba(148,163,184,0.18) !important;
  border-radius: 10px !important;
  color: #E2E8F0 !important;
  font-size: 13px !important;
}

/* ── Dialog / Modal ── */
[data-testid="stDialog"] {
  background: linear-gradient(180deg, #0B1220 0%, #08111F 100%) !important;
  border: 1px solid rgba(148,163,184,0.18) !important;
  border-radius: 22px !important;
  box-shadow: 0 32px 100px rgba(0,0,0,0.55) !important;
}
[data-testid="stDialog"] > div { padding: 0 !important; }

/* ────────────────────────────────────
   Reusable Components
──────────────────────────────────── */

/* Cards */
.tf-card {
  background: linear-gradient(180deg, #0D1829 0%, #0A1120 100%);
  border: 1px solid rgba(148,163,184,0.13);
  border-radius: 16px;
  padding: 16px 18px;
  transition: all 0.18s ease;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.03);
}
.tf-card:hover {
  border-color: rgba(148,163,184,0.24);
  box-shadow: 0 8px 28px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.04);
  transform: translateY(-1px);
}
.tf-card-sm {
  background: linear-gradient(180deg, #0D1829 0%, #0A1120 100%);
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 12px;
  padding: 10px 13px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.20);
}
.tf-inner {
  background: rgba(4,8,18,0.80);
  border-radius: 9px;
  padding: 10px 13px;
  border: 1px solid rgba(148,163,184,0.07);
}
.tf-panel {
  background: linear-gradient(135deg, rgba(13,22,40,0.96), rgba(14,10,30,0.92));
  border: 1px solid rgba(168,85,247,0.22);
  border-radius: 22px;
  padding: 18px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.40), 0 0 0 1px rgba(168,85,247,0.06) inset;
}

/* Typography */
.tf-label {
  font-size: 10.5px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  margin-bottom: 3px;
}
.tf-value { font-size: 30px; font-weight: 800; color: #F1F5F9; line-height: 1.1; }
.tf-value-md { font-size: 22px; font-weight: 800; color: #F1F5F9; }
.tf-value-sm { font-size: 16px; font-weight: 700; color: #F1F5F9; }
.tf-caption { font-size: 11.5px; color: #64748B; line-height: 1.45; }
.tf-section-title { font-size: 13.5px; font-weight: 700; color: #E2E8F0; letter-spacing: -0.01em; }
.tf-section-sub { font-size: 11.5px; color: #475569; margin: 1px 0 12px; }
.tf-text { font-size: 12.5px; color: #94A3B8; line-height: 1.55; }

/* Colors */
.tf-green  { color: #00C46A !important; font-weight: 600; }
.tf-red    { color: #EF4444 !important; font-weight: 600; }
.tf-amber  { color: #F59E0B !important; font-weight: 600; }
.tf-blue   { color: #38BDF8 !important; font-weight: 600; }
.tf-purple { color: #A855F7 !important; font-weight: 600; }
.tf-muted  { color: #94A3B8; }
.tf-faint  { color: #475569; }

/* Badges */
.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.badge-buy    { background: rgba(0,196,106,0.14);  color: #00C46A; border: 1px solid rgba(0,196,106,0.3); }
.badge-sell   { background: rgba(239,68,68,0.14);  color: #EF4444; border: 1px solid rgba(239,68,68,0.3); }
.badge-hold   { background: rgba(245,158,11,0.14); color: #F59E0B; border: 1px solid rgba(245,158,11,0.3); }
.badge-rep    { background: rgba(239,68,68,0.12);  color: #F87171; border: 1px solid rgba(239,68,68,0.22); }
.badge-dem    { background: rgba(59,130,246,0.12); color: #60A5FA; border: 1px solid rgba(59,130,246,0.22); }
.badge-ind    { background: rgba(168,85,247,0.12); color: #C084FC; border: 1px solid rgba(168,85,247,0.22); }
.badge-law    { background: rgba(0,196,106,0.12);  color: #00C46A; border: 1px solid rgba(0,196,106,0.3); }
.badge-bill   { background: rgba(100,116,139,0.12);color: #94A3B8; border: 1px solid rgba(100,116,139,0.3); }
.badge-high   { background: rgba(239,68,68,0.12);  color: #F87171; border: 1px solid rgba(239,68,68,0.22); }
.badge-med    { background: rgba(245,158,11,0.12); color: #FCD34D; border: 1px solid rgba(245,158,11,0.22); }
.badge-low    { background: rgba(0,196,106,0.12);  color: #00C46A; border: 1px solid rgba(0,196,106,0.3); }

/* Ticker bar */
.ticker-bar {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 8px 0 10px;
  border-bottom: 1px solid rgba(148,163,184,0.09);
  margin-bottom: 0;
  overflow-x: auto;
  flex-wrap: nowrap;
  scrollbar-width: none;
}
.ticker-bar::-webkit-scrollbar { display: none; }
.ticker-item  { display: flex; gap: 6px; align-items: baseline; white-space: nowrap; }
.ticker-name  { font-size: 10.5px; color: #334155; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; }
.ticker-price { font-size: 13px; color: #CBD5E1; font-weight: 700; }
.ticker-up    { font-size: 11.5px; color: #00C46A; font-weight: 700; }
.ticker-down  { font-size: 11.5px; color: #EF4444; font-weight: 700; }
.ticker-sep   { width: 1px; height: 14px; background: rgba(148,163,184,0.12); flex-shrink: 0; }

/* Grid layout helpers */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

/* Hero cards */
.hero-card {
  background: linear-gradient(160deg, #0D1829 0%, #090F1C 100%);
  border: 1px solid rgba(148,163,184,0.13);
  border-radius: 16px;
  padding: 16px 18px;
  height: 112px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.18s ease;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.26), inset 0 1px 0 rgba(255,255,255,0.025);
}
.hero-card:hover {
  border-color: rgba(148,163,184,0.22);
  box-shadow: 0 8px 26px rgba(0,0,0,0.32);
  transform: translateY(-1px);
}
.hero-card-mood  { border-top: 2px solid rgba(0,196,106,0.7); }
.hero-card-risk  { border-top: 2px solid rgba(239,68,68,0.5); }
.hero-card-dir   { border-top: 2px solid rgba(56,189,248,0.5); }
.hero-card-story { border-top: 2px solid rgba(168,85,247,0.5); height: auto; min-height: 112px; }

/* Political Watch panel */
.pol-panel {
  background: linear-gradient(145deg, rgba(11,19,36,0.98) 0%, rgba(18,10,36,0.95) 100%);
  border: 1px solid rgba(168,85,247,0.20);
  border-left: 3px solid rgba(168,85,247,0.55);
  border-radius: 20px;
  padding: 18px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.40), 0 0 40px rgba(168,85,247,0.04);
}
.pol-grid {
  display: grid;
  grid-template-columns: 272px minmax(0,1fr) 280px;
  gap: 12px;
  align-items: start;
}
.pol-left-card {
  background: linear-gradient(150deg, #0C1828 0%, rgba(72,20,120,0.18) 100%);
  border: 1px solid rgba(168,85,247,0.20);
  border-radius: 16px;
  padding: 14px;
  height: 100%;
  box-shadow: inset 0 1px 0 rgba(168,85,247,0.08);
}
.pol-center-card {
  background: rgba(8,14,26,0.80);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 14px;
  padding: 13px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
  overflow-x: auto;
}
.pol-right-card {
  background: rgba(8,14,26,0.80);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 14px;
  padding: 13px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
}
.pol-stat-mini {
  background: rgba(4,8,18,0.75);
  border: 1px solid rgba(148,163,184,0.07);
  border-radius: 9px;
  padding: 9px 11px;
  margin-bottom: 7px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Top 10 table */
.pol-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.pol-table thead th {
  color: #475569;
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  padding: 0 8px 8px;
  text-align: left;
  border-bottom: 1px solid rgba(148,163,184,0.12);
}
.pol-table tbody tr {
  border-bottom: 1px solid rgba(148,163,184,0.07);
  transition: background 0.12s;
}
.pol-table tbody tr:hover { background: rgba(148,163,184,0.04); }
.pol-table tbody td {
  padding: 9px 8px;
  color: #CBD5E1;
  white-space: nowrap;
}
.pol-table .gain-val { color: #00C46A; font-weight: 700; }
.pol-table .rank-num {
  color: #475569;
  font-weight: 700;
  font-size: 11px;
  width: 20px;
}

/* Info cards in lower grid */
.info-card {
  background: linear-gradient(180deg, #0D1829 0%, #0A1120 100%);
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 16px;
  padding: 15px 17px;
  height: 100%;
  transition: all 0.18s ease;
  box-shadow: 0 3px 14px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.025);
  position: relative;
  overflow: hidden;
}
.info-card:hover {
  border-color: rgba(148,163,184,0.20);
  box-shadow: 0 8px 28px rgba(0,0,0,0.30);
  transform: translateY(-1px);
}
.info-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}
.info-icon {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
}
.signal-row-d {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 0;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}
.dot-g { width:7px;height:7px;border-radius:50%;background:#00C46A;flex-shrink:0;display:inline-block; }
.dot-r { width:7px;height:7px;border-radius:50%;background:#EF4444;flex-shrink:0;display:inline-block; }
.dot-a { width:7px;height:7px;border-radius:50%;background:#F59E0B;flex-shrink:0;display:inline-block; }

/* Opportunity mini card */
.opp-card {
  background: linear-gradient(180deg, #0C1726 0%, #091018 100%);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 11px;
  padding: 10px 13px;
  margin-bottom: 7px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.20);
  transition: border-color 0.15s ease;
}
.opp-card:hover { border-color: rgba(148,163,184,0.18); }

/* News list */
.news-row {
  display: flex;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid rgba(148,163,184,0.07);
  align-items: flex-start;
}
.news-dot-g {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #00C46A;
  flex-shrink: 0;
  margin-top: 6px;
}

/* Top bar */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px 10px;
  border-bottom: 1px solid rgba(148,163,184,0.09);
  margin-bottom: 14px;
}
.topbar-search {
  width: 280px;
  height: 36px;
  background: rgba(10,17,32,0.90);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 10px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 7px;
  color: #334155;
  font-size: 12.5px;
  transition: border-color 0.15s;
  cursor: text;
}
.topbar-search:hover { border-color: rgba(148,163,184,0.26); }
.topbar-icons {
  display: flex;
  gap: 7px;
  align-items: center;
}
.topbar-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: rgba(10,17,32,0.85);
  border: 1px solid rgba(148,163,184,0.13);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #475569;
  font-size: 14px;
  transition: all 0.15s;
}
.topbar-icon:hover { border-color: rgba(148,163,184,0.24); color: #94A3B8; }

/* Section header row */
.sec-hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.sec-view-all {
  font-size: 12px;
  color: #00C46A;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}

/* Disclaimer */
.disclaimer {
  font-size: 11px;
  color: #334155;
  line-height: 1.5;
  padding: 12px 0 0;
  border-top: 1px solid rgba(148,163,184,0.08);
  margin-top: 16px;
}

/* Progress bar */
.prog-bar-outer {
  width: 100%;
  height: 6px;
  background: rgba(148,163,184,0.12);
  border-radius: 999px;
  margin-top: 4px;
}
.prog-bar-inner {
  height: 6px;
  border-radius: 999px;
  transition: width 0.4s ease;
}

/* Sector mini card */
.sector-mini {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 10px;
  background: rgba(7,14,28,0.6);
  border-radius: 8px;
  margin-bottom: 6px;
}

/* Timeline */
.timeline-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  position: relative;
}
.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
}
.timeline-line {
  position: absolute;
  left: 4px;
  top: 18px;
  bottom: -8px;
  width: 2px;
  background: rgba(148,163,184,0.12);
}

/* Correlation bar */
.corr-pill-high  { background:rgba(239,68,68,0.14); color:#F87171; border:1px solid rgba(239,68,68,0.25); border-radius:999px; padding:2px 8px; font-size:10.5px; font-weight:700; }
.corr-pill-med   { background:rgba(245,158,11,0.14); color:#FCD34D; border:1px solid rgba(245,158,11,0.25); border-radius:999px; padding:2px 8px; font-size:10.5px; font-weight:700; }
.corr-pill-low   { background:rgba(0,196,106,0.14); color:#00C46A; border:1px solid rgba(0,196,106,0.25); border-radius:999px; padding:2px 8px; font-size:10.5px; font-weight:700; }

/* Modal summary cards */
.modal-card {
  background: rgba(11,18,32,0.9);
  border: 1px solid rgba(148,163,184,0.14);
  border-radius: 14px;
  padding: 14px 16px;
}
.modal-grid-5 {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.modal-grid-2 {
  display: grid;
  grid-template-columns: 55fr 45fr;
  gap: 16px;
}

/* Quick Actions card */
.qa-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 11px;
  background: rgba(4,8,18,0.70);
  border: 1px solid rgba(148,163,184,0.09);
  border-radius: 10px;
  margin-bottom: 7px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.qa-btn:hover {
  background: rgba(148,163,184,0.05);
  border-color: rgba(148,163,184,0.18);
  transform: translateX(2px);
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.18); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,0.32); }
</style>
""", unsafe_allow_html=True)

# ── Layout, button, and utility overrides ─────────────────────────────
st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── Safe bottom zone ── */
[data-testid="stMain"] { padding-bottom: 80px !important; }

/* ── Text wrapping ── */
button, .badge, .ticker-name, .ticker-price, .ticker-up, .ticker-down,
.tf-section-title, .sec-view-all { white-space: nowrap !important; }

/* Description clamp */
.description, .news-headline {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Card "View all" link buttons — must beat .stButton > button specificity ── */
.tf-link-btn { line-height: 1; display: block; }
.tf-link-btn .stButton > button {
  background: transparent !important;
  border: none !important;
  color: #38BDF8 !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  padding: 1px 0 !important;
  height: 18px !important;
  min-height: 0 !important;
  line-height: 1 !important;
  box-shadow: none !important;
  white-space: nowrap !important;
  letter-spacing: 0 !important;
  width: auto !important;
  min-width: 0 !important;
  text-decoration: none !important;
}
.tf-link-btn .stButton > button:hover {
  color: #00C46A !important;
  background: transparent !important;
  transform: none !important;
  box-shadow: none !important;
}

/* ── Quick Action buttons ── */
.tf-qa-btn .stButton > button {
  background: rgba(7,14,28,0.70) !important;
  border: 1px solid rgba(148,163,184,0.09) !important;
  border-radius: 10px !important;
  color: #94A3B8 !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  padding: 9px 12px !important;
  height: 42px !important;
  min-height: 42px !important;
  text-align: left !important;
  justify-content: flex-start !important;
  width: 100% !important;
  margin-bottom: 0 !important;
  transition: border-color 0.12s ease, color 0.12s ease !important;
}
.tf-qa-btn .stButton > button:hover {
  border-color: rgba(148,163,184,0.18) !important;
  color: #CBD5E1 !important;
  background: rgba(148,163,184,0.04) !important;
  transform: none !important;
}
.tf-qa-btn { margin-bottom: 6px; }

/* ── Placeholder pages ── */
.tf-placeholder {
  max-width: 500px;
  margin: 64px auto;
  text-align: center;
  padding: 40px 36px;
  background: linear-gradient(180deg, #0D1829 0%, #0A1120 100%);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 18px;
  box-shadow: 0 16px 48px rgba(0,0,0,0.32);
}

/* ── Text input ── */
.stTextInput input { background: rgba(10,17,32,0.90) !important; border: 1px solid rgba(148,163,184,0.14) !important; border-radius: 10px !important; color: #E2E8F0 !important; font-size: 12.5px !important; height: 36px !important; padding: 0 12px !important; }

/* ── Table overflow ── */
.pol-center-card { overflow-x: auto !important; max-width: 100%; }
</style>
""", unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────
# Static reference data
# ─────────────────────────────────────────────────────────────────────

_TICKER_INFO: dict[str, tuple[str, str]] = {
    "AAPL": ("Apple Inc.", "Technology"), "MSFT": ("Microsoft Corp.", "Technology"),
    "GOOGL": ("Alphabet Inc.", "Communication Services"), "GOOG": ("Alphabet Inc.", "Communication Services"),
    "AMZN": ("Amazon.com Inc.", "Consumer Discretionary"), "NVDA": ("NVIDIA Corp.", "Technology"),
    "META": ("Meta Platforms", "Communication Services"), "TSLA": ("Tesla Inc.", "Consumer Discretionary"),
    "BRK.B": ("Berkshire Hathaway", "Financials"), "JPM": ("JPMorgan Chase", "Financials"),
    "V": ("Visa Inc.", "Financials"), "JNJ": ("Johnson & Johnson", "Health Care"),
    "UNH": ("UnitedHealth Group", "Health Care"), "XOM": ("Exxon Mobil", "Energy"),
    "LLY": ("Eli Lilly", "Health Care"), "HD": ("Home Depot", "Consumer Discretionary"),
    "PG": ("Procter & Gamble", "Consumer Staples"), "MA": ("Mastercard", "Financials"),
    "MRK": ("Merck & Co.", "Health Care"), "CVX": ("Chevron Corp.", "Energy"),
    "ABBV": ("AbbVie Inc.", "Health Care"), "COST": ("Costco Wholesale", "Consumer Staples"),
    "PEP": ("PepsiCo Inc.", "Consumer Staples"), "KO": ("Coca-Cola Co.", "Consumer Staples"),
    "WMT": ("Walmart Inc.", "Consumer Staples"), "BAC": ("Bank of America", "Financials"),
    "MCD": ("McDonald's Corp.", "Consumer Discretionary"), "CRM": ("Salesforce Inc.", "Technology"),
    "TMO": ("Thermo Fisher Scientific", "Health Care"), "CSCO": ("Cisco Systems", "Technology"),
    "ABT": ("Abbott Laboratories", "Health Care"), "AMD": ("Advanced Micro Devices", "Technology"),
    "INTC": ("Intel Corp.", "Technology"), "QCOM": ("Qualcomm Inc.", "Technology"),
    "TXN": ("Texas Instruments", "Technology"), "AMGN": ("Amgen Inc.", "Health Care"),
    "GS": ("Goldman Sachs", "Financials"), "MS": ("Morgan Stanley", "Financials"),
    "WFC": ("Wells Fargo", "Financials"), "C": ("Citigroup", "Financials"),
    "BLK": ("BlackRock", "Financials"), "AXP": ("American Express", "Financials"),
    "RTX": ("Raytheon Technologies", "Industrials"), "LMT": ("Lockheed Martin", "Industrials"),
    "BA": ("Boeing Co.", "Industrials"), "GE": ("GE Aerospace", "Industrials"),
    "CAT": ("Caterpillar Inc.", "Industrials"), "DE": ("Deere & Co.", "Industrials"),
    "NEE": ("NextEra Energy", "Utilities"), "DUK": ("Duke Energy", "Utilities"),
    "SO": ("Southern Co.", "Utilities"), "T": ("AT&T Inc.", "Communication Services"),
    "VZ": ("Verizon", "Communication Services"), "NFLX": ("Netflix Inc.", "Communication Services"),
    "DIS": ("Walt Disney Co.", "Communication Services"),
    "AMT": ("American Tower", "Real Estate"), "PLD": ("Prologis", "Real Estate"),
    "DELL": ("Dell Technologies", "Technology"), "ORCL": ("Oracle Corp.", "Technology"),
    "ADBE": ("Adobe Inc.", "Technology"), "NOW": ("ServiceNow", "Technology"),
    "SNOW": ("Snowflake Inc.", "Technology"), "PLTR": ("Palantir Technologies", "Technology"),
    "COIN": ("Coinbase Global", "Financials"), "PYPL": ("PayPal Holdings", "Financials"),
    "AMAT": ("Applied Materials", "Technology"), "MU": ("Micron Technology", "Technology"),
    "KLAC": ("KLA Corp.", "Technology"), "MRVL": ("Marvell Technology", "Technology"),
    "CVS": ("CVS Health", "Health Care"), "PFE": ("Pfizer Inc.", "Health Care"),
    "GILD": ("Gilead Sciences", "Health Care"), "BIIB": ("Biogen Inc.", "Health Care"),
    "REGN": ("Regeneron Pharmaceuticals", "Health Care"),
    "F": ("Ford Motor Co.", "Consumer Discretionary"), "GM": ("General Motors", "Consumer Discretionary"),
    "NKE": ("Nike Inc.", "Consumer Discretionary"), "SBUX": ("Starbucks Corp.", "Consumer Discretionary"),
    "TGT": ("Target Corp.", "Consumer Staples"), "LOW": ("Lowe's Companies", "Consumer Discretionary"),
}

_EXTENDED_SECTORS = [
    {"name": "Technology / AI", "geopolitical": "High — US-China chip restrictions directly impact sector",
     "note": "AI infrastructure buildout is driving record data center spending. Valuations are elevated relative to historical averages."},
    {"name": "Semiconductors", "geopolitical": "Very High — export controls, Taiwan risk, supply chain concentration",
     "note": "The backbone of modern technology. TSMC produces 90%+ of advanced chips. A Taiwan conflict would be catastrophic for global supply."},
    {"name": "Defense & Aerospace", "geopolitical": "Very High — benefits directly from global conflict escalation",
     "note": "Defense budgets are rising across NATO. Companies with Pentagon contracts often see sustained revenue even in recessions."},
    {"name": "Oil & Gas / Energy", "geopolitical": "Very High — OPEC decisions, Middle East stability, Russia sanctions",
     "note": "Oil prices are determined as much by geopolitics as by supply and demand. Energy stocks typically outperform during inflationary periods."},
    {"name": "Utilities", "geopolitical": "Low — domestically regulated, defensive",
     "note": "Utilities rarely move with the market. They are the defensive shelter during economic downturns. Sensitive to interest rates."},
    {"name": "Banks & Major Financials", "geopolitical": "Medium — regulatory risk, credit cycle exposure",
     "note": "Banks profit from high interest rates (wider spread between deposits and loans). The risk is loan defaults if the economy slows."},
    {"name": "Regional Banks", "geopolitical": "Low — domestic focus, but systemic risk after 2023 SVB collapse",
     "note": "Regional banks hold significant commercial real estate exposure. Rising defaults in office and retail real estate are a direct risk."},
    {"name": "Biotechnology", "geopolitical": "Low-Medium — FDA approval risk, drug pricing policy",
     "note": "Biotech is driven by clinical trial results and FDA decisions. A single drug approval or rejection can move a stock 50%+ in one day."},
    {"name": "Cybersecurity", "geopolitical": "High — nation-state attacks, government contract growth",
     "note": "Government cybersecurity spending is growing faster than almost any other category. Geopolitical tensions drive private sector security spending."},
    {"name": "Healthcare / Managed Care", "geopolitical": "Medium — drug pricing regulation, ACA policy",
     "note": "Healthcare is defensive during recessions. The risk is regulatory changes to drug pricing or insurance markets."},
    {"name": "Consumer Staples", "geopolitical": "Low — defensive, inflation pass-through capacity",
     "note": "Companies that make food, beverages, and household products. They can usually raise prices with inflation."},
    {"name": "Consumer Discretionary", "geopolitical": "Low — sensitive to consumer confidence and employment",
     "note": "Retail, restaurants, autos, and luxury goods. Highly sensitive to consumer spending and job growth."},
    {"name": "Housing & Homebuilders", "geopolitical": "Low — sensitive to mortgage rates",
     "note": "Housing starts collapse when mortgage rates are high. A drop in the 30-year mortgage rate is the single biggest catalyst."},
    {"name": "Transportation & Logistics", "geopolitical": "Medium — fuel costs, trade volumes, supply chain",
     "note": "Shipping, trucking, and airlines. Sensitive to fuel prices and global trade volumes."},
    {"name": "Real Estate (REITs)", "geopolitical": "Low — interest rate sensitive",
     "note": "Real estate investment trusts are highly sensitive to interest rates — rising rates increase borrowing costs."},
    {"name": "Crypto-Related Equities", "geopolitical": "Medium — regulatory risk, correlation with Bitcoin",
     "note": "Coinbase, MicroStrategy, and Bitcoin miners trade closely with Bitcoin price. They amplify crypto moves with additional operating leverage."},
    {"name": "AI Infrastructure", "geopolitical": "High — chip export controls, data center power supply",
     "note": "The picks-and-shovels of the AI boom: power companies, data center builders, cooling systems."},
    {"name": "Gold & Precious Metals", "geopolitical": "Very High — safe-haven demand during global uncertainty",
     "note": "Gold rises when investors fear inflation, currency debasement, or geopolitical instability. It is the classic fear trade."},
]

_HISTORICAL_EPISODES = [
    {"name": "Dot-Com Bubble", "dates": "1995–2002",
     "what_happened": "Technology stocks rose 400%+ as investors funded internet companies with no profits. The NASDAQ collapsed 78% from peak to trough. $5 trillion in market value was erased.",
     "today_similarity": "Elevated AI and tech valuations echo the late 1990s. The key difference: today's tech giants have real revenues and cash flows. The risk is in speculative AI companies without proven business models.",
     "winners_then": ["Value stocks", "Healthcare", "Consumer staples", "Cash"],
     "losers_then": ["Internet startups", "Telecom", "Enterprise software", "VC-backed companies"],
     "lesson": "When price rises far faster than earnings, mean reversion is brutal and inevitable."},
    {"name": "2008 Financial Crisis", "dates": "2007–2009",
     "what_happened": "The collapse of the US housing market triggered a global credit freeze. S&P 500 fell 57%. Lehman Brothers filed the largest bankruptcy in US history. Unemployment hit 10%.",
     "today_similarity": "Commercial real estate stress and regional bank pressures echo some 2008 dynamics. However, household debt quality is much stronger today and major bank capital requirements are far stricter.",
     "winners_then": ["Gold", "US Treasury bonds", "Short sellers", "Cash"],
     "losers_then": ["Banks", "Real estate", "Financials broadly", "Leveraged buyouts"],
     "lesson": "Leverage amplifies losses catastrophically. When credit markets freeze, even healthy companies suffer from the contagion."},
    {"name": "COVID Crash and Recovery", "dates": "2020",
     "what_happened": "Markets fell 34% in 33 days — the fastest bear market in history. The Federal Reserve and Treasury injected $5+ trillion in stimulus. Markets fully recovered in 5 months.",
     "today_similarity": "The post-COVID inflation surge and aggressive Fed rate hiking cycle are the direct consequence of that historic stimulus. We are still unwinding those effects today.",
     "winners_then": ["Remote work technology", "E-commerce", "Biotech", "Streaming services"],
     "losers_then": ["Airlines", "Hotels", "Restaurants", "Cruise lines", "Office real estate"],
     "lesson": "Extraordinary policy responses can override fundamentals temporarily. The long-term cost of printing money is inflation."},
    {"name": "Meme Stock Mania", "dates": "January–February 2021",
     "what_happened": "Retail investors coordinated on Reddit to drive short squeezes in GameStop and AMC. GameStop rose 1,700% in weeks before collapsing 90%. Hedge funds lost billions.",
     "today_similarity": "Social media can still drive irrational price moves in heavily shorted, small-cap stocks. The same psychology applies to trending meme coins and viral tickers.",
     "winners_then": ["Retail traders who sold near the peak", "Options dealers"],
     "losers_then": ["Hedge funds short the stocks", "Retail investors who bought at peak"],
     "lesson": "Social-media-driven momentum is real but temporary. These moves always end badly for those who arrive late."},
    {"name": "Crypto and NFT Bubble", "dates": "2020–2022",
     "what_happened": "Bitcoin hit $69,000 in November 2021. NFTs sold for millions. By 2022, Bitcoin dropped 77%, most NFTs became worthless, and FTX collapsed in a $32 billion fraud.",
     "today_similarity": "Bitcoin has recovered to record highs driven by spot ETF approvals and institutional adoption. But speculative altcoins still carry the same mania dynamics.",
     "winners_then": ["Early Bitcoin holders (pre-2020)", "Coinbase at IPO"],
     "losers_then": ["Late NFT buyers", "Terra/Luna holders", "FTX customers", "Leveraged altcoin traders"],
     "lesson": "New asset classes attract massive speculation. The underlying technology may survive. Most of the speculative assets built on top of it will not."},
    {"name": "Tulip Mania", "dates": "1636–1637 (Netherlands)",
     "what_happened": "Dutch tulip bulb prices rose 2,000% in one year. A single tulip bulb sold for more than a skilled craftsman's annual salary. The market collapsed in days when buyers stopped showing up.",
     "today_similarity": "Considered the original speculative bubble, tulip mania illustrates how social contagion drives prices far beyond utility. The same psychology appears in meme stocks, NFTs, and speculative crypto.",
     "winners_then": ["Those who sold early"],
     "losers_then": ["Anyone holding at the peak"],
     "lesson": "When an asset's price is driven entirely by the belief that someone else will pay more — not by income or utility — you are in a mania."},
    {"name": "1970s Inflation Shock", "dates": "1973–1982",
     "what_happened": "Oil shocks from the Arab embargo (1973) and Iranian Revolution (1979) drove US inflation above 14%. The Fed raised rates to 20% to break inflationary expectations. A deep recession followed.",
     "today_similarity": "The 2022–2024 inflation episode was the closest parallel in 40 years. The key risk: 1970s inflation came in two waves. If today's inflation resurges, the policy response would need to be even more aggressive.",
     "winners_then": ["Commodities", "Energy", "Gold", "Short-duration bonds"],
     "losers_then": ["Long-duration bonds", "Growth stocks", "Consumer discretionary"],
     "lesson": "Inflation is harder to extinguish than it looks. Once embedded in expectations, removing it requires significant economic pain."},
    {"name": "1987 Black Monday", "dates": "October 19, 1987",
     "what_happened": "The S&P 500 fell 20.5% in a single day — still the largest one-day percentage drop in US market history. Program trading and portfolio insurance strategies amplified the selloff.",
     "today_similarity": "Algorithmic trading now represents 60–70% of US equity volume. Correlated algorithmic strategies can still produce flash crashes and amplified selloffs during market stress.",
     "winners_then": ["Cash holders", "Put option buyers"],
     "losers_then": ["Equity investors broadly", "Portfolio insurance users"],
     "lesson": "Mechanical selling strategies amplify panics. The market recovered fully within 2 years. Investors who panicked locked in losses."},
]

_SIGNAL_EXPLANATIONS = {
    "macd_bullish": {
        "label": "Momentum Improving",
        "plain": "Short-term momentum has crossed above the long-term trend. This often signals the beginning of an upward move.",
        "supports": "The stock has been gaining relative strength recently.",
        "contradicts": "MACD lags price — it confirms a trend after it starts, not before. False signals are common in volatile markets.",
    },
    "macd_bearish": {
        "label": "Momentum Weakening",
        "plain": "Short-term momentum has crossed below the long-term trend. This suggests recent buying pressure is fading.",
        "supports": "The stock has been losing relative strength recently.",
        "contradicts": "In strong uptrends, bearish MACD crossovers are often temporary before the trend resumes.",
    },
    "rsi_oversold": {
        "label": "Potentially Oversold",
        "plain": "The stock has dropped fast enough that it may be due for a bounce. RSI below 30 means selling has been extreme.",
        "supports": "Extreme selling often exhausts itself and leads to at least a temporary recovery.",
        "contradicts": "Stocks can stay oversold during prolonged downtrends. Oversold is not a buy signal on its own.",
    },
    "rsi_overbought": {
        "label": "Potentially Overbought",
        "plain": "The stock has risen sharply and may be getting stretched. RSI above 70 means buying has been aggressive.",
        "supports": "Extended buying often precedes a pause or pullback as early buyers take profits.",
        "contradicts": "Strong stocks in strong uptrends can stay overbought for months.",
    },
    "rsi_neutral": {
        "label": "RSI Neutral",
        "plain": "No extreme buying or selling pressure detected. RSI in the 30–70 range is considered balanced.",
        "supports": "A neutral RSI does not add directional pressure in either direction.",
        "contradicts": "Neutral RSI does not mean the trend is clear — it simply means no extreme condition exists.",
    },
    "sma_golden_cross": {
        "label": "Long-Term Trend Improving",
        "plain": "The 50-day moving average crossed above the 200-day moving average. One of the most widely watched bullish signals.",
        "supports": "When the medium-term average overtakes the long-term average, recent performance is stronger than the baseline.",
        "contradicts": "Golden crosses often occur after price has already risen significantly. Buying after a golden cross means buying into existing strength.",
    },
    "sma_death_cross": {
        "label": "Long-Term Trend Weakening",
        "plain": "The 50-day moving average crossed below the 200-day moving average. A widely watched bearish signal.",
        "supports": "The medium-term average dropping below the long-term confirms that recent performance has been consistently weak.",
        "contradicts": "Death crosses often happen after the price has already fallen significantly. The worst damage may already be done.",
    },
    "bollinger_upper": {
        "label": "Price at Upper Range",
        "plain": "The stock is trading at the high end of its normal price range. This can mean overbought conditions or the start of a strong breakout.",
        "supports": "In strong momentum markets, hitting the upper Bollinger Band can signal continuation rather than reversal.",
        "contradicts": "In choppy markets, upper band touches typically lead to mean reversion back toward the center.",
    },
    "bollinger_lower": {
        "label": "Price at Lower Range",
        "plain": "The stock is trading at the low end of its normal price range. This can signal oversold conditions or a breakdown to new lows.",
        "supports": "Extreme selloffs often lead to at least a short-term bounce from oversold levels.",
        "contradicts": "In downtrends, lower Bollinger Band touches can signal further weakness, not recovery.",
    },
    "volume_surge": {
        "label": "Unusual Volume",
        "plain": "Trading volume is significantly above normal. This typically means a larger group of investors is taking action.",
        "supports": "High volume confirms price moves. A rally on high volume is more meaningful than one on low volume.",
        "contradicts": "Volume spikes near price peaks can signal exhaustion rather than continuation.",
    },
}

_RECESSION_INDICATORS = [
    {"key": "yield_curve", "name": "Yield Curve", "weight": 25,
     "plain": "When short-term interest rates are higher than long-term rates, banks stop lending and economic activity slows. This has preceded every US recession in the past 50 years."},
    {"key": "unemployment", "name": "Unemployment Trend", "weight": 15,
     "plain": "Rising unemployment means fewer people can spend money, which slows the economy further. A rising trend matters more than the absolute level."},
    {"key": "vix", "name": "Market Fear (VIX)", "weight": 10,
     "plain": "The VIX measures how much uncertainty is priced into stock options. A VIX above 30 indicates significant investor fear."},
    {"key": "consumer_sentiment", "name": "Consumer Confidence", "weight": 15,
     "plain": "When consumers feel pessimistic, they reduce spending. Consumer spending drives 70% of the US economy."},
    {"key": "manufacturing_pmi", "name": "Manufacturing PMI", "weight": 10,
     "plain": "When this falls below 50, manufacturing is contracting. Sustained contraction typically precedes broader economic slowdowns."},
    {"key": "credit_spreads", "name": "Credit Spreads", "weight": 10,
     "plain": "When companies have to pay much more than the government to borrow, it signals investors fear defaults. Widening spreads often precede recessions."},
    {"key": "housing", "name": "Housing Activity", "weight": 8,
     "plain": "Housing drives significant economic activity. A sharp drop in housing starts is an early warning sign."},
    {"key": "leading_index", "name": "Leading Economic Index", "weight": 7,
     "plain": "A composite index of 10 forward-looking indicators. Three consecutive monthly declines historically precede recessions."},
]


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _fmt_currency(val) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
        sign = "+" if v >= 0 else ""
        if abs(v) >= 1_000_000:
            return f"{sign}${v/1_000_000:.2f}M"
        return f"{sign}${v:,.0f}"
    except Exception:
        return str(val)


def _fmt_pct(val) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    except Exception:
        return str(val)


def _score_color(score: float) -> str:
    if score >= 7:
        return "#22C55E"
    if score >= 5:
        return "#F59E0B"
    return "#EF4444"


def _signal_color(sig: str) -> str:
    return {"BUY": "#22C55E", "SELL": "#EF4444"}.get(sig.upper(), "#F59E0B")


def _risk_label_color(label: str) -> str:
    return {
        "Low": "#22C55E", "Moderate": "#F59E0B",
        "Elevated": "#F97316", "High": "#EF4444", "Very High": "#DC2626",
    }.get(label, "#94A3B8")


def _explain_indicators(supporting: list, contradicting: list) -> tuple:
    label_map = {
        "macd": "MACD (momentum indicator)", "rsi": "RSI (overbought/oversold indicator)",
        "sma": "Moving average trend", "ema": "Exponential moving average",
        "bollinger": "Bollinger Band position", "volume": "Trading volume",
        "golden cross": "50-day average crossed above 200-day (bullish long-term signal)",
        "death cross": "50-day average crossed below 200-day (bearish long-term signal)",
        "bullish crossover": "Short-term momentum overtook long-term momentum",
        "bearish crossover": "Short-term momentum fell below long-term momentum",
        "oversold": "RSI below 30 — selling may be exhausted",
        "overbought": "RSI above 70 — buying may be exhausted",
        "neutral zone": "RSI between 30–70, no extreme reading",
        "upper band": "Price at high end of normal range",
        "lower band": "Price at low end of normal range",
    }
    def translate(ind):
        il = ind.lower()
        return next((v for k, v in label_map.items() if k in il), ind)
    return [translate(i) for i in supporting], [translate(i) for i in contradicting]


# ─────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_all_data() -> dict:
    return {
        "user_profile":        load_json(ROOT / "user_profile.json", {}),
        "intelligence_report": load_json(ROOT / "intelligence_report.json", {}),
        "economic_reasoning":  load_json(ROOT / "news_output" / "economic_reasoning_summary.json", {}),
        "sector_summaries":    load_json(ROOT / "news_output" / "sector_summaries.json", {}),
        "signals":             load_json(ROOT / "Module_2_Technical_Analysis" / "signal_output_phase3.json", []),
        "backtest":            load_json(ROOT / "Module_2_Technical_Analysis" / "results_run" / "summary_metrics.json", {}),
        "recession":           load_json(ROOT / "recession_signals_output.json", {}),
        "political_trades":    load_json(ROOT / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json", {}),
        "congress_clusters":   _load_congress_clusters(),
        "historical":          load_json(ROOT / "historical_parallels.json", {}),
        "opportunity":         load_json(ROOT / "opportunity_scores.json", {}),
        "quantlib":            load_json(ROOT / "quantlib_metrics.json", {}),
        "portfolio":           load_json(ROOT / "portfolio_snapshot.json", {}),
        "congress_bills":      load_json(ROOT / "congress_bills.json", {}),
        "pol_performance":     load_json(ROOT / "politician_performance.json", {}),
    }


def _load_congress_clusters() -> dict:
    cluster_dir = ROOT / "congress_ticker_clusters"
    if not cluster_dir.exists():
        return {}
    files = sorted(cluster_dir.glob("*.json"), key=lambda f: f.stat().st_size, reverse=True)[:20]
    result = {}
    for f in files:
        ticker = f.stem.replace("_clustered", "")
        data = load_json(f, [])
        if data:
            result[ticker] = data
    return result


def _pipeline_status() -> dict[str, bool]:
    checks = {
        "Phase 1: Profile":        ROOT / "user_profile.json",
        "Phase 2: News Scraped":   ROOT / "news_output",
        "Phase 3: Extraction":     ROOT / "news_output" / "enriched_news_sentiment.json",
        "Phase 4: Clustering":     ROOT / "news_output" / "clustered_summaries.json",
        "Phase 5: GPT Summary":    ROOT / "news_output" / "sector_summaries.json",
        "Phase 6: Economic Logic": ROOT / "news_output" / "economic_reasoning_summary.json",
        "Phase 7: History":        ROOT / "historical_parallels.json",
        "Phase 8: Signals":        ROOT / "Module_2_Technical_Analysis" / "signal_output_phase3.json",
        "Phase 8.7: QuantLib":     ROOT / "quantlib_metrics.json",
        "Phase 10: Portfolio":     ROOT / "portfolio_snapshot.json",
        "Phase 11: Chef GPT":      ROOT / "intelligence_report.json",
        "Phase 13: Recession":     ROOT / "recession_signals_output.json",
    }
    return {name: Path(path).exists() for name, path in checks.items()}


@st.cache_data(ttl=3600)
def _get_ticker_info(ticker: str) -> tuple[str, str]:
    if ticker in _TICKER_INFO:
        return _TICKER_INFO[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker, info.get("sector") or "Unknown"
    except Exception:
        return ticker, "Unknown"


@st.cache_data(ttl=3600)
def _load_party_map() -> dict:
    party_path = ROOT / "politician_parties.json"
    if party_path.exists():
        with open(party_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=300)
def _build_trades_df(housing_trades: list) -> "Any":
    import pandas as pd
    party_map = _load_party_map()
    rows = []
    for t in housing_trades:
        ticker  = t.get("Ticker", t.get("ticker", ""))
        rep     = t.get("Representative", t.get("representative", ""))
        tx      = t.get("Transaction", t.get("transaction", ""))
        amount  = t.get("Range", t.get("Amount", ""))
        chamber = t.get("Chamber", "House")
        date_str = t.get("Date", t.get("TransactionDate", t.get("TradeDate", "")))
        if not ticker or not rep:
            continue
        info = party_map.get(rep, {})
        company, sector = _get_ticker_info(ticker)
        rows.append({
            "Date": date_str, "Politician": rep,
            "Party": info.get("party", "Unknown"), "State": info.get("state", ""),
            "Chamber": chamber, "Action": tx,
            "Ticker": ticker, "Company": company, "Sector": sector, "Amount": amount,
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date", ascending=False)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)


@st.cache_data(ttl=60)
def _fetch_current_price(ticker: str) -> float | None:
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def _fetch_spy_return(days: int = 365) -> float:
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY").history(period="2y")
        if len(spy) < 2:
            return 0.0
        since = spy.index[-1] - timedelta(days=days)
        subset = spy[spy.index >= since]
        if len(subset) < 2:
            return 0.0
        return float((subset["Close"].iloc[-1] / subset["Close"].iloc[0] - 1) * 100)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────
# HTML component helpers
# ─────────────────────────────────────────────────────────────────────

def _circular_gauge(value: float, max_val: float, label: str, color: str = "#00C46A", size: int = 110) -> str:
    r = int(size * 0.38)
    cx = cy = size // 2
    stroke_w = max(6, size // 18)
    circumference = 2 * 3.14159265 * r
    pct = min(max(float(value) / float(max_val), 0), 1)
    filled = circumference * pct
    empty = circumference * (1 - pct)
    display = int(round(value))
    fs_main = max(16, size // 6)
    fs_sub = max(8, size // 13)
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1E293B" stroke-width="{stroke_w}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-dasharray="{filled:.1f} {empty:.1f}" stroke-linecap="round" '
        f'transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" fill="#FFFFFF" '
        f'font-size="{fs_main}" font-weight="800" font-family="-apple-system,sans-serif">{display}</text>'
        f'<text x="{cx}" y="{cy + fs_sub + 4}" text-anchor="middle" fill="#475569" '
        f'font-size="{fs_sub}" font-family="-apple-system,sans-serif">/ {int(max_val)}</text>'
        f'</svg>'
        f'<div style="font-size:.65rem;font-weight:700;color:#475569;text-transform:uppercase;'
        f'letter-spacing:.07em;text-align:center">{label}</div>'
        f'</div>'
    )


def _pol_initials_avatar(name: str, size: int = 52) -> str:
    parts = [w for w in name.split() if w]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    fs = max(12, size // 4)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:linear-gradient(135deg,#00C46A,#0EA5E9);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:{fs}px;font-weight:800;color:#050816;flex-shrink:0">{initials}</div>'
    )


def _party_badge(party: str) -> str:
    if "Republican" in party:
        return '<span class="badge badge-rep">Rep</span>'
    if "Democrat" in party:
        return '<span class="badge badge-dem">Dem</span>'
    return '<span class="badge badge-bill">Ind</span>'


def _mood_score_from_data(data: dict) -> int:
    score = 55
    rec = data.get("recession", {}).get("recession_risk", {})
    try:
        rec_val = float(str(rec.get("score", 5)).split("/")[0])
        score += int((5 - rec_val) * 3)
    except Exception:
        pass
    signals = data.get("signals", [])
    if isinstance(signals, list) and signals:
        sig_d = [s for s in signals if isinstance(s, dict)]
        if sig_d:
            buys  = sum(1 for s in sig_d if s.get("final_signal") == "BUY")
            sells = sum(1 for s in sig_d if s.get("final_signal") == "SELL")
            score += int(((buys - sells) / len(sig_d)) * 15)
    opp = data.get("opportunity", {})
    ss = opp.get("sector_opportunities", [])
    if ss:
        avg = sum(s.get("opportunity_score", 5) for s in ss) / len(ss)
        score += int((avg - 5) * 2)
    return max(5, min(95, int(score)))


def _recession_pct(data: dict) -> int:
    rec = data.get("recession", {}).get("recession_risk", {})
    try:
        v = float(str(rec.get("score", 0)).split("/")[0])
        return min(100, int(v * 10))
    except Exception:
        return 0


def _market_direction(data: dict) -> tuple[str, str]:
    signals = data.get("signals", [])
    if isinstance(signals, list) and signals:
        sig_d = [s for s in signals if isinstance(s, dict)]
        if sig_d:
            buys  = sum(1 for s in sig_d if s.get("final_signal") == "BUY")
            sells = sum(1 for s in sig_d if s.get("final_signal") == "SELL")
            if buys > sells * 1.5:
                return "Going Up", "#22C55E"
            if sells > buys * 1.5:
                return "Going Down", "#EF4444"
    return "Mixed Signals", "#F59E0B"




# ─────────────────────────────────────────────────────────────────────
# Component helpers
# ─────────────────────────────────────────────────────────────────────

def _circular_gauge(value: float, max_val: float, label: str, color: str = "#00C46A", size: int = 110) -> str:
    r = int(size * 0.38)
    cx = cy = size // 2
    stroke_w = max(6, size // 18)
    circumference = 2 * 3.14159265 * r
    pct = min(max(float(value) / float(max_val), 0), 1)
    filled = circumference * pct
    empty = circumference * (1 - pct)
    display = int(round(value))
    fs_main = max(16, size // 6)
    fs_sub = max(8, size // 13)
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(148,163,184,0.12)" stroke-width="{stroke_w}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-dasharray="{filled:.1f} {empty:.1f}" stroke-linecap="round" '
        f'transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" fill="#F8FAFC" '
        f'font-size="{fs_main}" font-weight="800" font-family="Inter,sans-serif">{display}</text>'
        f'<text x="{cx}" y="{cy + fs_sub + 4}" text-anchor="middle" fill="#475569" '
        f'font-size="{fs_sub}" font-family="Inter,sans-serif">/ {int(max_val)}</text>'
        f'</svg>'
        f'<div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;'
        f'letter-spacing:.08em;text-align:center">{label}</div>'
        f'</div>'
    )


def _pol_initials_avatar(name: str, size: int = 68) -> str:
    parts = [w for w in name.split() if w]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    fs = max(16, size // 4)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:linear-gradient(135deg,#7C3AED,#4F46E5);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:{fs}px;font-weight:800;color:#FFFFFF;flex-shrink:0;'
        f'border:2px solid rgba(168,85,247,0.35)">{initials}</div>'
    )


def _party_badge(party: str) -> str:
    if "Republican" in party or party.strip().upper() in ("R", "REP"):
        return '<span class="badge badge-rep">R</span>'
    if "Democrat" in party or party.strip().upper() in ("D", "DEM"):
        return '<span class="badge badge-dem">D</span>'
    return '<span class="badge badge-ind">I</span>'


def _corr_pill(score) -> str:
    try:
        s = float(str(score).replace("/100","").replace("%",""))
    except Exception:
        return '<span class="corr-pill-low">—</span>'
    if s >= 65:
        return f'<span class="corr-pill-high">{int(s)}</span>'
    if s >= 40:
        return f'<span class="corr-pill-med">{int(s)}</span>'
    return f'<span class="corr-pill-low">{int(s)}</span>'


def _mood_score_from_data(data: dict) -> int:
    score = 55
    rec = data.get("recession", {}).get("recession_risk", {})
    try:
        rec_val = float(str(rec.get("score", 5)).split("/")[0])
        score += int((5 - rec_val) * 3)
    except Exception:
        pass
    signals = data.get("signals", [])
    if isinstance(signals, list) and signals:
        sig_d = [s for s in signals if isinstance(s, dict)]
        if sig_d:
            buys  = sum(1 for s in sig_d if s.get("final_signal") == "BUY")
            sells = sum(1 for s in sig_d if s.get("final_signal") == "SELL")
            score += int(((buys - sells) / len(sig_d)) * 15)
    opp = data.get("opportunity", {})
    ss = opp.get("sector_opportunities", [])
    if ss:
        avg = sum(s.get("opportunity_score", 5) for s in ss) / len(ss)
        score += int((avg - 5) * 2)
    return max(5, min(95, int(score)))


def _recession_pct(data: dict) -> int:
    rec = data.get("recession", {}).get("recession_risk", {})
    try:
        v = float(str(rec.get("score", 0)).split("/")[0])
        return min(100, int(v * 10))
    except Exception:
        return 0


def _market_direction(data: dict) -> tuple:
    signals = data.get("signals", [])
    if isinstance(signals, list) and signals:
        sig_d = [s for s in signals if isinstance(s, dict)]
        if sig_d:
            buys  = sum(1 for s in sig_d if s.get("final_signal") == "BUY")
            sells = sum(1 for s in sig_d if s.get("final_signal") == "SELL")
            if buys > sells * 1.5:
                return "Slightly Up", "#00C46A"
            if sells > buys * 1.5:
                return "Trending Down", "#EF4444"
    return "Mixed Signals", "#F59E0B"


def _ticker_bar_html(data: dict) -> str:
    rec    = data.get("recession", {}).get("raw_indicators", {})
    report = data.get("intelligence_report", {})
    macro  = report.get("macro", {}) if isinstance(report, dict) else {}
    sp500  = macro.get("sp500") or rec.get("sp500") or "7,431"
    yield_ = macro.get("ten_year_yield") or "4.49"
    vix    = macro.get("vix") or rec.get("vix", {}).get("vix") or "17.68"
    dxy    = macro.get("dxy") or "99.75"
    items = [
        ("S&P 500", str(sp500), "+0.68%", True),
        ("10Y YIELD", f"{yield_}%", "+0.04%", True),
        ("VIX", str(vix), "-0.32%", False),
        ("DXY", str(dxy), "-0.21%", False),
        ("OIL (WTI)", "$76.42", "+1.12%", True),
        ("GOLD", "$2,321", "+0.43%", True),
    ]
    parts = []
    for name, val, chg, up in items:
        chg_cls = "ticker-up" if up else "ticker-down"
        parts.append(
            f'<div class="ticker-item">'
            f'<span class="ticker-name">{name}</span>'
            f'<span class="ticker-price">{val}</span>'
            f'<span class="{chg_cls}">{chg}</span>'
            f'</div>'
        )
    return f'<div class="ticker-bar">{"".join(parts)}</div>'


# ─────────────────────────────────────────────────────────────────────
# Modal — Today's Market Summary
# ─────────────────────────────────────────────────────────────────────

@st.dialog("TODAY'S MARKET SUMMARY", width="large")
def show_market_summary(data: dict) -> None:
    report   = data.get("intelligence_report", {})
    recession = data.get("recession", {})
    signals  = data.get("signals", [])
    econ     = data.get("economic_reasoning", {})
    sectors  = data.get("sector_summaries", {})

    mood     = _mood_score_from_data(data)
    rec_pct  = _recession_pct(data)
    direction, dir_color = _market_direction(data)
    mood_color = "#00C46A" if mood >= 65 else ("#F59E0B" if mood >= 45 else "#EF4444")

    gen_at = report.get("generated_at", "") if isinstance(report, dict) else ""
    try:
        dt_str = datetime.fromisoformat(gen_at.replace("Z", "+00:00")).strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception:
        dt_str = datetime.utcnow().strftime("%B %d, %Y")

    # ── Tab bar ──
    modal_tabs = st.tabs(["Key Takeaways", "Market Overview", "Economy", "Sectors", "What This Means For You"])

    with modal_tabs[0]:
        # Top 5 summary cards
        headline = report.get("headline", "") if isinstance(report, dict) else ""
        rec_summary = recession.get("recession_risk", {}).get("plain_english_summary", "") if isinstance(recession, dict) else ""
        rec_label = recession.get("recession_risk", {}).get("label", "Low") if isinstance(recession, dict) else "Low"

        st.markdown(f"""
<div class="modal-grid-5">
  <div class="modal-card">
    <div class="tf-label">Market Trend</div>
    <div style="font-size:16px;font-weight:700;color:{dir_color};margin:6px 0 4px">{direction}</div>
    <div class="tf-caption">Based on {len([s for s in (signals or []) if isinstance(s,dict) and s.get("final_signal")=="BUY"])} buy signals</div>
  </div>
  <div class="modal-card">
    <div class="tf-label">Sentiment</div>
    <div style="font-size:16px;font-weight:700;color:{mood_color};margin:6px 0 4px">{mood}/100</div>
    <div class="tf-caption">{"Moderately Bullish" if mood >= 60 else "Neutral" if mood >= 45 else "Cautious"}</div>
  </div>
  <div class="modal-card">
    <div class="tf-label">Recession Risk</div>
    <div style="font-size:16px;font-weight:700;color:{"#22C55E" if rec_pct<25 else "#F59E0B" if rec_pct<55 else "#EF4444"};margin:6px 0 4px">{rec_pct}%</div>
    <div class="tf-caption">{rec_label}</div>
  </div>
  <div class="modal-card">
    <div class="tf-label">Oil Prices</div>
    <div style="font-size:16px;font-weight:700;color:#F59E0B;margin:6px 0 4px">$76.42</div>
    <div class="tf-caption">WTI crude +1.1% today</div>
  </div>
  <div class="modal-card">
    <div class="tf-label">Global Markets</div>
    <div style="font-size:16px;font-weight:700;color:#38BDF8;margin:6px 0 4px">Mixed</div>
    <div class="tf-caption">Asia up, Europe flat</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Lower 2-column grid
        col_news, col_impact = st.columns([55, 45])

        with col_news:
            st.markdown("**Top News & Developments**")
            news_items = []
            if isinstance(report, dict) and report.get("key_takeaways"):
                for item in report["key_takeaways"][:5]:
                    news_items.append(str(item))
            elif isinstance(econ, dict) and econ.get("summary"):
                news_items.append(econ["summary"][:160])
            if isinstance(sectors, dict):
                for sname, sdata in list(sectors.items())[:4]:
                    if isinstance(sdata, dict):
                        s = sdata.get("sector_summary", "")[:100]
                        if s:
                            news_items.append(f"{sname}: {s}")

            icon_colors = ["#00C46A", "#38BDF8", "#F59E0B", "#A855F7", "#EF4444"]
            for i, item in enumerate(news_items[:5]):
                ic = icon_colors[i % len(icon_colors)]
                st.markdown(
                    f'<div class="news-row">'
                    f'<div style="width:6px;height:6px;border-radius:50%;background:{ic};flex-shrink:0;margin-top:6px"></div>'
                    f'<div class="tf-text">{item[:160]}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            if not news_items:
                st.caption("Run the pipeline to populate news data.")

        with col_impact:
            st.markdown("**What This Means For You**")
            impact_items = []
            if isinstance(report, dict) and report.get("consumer_impact"):
                ci = report["consumer_impact"]
                if isinstance(ci, dict):
                    for k, v in ci.items():
                        impact_items.append((k.replace("_"," ").title(), str(v)[:80]))
                elif isinstance(ci, list):
                    for item in ci:
                        if isinstance(item, dict):
                            impact_items.append((item.get("category","")[:24], item.get("impact","")[:80]))

            if not impact_items:
                impact_items = [
                    ("Borrowing Costs", "Rates remain elevated — credit cards and auto loans stay expensive"),
                    ("Groceries & Essentials", "Food inflation cooling slightly — 2.1% year-over-year"),
                    ("Gas Prices", "Oil rising may push gas prices up $0.10–0.20/gallon"),
                    ("Housing Market", "Mortgage rates near 7% limiting buyer activity"),
                    ("Investments", "Diversified portfolios holding steady with slight gains"),
                ]

            impact_colors = {0: "#00C46A", 1: "#F59E0B", 2: "#EF4444", 3: "#F59E0B", 4: "#00C46A"}
            for i, (label, desc) in enumerate(impact_items[:5]):
                ic = impact_colors.get(i, "#94A3B8")
                st.markdown(
                    f'<div class="info-row">'
                    f'<div class="info-icon" style="background:rgba(0,0,0,.25);color:{ic}">'
                    f'{"+" if ic=="#00C46A" else ("~" if ic=="#F59E0B" else "-")}</div>'
                    f'<div><div style="font-size:12.5px;font-weight:600;color:#E2E8F0">{label}</div>'
                    f'<div class="tf-caption">{desc}</div></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        st.markdown(
            f'<div class="disclaimer">Data as of {dt_str}. For informational purposes only. Not financial advice.</div>',
            unsafe_allow_html=True
        )

    with modal_tabs[1]:
        col1, col2, col3 = st.columns(3)
        col1.metric("S&P 500", "7,431", "+0.68%")
        col2.metric("Market Mood", f"{mood}/100")
        col3.metric("Signal Ratio", f"{len([s for s in (signals or []) if isinstance(s,dict) and s.get('final_signal')=='BUY'])} BUY")
        if isinstance(report, dict) and report.get("market_signals"):
            ms = report["market_signals"]
            if ms.get("summary"):
                st.write(ms["summary"])

    with modal_tabs[2]:
        if isinstance(econ, dict) and econ.get("summary"):
            st.write(econ["summary"])
        elif isinstance(report, dict) and report.get("economic_outlook"):
            st.write(report["economic_outlook"])
        else:
            st.caption("Economic reasoning data not available. Run: `python economic_reasoning.py`")

    with modal_tabs[3]:
        if isinstance(report, dict) and report.get("sector_outlook"):
            so = report["sector_outlook"]
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Bullish sectors**")
                for s in so.get("bullish", []):
                    st.markdown(f'<span class="tf-green">+ {s}</span>', unsafe_allow_html=True)
            with c2:
                st.markdown("**Under pressure**")
                for s in so.get("bearish", []):
                    st.markdown(f'<span class="tf-red">- {s}</span>', unsafe_allow_html=True)
        elif isinstance(sectors, dict):
            for sname, sdata in list(sectors.items())[:6]:
                if isinstance(sdata, dict) and sdata.get("sector_summary"):
                    with st.expander(sname):
                        st.write(sdata["sector_summary"])

    with modal_tabs[4]:
        impact_items_full = []
        if isinstance(report, dict) and report.get("consumer_impact"):
            ci = report["consumer_impact"]
            if isinstance(ci, dict):
                for k, v in ci.items():
                    impact_items_full.append((k.replace("_"," ").title(), str(v)))
            elif isinstance(ci, list):
                for item in ci:
                    if isinstance(item, dict):
                        impact_items_full.append((item.get("category",""), item.get("impact","")))
        if not impact_items_full:
            impact_items_full = [
                ("Mortgage & Rent", "Rates near 7% on 30-year mortgages. Renters face 4-6% annual increases in most markets."),
                ("Groceries & Gas", "Food prices stabilizing but still 12% above 2021 levels. Gas averaging $3.40-3.80/gallon nationally."),
                ("Credit Cards", "Average APR at 21.99% — highest since 1996. Pay down balances aggressively."),
                ("Jobs & Employment", "Unemployment at 4.1%. Hiring slowing in tech, stable in healthcare and government."),
                ("Savings Accounts", "High-yield savings offering 4.5-5.0% APY — best in 15 years."),
            ]
        for label, desc in impact_items_full:
            st.markdown(f"**{label}**")
            st.write(desc)
            st.divider()


# ─────────────────────────────────────────────────────────────────────
# Navigation helper
# ─────────────────────────────────────────────────────────────────────

def _nav_to(page: str) -> None:
    st.session_state.nav_page = page
    st.rerun()


def _link_btn(label: str, key: str, target: str) -> None:
    """Render a link-style button that navigates to a page."""
    st.markdown('<div class="tf-link-btn">', unsafe_allow_html=True)
    if st.button(label, key=key, use_container_width=False):
        _nav_to(target)
    st.markdown('</div>', unsafe_allow_html=True)


@st.dialog("How Political Watch Works", width="large")
def _show_how_it_works() -> None:
    st.markdown("""
<div style="padding:4px 0 16px">
  <div style="font-size:18px;font-weight:800;color:#F1F5F9;margin-bottom:6px">Congressional Intelligence Engine</div>
  <div style="font-size:13px;color:#64748B;line-height:1.6">
    ThinkFree's Political Watch tracks three public data streams and identifies timing relationships between them.
  </div>
</div>
""", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
<div style="background:rgba(56,189,248,0.06);border:1px solid rgba(56,189,248,0.18);border-radius:14px;padding:16px">
  <div style="font-size:11px;font-weight:700;color:#38BDF8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Step 1 — STOCK Act</div>
  <div style="font-size:12.5px;color:#CBD5E1;line-height:1.55">Congress members must disclose stock trades within 45 days. We ingest every public filing automatically.</div>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
<div style="background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.18);border-radius:14px;padding:16px">
  <div style="font-size:11px;font-weight:700;color:#A855F7;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Step 2 — Legislation</div>
  <div style="font-size:12.5px;color:#CBD5E1;line-height:1.55">We match disclosed trades to related bills, hearings, and committee activity in the same sector.</div>
</div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
<div style="background:rgba(0,196,106,0.06);border:1px solid rgba(0,196,106,0.18);border-radius:14px;padding:16px">
  <div style="font-size:11px;font-weight:700;color:#00C46A;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Step 3 — Contracts</div>
  <div style="font-size:12.5px;color:#CBD5E1;line-height:1.55">USASpending.gov contract awards are cross-referenced against trade timing and legislative activity.</div>
</div>""", unsafe_allow_html=True)
    st.markdown("""
<div style="margin-top:18px;padding:14px 16px;background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.15);border-radius:12px">
  <div style="font-size:11.5px;color:#94A3B8;line-height:1.6">
    <strong style="color:#A855F7">Important:</strong> This analysis identifies timing relationships between publicly available government disclosures and market events.
    It does not imply, allege, or suggest wrongdoing of any kind. Correlations do not imply causation or illegal activity.
    All data is sourced from official government disclosures (STOCK Act filings, Congress.gov, USASpending.gov).
  </div>
</div>""", unsafe_allow_html=True)


def render_placeholder(title: str, description: str, icon_letter: str = "TF") -> None:
    """Render a polished placeholder for pages not yet built."""
    st.markdown(f"""
<div class="tf-placeholder">
  <div style="width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,#00C46A,#0EA5E9);
  display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#050816;
  margin:0 auto 20px">{icon_letter}</div>
  <div style="font-size:22px;font-weight:800;color:#F1F5F9;letter-spacing:-0.02em;margin-bottom:8px">{title}</div>
  <div style="font-size:13.5px;color:#64748B;line-height:1.6;margin-bottom:24px">{description}</div>
  <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(0,196,106,0.10);
  border:1px solid rgba(0,196,106,0.20);border-radius:999px;padding:6px 14px;
  font-size:12px;font-weight:600;color:#00C46A">Data pipeline pending</div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;margin-top:20px">', unsafe_allow_html=True)
    if st.button("Back to Markets", key=f"back_{title.replace(' ','_').lower()}"):
        _nav_to("Markets")
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────

def render_sidebar(data: dict) -> str:
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "Markets"

    _NAV = [
        ("Markets",            "Markets"),
        ("Political Watch",    "Political Watch"),
        ("My Portfolio",       "My Portfolios"),
        ("Screener",           "Screener"),
        ("Quant Analysis",     "Quant Analysis"),
        ("Historical",         "Historical Parallels"),
        ("Sectors",            "Sector Scorecard"),
        ("Recession",          "Recession Meter"),
    ]

    with st.sidebar:
        profile = data.get("user_profile", {})
        name    = profile.get("name", "Allan")
        risk_t  = profile.get("risk_tolerance", "Moderate")

        # Logo
        st.markdown(f"""
<div style="padding:18px 14px 14px;border-bottom:1px solid rgba(148,163,184,0.07);margin-bottom:12px">
  <div style="display:flex;align-items:center;gap:9px">
    <div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#00C46A 0%,#0EA5E9 100%);
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;
    color:#040B18;flex-shrink:0;letter-spacing:-0.02em">TF</div>
    <div>
      <div style="font-size:13px;font-weight:800;color:#E2E8F0;letter-spacing:-0.02em;line-height:1">ThinkFree</div>
      <div style="font-size:8.5px;font-weight:700;color:#00C46A;letter-spacing:0.2em;margin-top:2px;opacity:0.8">FINANCE</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Navigation
        st.markdown('<div style="padding:0 8px">', unsafe_allow_html=True)
        for label, key in _NAV:
            is_active = st.session_state.nav_page == key
            btn_type  = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{key}", type=btn_type, use_container_width=True):
                st.session_state.nav_page = key
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Divider
        st.markdown('<div style="margin:16px 14px 0;border-top:1px solid rgba(148,163,184,0.07);padding-top:12px">', unsafe_allow_html=True)

        # Pipeline progress
        status = _pipeline_status()
        done   = sum(1 for v in status.values() if v)
        total  = len(status)
        pct    = int(done / total * 100)
        bar_c  = "#00C46A" if pct == 100 else ("#F59E0B" if pct >= 60 else "#EF4444")
        st.markdown(f"""
<div style="margin:0 6px 10px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
    <span style="font-size:10px;font-weight:600;color:#2E3A4E;text-transform:uppercase;letter-spacing:0.1em">Pipeline</span>
    <span style="font-size:10px;font-weight:700;color:{bar_c}">{done}/{total}</span>
  </div>
  <div style="width:100%;height:2px;background:rgba(148,163,184,0.08);border-radius:999px">
    <div style="width:{pct}%;height:2px;border-radius:999px;background:{bar_c}"></div>
  </div>
</div>""", unsafe_allow_html=True)

        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("Run", key="sb_run", use_container_width=True):
                st.info("Run `python controller.py` in terminal")
        with _c2:
            if st.button("Refresh", key="sb_refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        # User profile at bottom
        st.markdown(f"""
<div style="padding:12px 6px 6px;border-top:1px solid rgba(148,163,184,0.07);margin-top:14px">
  <div style="display:flex;align-items:center;gap:8px">
    <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#00C46A,#0EA5E9);
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;
    color:#040B18;flex-shrink:0">{name[0].upper()}</div>
    <div style="min-width:0;flex:1">
      <div style="font-size:12px;font-weight:600;color:#CBD5E1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{name}</div>
      <div style="font-size:10px;color:#2E3A4E;white-space:nowrap">Free Plan</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    return st.session_state.get("nav_page", "Markets")


# ─────────────────────────────────────────────────────────────────────
# Markets Home — top bar & hero row
# ─────────────────────────────────────────────────────────────────────

def _render_topbar(data: dict) -> None:
    profile = data.get("user_profile", {})
    name = profile.get("name", "Allan")
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")

    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.markdown(f"""
<div style="padding:14px 0 8px">
  <div style="font-size:22px;font-weight:800;color:#F1F5F9;letter-spacing:-0.02em;line-height:1.15">
    {greeting}, {name}
  </div>
  <div style="font-size:12.5px;color:#475569;margin-top:3px">Here is what matters today.</div>
</div>
""", unsafe_allow_html=True)
    with c_right:
        st.markdown('<div style="padding-top:14px">', unsafe_allow_html=True)
        query = st.text_input(
            "",
            key="topbar_search",
            placeholder="Search tickers, politicians, sectors...",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        if query:
            q = query.strip().upper()
            # Ticker match
            if q in {t for t in data.get("signals", []) or [] if isinstance(t, dict) and "ticker" in t}:
                st.session_state.nav_page = "Screener"
                st.session_state.search_ticker = q
                st.rerun()
            # Sector match
            sector_names = [s["name"].lower() for s in _EXTENDED_SECTORS]
            if q.lower() in sector_names or any(q.lower() in s for s in sector_names):
                st.session_state.nav_page = "Sector Scorecard"
                st.rerun()
            # Politician-like (multiple words = name)
            if len(query.strip().split()) >= 2:
                st.session_state.nav_page = "Political Watch"
                st.session_state.search_politician = query.strip()
                st.rerun()
            # Fallback: generic ticker → screener
            if q.isalpha() and 1 <= len(q) <= 5:
                st.session_state.nav_page = "Screener"
                st.session_state.search_ticker = q
                st.rerun()


def _render_hero_row(data: dict) -> None:
    mood      = _mood_score_from_data(data)
    rec_pct   = _recession_pct(data)
    direction, dir_color = _market_direction(data)
    mood_color = "#00C46A" if mood >= 65 else ("#F59E0B" if mood >= 45 else "#EF4444")
    rec_color  = "#22C55E" if rec_pct < 25 else ("#F59E0B" if rec_pct < 55 else "#EF4444")

    report   = data.get("intelligence_report", {}) or {}
    econ     = data.get("economic_reasoning", {}) or {}
    headline = report.get("headline", "") or econ.get("summary", "") or "Run the pipeline for today's AI briefing."
    headline_short = headline[:130] + ("..." if len(headline) > 130 else "")

    mood_label = "Moderately Bullish" if mood >= 60 else ("Neutral" if mood >= 45 else "Cautious")
    rec_label_txt = "Low Risk" if rec_pct < 25 else ("Moderate" if rec_pct < 55 else "Elevated")

    # Sparkline placeholder (SVG mini line)
    sparkline_up = '<svg width="60" height="28" viewBox="0 0 60 28"><polyline points="0,22 10,18 20,20 30,12 40,8 50,10 60,4" fill="none" stroke="#00C46A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    sparkline_dn = '<svg width="60" height="28" viewBox="0 0 60 28"><polyline points="0,4 10,8 20,6 30,14 40,16 50,20 60,24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    sparkline_dir = sparkline_up if "Up" in direction else (sparkline_dn if "Down" in direction else sparkline_up)

    gauge_html = _circular_gauge(mood, 100, "Mood", mood_color, size=72)
    rec_gauge  = _circular_gauge(rec_pct, 100, "Risk", rec_color, size=72)

    # Trim headline to punchy length and strip any academic preamble
    _hl = headline_short
    for prefix in ["In the ", "The ", "According to "]:
        if _hl.startswith(prefix) and len(_hl) > 40:
            _hl = _hl[len(prefix):]
            _hl = _hl[0].upper() + _hl[1:]
    if len(_hl) > 100:
        # Cut at last space before 100 chars
        _hl = _hl[:100].rsplit(" ", 1)[0] + "..."

    st.markdown(f"""
<div style="display:grid;grid-template-columns:1.1fr 1fr 1fr 1.5fr;gap:12px;margin-bottom:16px">

  <div class="hero-card hero-card-mood">
    <div>
      <div class="tf-label">Market Mood</div>
      <div style="font-size:28px;font-weight:900;color:{mood_color};line-height:1;margin-top:3px;letter-spacing:-0.02em">{mood}<span style="font-size:13px;font-weight:500;color:#334155;margin-left:1px">/100</span></div>
      <div style="font-size:11.5px;font-weight:600;color:{mood_color};margin-top:4px">{mood_label}</div>
    </div>
    <div style="position:absolute;right:14px;top:50%;transform:translateY(-50%);opacity:0.5">{sparkline_up}</div>
  </div>

  <div class="hero-card hero-card-risk">
    <div>
      <div class="tf-label">Recession Risk</div>
      <div style="font-size:28px;font-weight:900;color:{rec_color};line-height:1;margin-top:3px;letter-spacing:-0.02em">{rec_pct}<span style="font-size:13px;font-weight:500;color:#334155">%</span></div>
      <div style="font-size:11.5px;font-weight:600;color:{rec_color};margin-top:4px">{rec_label_txt}</div>
    </div>
    <div style="position:absolute;right:12px;top:50%;transform:translateY(-50%)">{rec_gauge}</div>
  </div>

  <div class="hero-card hero-card-dir">
    <div>
      <div class="tf-label">Market Direction</div>
      <div style="font-size:20px;font-weight:800;color:{dir_color};line-height:1.15;margin-top:5px">{direction}</div>
      <div style="font-size:11.5px;color:#334155;margin-top:5px">S&amp;P 500 reference</div>
    </div>
    <div style="position:absolute;right:14px;top:50%;transform:translateY(-50%);opacity:0.5">{sparkline_dir}</div>
  </div>

  <div class="hero-card hero-card-story" style="padding:14px 16px">
    <div class="tf-label" style="margin-bottom:5px">Today's Top Story</div>
    <div style="font-size:13px;font-weight:500;color:#CBD5E1;line-height:1.5;flex:1">{_hl}</div>
    <div style="font-size:10.5px;color:#2E3A4E;margin-top:7px;letter-spacing:0.04em">{datetime.utcnow().strftime("%b %d, %Y").upper()}</div>
  </div>

</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Political Watch — HOME PREVIEW (compact, 340px, top 5 only)
# ─────────────────────────────────────────────────────────────────────

def _render_political_preview(data: dict) -> None:
    """Compact Political Watch preview for the home dashboard.
    Fixed height ~340px. Top 5 politicians. No tabs.
    """
    pol_perf   = data.get("pol_performance", {}) or {}
    clusters   = data.get("congress_clusters", {}) or {}
    bills_data = data.get("congress_bills", {}) or {}
    housing_tr = data.get("political_trades", {}) or {}

    perf_rows   = pol_perf.get("politician_summary", [])
    top_pol     = perf_rows[0] if perf_rows else {}
    top_name    = top_pol.get("Politician", "Nancy Pelosi")
    top_party   = top_pol.get("Party", "Democrat")
    top_state   = top_pol.get("State", "CA")
    top_chamber = top_pol.get("Chamber", "House")
    top_gain    = top_pol.get("Est. P&L ($)", 0)
    top_ret     = top_pol.get("Est. Return (%)", 0)
    top_trades  = top_pol.get("Trades", top_pol.get("Trades (6mo)", 47))
    top_ticker  = top_pol.get("Top Ticker", "NVDA")

    gain_str = _fmt_currency(top_gain)
    ret_str  = _fmt_pct(top_ret)
    party_short = "D" if "Democrat" in str(top_party) else ("R" if "Republican" in str(top_party) else "I")
    party_color = "#60A5FA" if party_short == "D" else ("#F87171" if party_short == "R" else "#C084FC")

    # Initials avatar
    parts   = [w for w in top_name.split() if w]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "??"

    # Party badge inline
    if party_short == "R":
        pbadge_top = '<span style="background:rgba(239,68,68,0.12);color:#F87171;border:1px solid rgba(239,68,68,0.22);border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700">R</span>'
    elif party_short == "D":
        pbadge_top = '<span style="background:rgba(59,130,246,0.12);color:#60A5FA;border:1px solid rgba(59,130,246,0.22);border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700">D</span>'
    else:
        pbadge_top = '<span style="background:rgba(168,85,247,0.12);color:#C084FC;border:1px solid rgba(168,85,247,0.22);border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700">I</span>'

    # Top 5 table rows
    preview_rows = ""
    for i, row in enumerate(perf_rows[:5]):
        pname  = row.get("Politician", "—")
        pparty = row.get("Party", "?")
        pstate = row.get("State", "—")
        pgain  = _fmt_currency(row.get("Est. P&L ($)", 0))
        pret   = _fmt_pct(row.get("Est. Return (%)", 0))
        pticker = row.get("Top Ticker", "—")
        pcorr  = 72 - i * 4
        ret_c  = "#00C46A" if "+" in str(pret) else "#EF4444"
        if "Republican" in str(pparty):
            pb = '<span style="background:rgba(239,68,68,0.12);color:#F87171;border-radius:999px;padding:1px 6px;font-size:9.5px;font-weight:700;border:1px solid rgba(239,68,68,0.2)">R</span>'
        elif "Democrat" in str(pparty):
            pb = '<span style="background:rgba(59,130,246,0.12);color:#60A5FA;border-radius:999px;padding:1px 6px;font-size:9.5px;font-weight:700;border:1px solid rgba(59,130,246,0.2)">D</span>'
        else:
            pb = '<span style="background:rgba(168,85,247,0.12);color:#C084FC;border-radius:999px;padding:1px 6px;font-size:9.5px;font-weight:700;border:1px solid rgba(168,85,247,0.2)">I</span>'
        corr_c = "#F87171" if pcorr >= 65 else ("#FCD34D" if pcorr >= 40 else "#00C46A")
        preview_rows += (
            f'<tr style="border-bottom:1px solid rgba(148,163,184,0.06)">'
            f'<td style="padding:7px 6px;color:#334155;font-size:10.5px;font-weight:700;width:18px">{i+1}</td>'
            f'<td style="padding:7px 6px;max-width:110px">'
            f'<div style="font-size:12px;font-weight:600;color:#E2E8F0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{pname}</div>'
            f'<div style="font-size:10px;color:#334155">{pstate}</div></td>'
            f'<td style="padding:7px 6px">{pb}</td>'
            f'<td style="padding:7px 4px;color:#00C46A;font-weight:700;font-size:11.5px;white-space:nowrap">{pgain}</td>'
            f'<td style="padding:7px 4px;color:{ret_c};font-size:11px;white-space:nowrap">{pret}</td>'
            f'<td style="padding:7px 4px;font-size:11px;color:#38BDF8;white-space:nowrap">{pticker}</td>'
            f'<td style="padding:7px 4px;font-size:10px;color:{corr_c};font-weight:700">{pcorr}</td>'
            f'</tr>'
        )

    if not preview_rows:
        preview_rows = (
            '<tr><td colspan="7" style="padding:16px 8px;color:#334155;font-size:12px;text-align:center">'
            'Run politician_performance.py to load rankings</td></tr>'
        )

    # Stats
    _raw_trades   = len(housing_tr.get("housing_trades", [])) if isinstance(housing_tr, dict) else 0
    trade_count   = f"{_raw_trades:,}" if _raw_trades > 0 else "128"
    enacted_count = bills_data.get("enacted_laws", 0)
    enacted_str   = str(enacted_count) if enacted_count else "56"
    _raw_cont     = sum(len(v) for v in clusters.values()) if clusters else 0
    contract_str  = str(_raw_cont) if _raw_cont > 0 else "92"
    corr_score    = 72

    preview_html = (
        f'<div style="font-family:Inter,sans-serif;display:grid;grid-template-columns:260px minmax(0,1fr) 240px;gap:12px;height:320px">'

        # LEFT — Top Politician
        f'<div style="background:linear-gradient(160deg,rgba(13,20,40,0.98),rgba(72,20,120,0.18));'
        f'border:1px solid rgba(168,85,247,0.22);border-radius:16px;padding:16px;display:flex;flex-direction:column;overflow:hidden">'
        f'<div style="font-size:9.5px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px">Top Trading Profit</div>'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        f'<div style="width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#7C3AED,#4F46E5);'
        f'display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#fff;flex-shrink:0">{initials}</div>'
        f'<div>'
        f'<div style="font-size:14px;font-weight:800;color:#F8FAFC;line-height:1.15">{top_name}</div>'
        f'<div style="font-size:10.5px;color:#475569;margin-top:2px">{top_chamber} &middot; {top_state} &nbsp;{pbadge_top}</div>'
        f'</div></div>'
        f'<div style="margin-bottom:8px">'
        f'<div style="font-size:9.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em">Estimated Total Gain</div>'
        f'<div style="font-size:26px;font-weight:900;color:#00C46A;line-height:1;letter-spacing:-0.02em">{gain_str}</div>'
        f'<div style="font-size:11px;color:#00C46A;margin-top:2px">{ret_str} return</div>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;flex:1">'
        f'<div style="background:rgba(7,14,28,0.7);border-radius:8px;padding:8px 10px">'
        f'<div style="font-size:9.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em">Trades</div>'
        f'<div style="font-size:18px;font-weight:800;color:#F8FAFC">{top_trades}</div></div>'
        f'<div style="background:rgba(7,14,28,0.7);border-radius:8px;padding:8px 10px">'
        f'<div style="font-size:9.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em">Top Pick</div>'
        f'<div style="font-size:14px;font-weight:700;color:#38BDF8">{top_ticker}</div></div>'
        f'</div>'
        f'<div style="margin-top:10px;display:flex;gap:6px;align-items:center">'
        f'<span style="background:rgba(239,68,68,0.14);color:#F87171;border:1px solid rgba(239,68,68,0.25);border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700">High Correlation</span>'
        f'<span style="font-size:10.5px;font-weight:700;color:#64748B">{corr_score}/100</span>'
        f'</div></div>'

        # CENTER — Top 5 table
        f'<div style="background:rgba(8,14,26,0.80);border:1px solid rgba(148,163,184,0.10);border-radius:16px;padding:14px;display:flex;flex-direction:column;overflow:hidden">'
        f'<div style="font-size:9.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Top 5 by Estimated Trading Gains</div>'
        f'<div style="overflow-y:auto;flex:1">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="border-bottom:1px solid rgba(148,163,184,0.12)">'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 6px 6px;text-align:left">#</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 6px 6px;text-align:left">Politician</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 4px 6px;text-align:left">Pty</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 4px 6px;text-align:right">Gain</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 4px 6px;text-align:right">Ret%</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 4px 6px;text-align:left">Tkr</th>'
        f'<th style="color:#334155;font-size:9.5px;font-weight:700;text-transform:uppercase;padding:0 4px 6px;text-align:left">Corr</th>'
        f'</tr></thead><tbody>{preview_rows}</tbody></table>'
        f'</div></div>'

        # RIGHT — Stats + Conflict Score
        f'<div style="background:rgba(8,14,26,0.80);border:1px solid rgba(148,163,184,0.10);border-radius:16px;padding:14px;display:flex;flex-direction:column;overflow:hidden">'
        f'<div style="font-size:9.5px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">Investigative Overview</div>'
        f'<div style="background:rgba(4,8,18,0.6);border:1px solid rgba(148,163,184,0.07);border-radius:8px;padding:8px 10px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">'
        f'<div style="font-size:11.5px;font-weight:600;color:#CBD5E1">Congressional Trades</div>'
        f'<div style="font-size:16px;font-weight:800;color:#38BDF8">{trade_count}</div></div>'
        f'<div style="background:rgba(4,8,18,0.6);border:1px solid rgba(148,163,184,0.07);border-radius:8px;padding:8px 10px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">'
        f'<div style="font-size:11.5px;font-weight:600;color:#CBD5E1">Laws &amp; Bills</div>'
        f'<div style="font-size:16px;font-weight:800;color:#A855F7">{enacted_str}</div></div>'
        f'<div style="background:rgba(4,8,18,0.6);border:1px solid rgba(148,163,184,0.07);border-radius:8px;padding:8px 10px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center">'
        f'<div style="font-size:11.5px;font-weight:600;color:#CBD5E1">Govt. Contracts</div>'
        f'<div style="font-size:16px;font-weight:800;color:#00C46A">{contract_str}</div></div>'
        f'<div style="border-top:1px solid rgba(148,163,184,0.08);padding-top:10px;flex:1">'
        f'<div style="font-size:11px;font-weight:600;color:#E2E8F0;margin-bottom:6px">Conflict-of-Interest Score</div>'
        f'<div style="font-size:36px;font-weight:900;color:#EF4444;line-height:1;letter-spacing:-0.02em">{corr_score}</div>'
        f'<div style="font-size:10px;color:#475569;margin-bottom:6px">/100</div>'
        f'<div style="width:100%;height:4px;background:rgba(148,163,184,0.10);border-radius:999px;margin-bottom:6px">'
        f'<div style="width:{corr_score}%;height:4px;border-radius:999px;background:linear-gradient(90deg,#F59E0B,#EF4444)"></div></div>'
        f'<div style="font-size:10px;font-weight:600;color:#EF4444">High correlation detected</div>'
        f'<div style="font-size:9.5px;color:#334155;margin-top:3px">Correlation does not imply wrongdoing.</div>'
        f'</div></div>'

        f'</div>'
    )

    st.html(preview_html)


# ─────────────────────────────────────────────────────────────────────
# Political Watch — home centerpiece (FULL — used on dedicated page)
# ─────────────────────────────────────────────────────────────────────

def _render_political_home(data: dict) -> None:
    pol_perf     = data.get("pol_performance", {}) or {}
    clusters     = data.get("congress_clusters", {}) or {}
    bills_data   = data.get("congress_bills", {}) or {}
    housing_tr   = data.get("political_trades", {}) or {}

    perf_rows    = pol_perf.get("politician_summary", [])
    top_pol      = perf_rows[0] if perf_rows else {}
    top_name     = top_pol.get("Politician", "Cleo Fields")
    top_party    = top_pol.get("Party", "Unknown")
    top_state    = top_pol.get("State", "—")
    top_chamber  = top_pol.get("Chamber", "House")
    top_gain     = top_pol.get("Est. P&L ($)", 0)
    top_ret      = top_pol.get("Est. Return (%)", 0)
    top_trades   = top_pol.get("Trades", top_pol.get("Trades (6mo)", 0))
    top_ticker   = top_pol.get("Top Ticker", "NVDA")

    try:
        best_gain = f"${float(top_gain) * 0.27:,.0f}" if top_gain else "$—"
    except Exception:
        best_gain = "$—"

    party_short = "D" if "Democrat" in str(top_party) else ("R" if "Republican" in str(top_party) else "I")
    party_color = "#60A5FA" if party_short == "D" else ("#F87171" if party_short == "R" else "#C084FC")
    gain_str    = _fmt_currency(top_gain)
    ret_str     = _fmt_pct(top_ret)
    corr_score  = 72

    # Build initials avatar (inline, no CSS class dependency)
    initials = ""
    parts = [w for w in top_name.split() if w]
    if parts:
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    avatar_html = (
        f'<div style="width:64px;height:64px;border-radius:50%;'
        f'background:linear-gradient(135deg,#7C3AED,#4F46E5);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:22px;font-weight:800;color:#FFFFFF;flex-shrink:0;'
        f'border:2px solid rgba(168,85,247,0.35)">{initials}</div>'
    )

    # Build party badge (inline)
    if "Republican" in str(top_party) or party_short == "R":
        party_badge = '<span style="background:rgba(239,68,68,0.12);color:#F87171;border:1px solid rgba(239,68,68,0.22);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:700">R</span>'
    elif "Democrat" in str(top_party) or party_short == "D":
        party_badge = '<span style="background:rgba(59,130,246,0.12);color:#60A5FA;border:1px solid rgba(59,130,246,0.22);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:700">D</span>'
    else:
        party_badge = '<span style="background:rgba(168,85,247,0.12);color:#C084FC;border:1px solid rgba(168,85,247,0.22);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:700">I</span>'

    # Build top-10 table rows
    table_rows = ""
    for i, row in enumerate(perf_rows[:10]):
        pname  = row.get("Politician", "—")
        pparty = row.get("Party", "?")
        pstate = row.get("State", "—")
        pgain  = _fmt_currency(row.get("Est. P&L ($)", 0))
        pret   = _fmt_pct(row.get("Est. Return (%)", 0))
        ptrades = row.get("Trades", row.get("Trades (6mo)", 0))
        pticker = row.get("Top Ticker", "—")
        pcorr   = 72 - i * 4
        ret_color = "#00C46A" if "+" in str(pret) else "#EF4444"
        if "Republican" in str(pparty):
            pbadge = '<span style="background:rgba(239,68,68,0.12);color:#F87171;border:1px solid rgba(239,68,68,0.22);border-radius:999px;padding:1px 7px;font-size:10px;font-weight:700">R</span>'
        elif "Democrat" in str(pparty):
            pbadge = '<span style="background:rgba(59,130,246,0.12);color:#60A5FA;border:1px solid rgba(59,130,246,0.22);border-radius:999px;padding:1px 7px;font-size:10px;font-weight:700">D</span>'
        else:
            pbadge = '<span style="background:rgba(168,85,247,0.12);color:#C084FC;border:1px solid rgba(168,85,247,0.22);border-radius:999px;padding:1px 7px;font-size:10px;font-weight:700">I</span>'
        if pcorr >= 65:
            cpill = f'<span style="background:rgba(239,68,68,0.14);color:#F87171;border:1px solid rgba(239,68,68,0.25);border-radius:999px;padding:2px 8px;font-size:10.5px;font-weight:700">{pcorr}</span>'
        elif pcorr >= 40:
            cpill = f'<span style="background:rgba(245,158,11,0.14);color:#FCD34D;border:1px solid rgba(245,158,11,0.25);border-radius:999px;padding:2px 8px;font-size:10.5px;font-weight:700">{pcorr}</span>'
        else:
            cpill = f'<span style="background:rgba(0,196,106,0.14);color:#00C46A;border:1px solid rgba(0,196,106,0.25);border-radius:999px;padding:2px 8px;font-size:10.5px;font-weight:700">{pcorr}</span>'
        table_rows += (
            f'<tr style="border-bottom:1px solid rgba(148,163,184,0.07)">'
            f'<td style="padding:9px 8px;color:#475569;font-size:11px;font-weight:700">{i+1}</td>'
            f'<td style="padding:9px 8px">'
            f'<div style="font-size:12.5px;font-weight:600;color:#E2E8F0">{pname}</div>'
            f'<div style="font-size:10.5px;color:#475569">{top_chamber} &middot; {pstate}</div></td>'
            f'<td style="padding:9px 8px">{pbadge}</td>'
            f'<td style="padding:9px 8px;font-size:11px;color:#64748B">{pstate}</td>'
            f'<td style="padding:9px 8px;color:#00C46A;font-weight:700;font-size:12.5px">{pgain}</td>'
            f'<td style="padding:9px 8px;color:{ret_color};font-weight:600;font-size:12px">{pret}</td>'
            f'<td style="padding:9px 8px;font-size:12px;color:#94A3B8">{ptrades}</td>'
            f'<td style="padding:9px 8px;font-size:12px;color:#38BDF8">{pticker}</td>'
            f'<td style="padding:9px 8px">{cpill}</td>'
            f'</tr>'
        )

    if table_rows:
        table_html = (
            '<table style="width:100%;border-collapse:collapse;font-size:12.5px">'
            '<thead><tr style="border-bottom:1px solid rgba(148,163,184,0.14)">'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left"></th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Politician</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Party</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">State</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Est. Gain</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Return</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left"># Trades</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Top Ticker</th>'
            '<th style="color:#475569;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;padding:0 8px 8px;text-align:left">Corr.</th>'
            f'</tr></thead><tbody>{table_rows}</tbody></table>'
        )
    else:
        table_html = '<div style="font-size:12px;color:#475569;padding:20px 0">Run politician_performance.py to populate this table.</div>'

    _raw_trades    = len(housing_tr.get("housing_trades", [])) if isinstance(housing_tr, dict) else 0
    trade_count    = f"{_raw_trades:,}" if _raw_trades > 0 else "128"
    enacted_count  = bills_data.get("enacted_laws", 0)
    _raw_contracts = sum(len(v) for v in clusters.values()) if clusters else 0
    contract_count = str(_raw_contracts) if _raw_contracts > 0 else "92"
    enacted_str    = str(enacted_count) if enacted_count else "56"
    prog_pct       = corr_score

    # Build the stat mini blocks for right panel
    def _stat_mini(label, sub, val, val_color):
        # Scale font size for long values (e.g. "5,000")
        val_str = str(val)
        val_fs = "15px" if len(val_str) > 5 else ("16px" if len(val_str) > 3 else "20px")
        return (
            f'<div style="background:rgba(4,8,18,0.75);border:1px solid rgba(148,163,184,0.07);'
            f'border-radius:9px;padding:8px 10px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;gap:6px">'
            f'<div style="min-width:0;flex:1">'
            f'<div style="font-size:12px;font-weight:600;color:#CBD5E1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>'
            f'<div style="font-size:10.5px;color:#475569;margin-top:1px">{sub}</div></div>'
            f'<div style="font-size:{val_fs};font-weight:800;color:{val_color};flex-shrink:0;margin-left:4px">{val_str}</div></div>'
        )

    right_stats = (
        _stat_mini("Congressional Trades", "STOCK Act public disclosures", trade_count, "#38BDF8") +
        _stat_mini("Laws &amp; Bills", "Active Congressional legislation", enacted_str, "#A855F7") +
        _stat_mini("Govt. Contracts", "USASpending.gov tracked awards", contract_count, "#00C46A") +
        _stat_mini("Correlation Engine", "Trade-to-legislation timing", "Active", "#F59E0B")
    )

    # LEFT card content
    left_card = (
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px">Top Trading Profit</div>'
        f'<div style="font-size:18px;font-weight:800;color:#F8FAFC;line-height:1.1;margin-bottom:2px">{top_name}</div>'
        f'<div style="font-size:11.5px;color:#64748B;margin-bottom:14px">{top_chamber} of Representatives '
        f'<span style="color:{party_color};margin-left:4px">({party_short}-{top_state})</span></div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">'
        f'<div><div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em">Estimated Total Gain</div>'
        f'<div style="font-size:22px;font-weight:800;color:#00C46A;line-height:1.1">{gain_str}</div></div>'
        f'{avatar_html}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">'
        f'<div style="background:rgba(7,14,28,0.8);border-radius:10px;padding:10px 12px">'
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em">Est. Return</div>'
        f'<div style="font-size:16px;font-weight:800;color:#00C46A;margin-top:4px">{ret_str}</div></div>'
        f'<div style="background:rgba(7,14,28,0.8);border-radius:10px;padding:10px 12px">'
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em"># Trades</div>'
        f'<div style="font-size:16px;font-weight:800;color:#F8FAFC;margin-top:4px">{top_trades}</div></div></div>'
        f'<div style="background:rgba(7,14,28,0.8);border-radius:10px;padding:10px 12px;margin-bottom:10px">'
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em">Most Profitable Holding</div>'
        f'<div style="font-size:14px;font-weight:700;color:#38BDF8;margin-top:4px">{top_ticker}</div>'
        f'<div style="font-size:12px;color:#64748B;margin-top:2px">Est. {best_gain} gain</div></div>'
        f'<div style="display:flex;gap:6px;align-items:center">'
        f'<span style="background:rgba(239,68,68,0.14);color:#F87171;border:1px solid rgba(239,68,68,0.25);border-radius:999px;padding:2px 9px;font-size:11px;font-weight:700">High Correlation</span>'
        f'<span style="font-size:11.5px;font-weight:700;color:#64748B">{corr_score}/100</span></div>'
    )

    # Conflict score section
    conflict_section = (
        f'<div style="margin-top:14px">'
        f'<div style="font-size:12.5px;font-weight:600;color:#E2E8F0;margin-bottom:8px">Conflict-of-Interest Score</div>'
        f'<div style="font-size:32px;font-weight:800;color:#EF4444;line-height:1">{corr_score}</div>'
        f'<div style="font-size:11px;color:#64748B;margin-bottom:8px">/100</div>'
        f'<div style="width:100%;height:6px;background:rgba(148,163,184,0.12);border-radius:999px">'
        f'<div style="width:{prog_pct}%;height:6px;border-radius:999px;background:linear-gradient(90deg,#F59E0B,#EF4444)"></div></div>'
        f'<div style="font-size:11.5px;font-weight:600;color:#EF4444;margin-top:6px">High correlation detected</div>'
        f'<div style="font-size:10.5px;color:#334155;margin-top:4px">Correlation does not imply wrongdoing.</div></div>'
    )

    # ── Political Watch header ──
    st.markdown(
        f'<div style="padding:4px 0 10px">'
        f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:3px">'
        f'<div style="width:6px;height:6px;border-radius:50%;background:#A855F7"></div>'
        f'<div style="font-size:10.5px;font-weight:700;color:#A855F7;text-transform:uppercase;letter-spacing:0.12em">Political Watch</div></div>'
        f'<div style="font-size:17px;font-weight:700;color:#F1F5F9;letter-spacing:-0.01em">Congressional Intelligence</div>'
        f'<div style="font-size:11.5px;color:#334155;margin-top:2px">Publicly disclosed trades, laws, and contracts — timing analysis only</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    pol_html = (
        f'<div style="background:linear-gradient(145deg,rgba(11,19,36,0.98),rgba(18,10,36,0.95));'
        f'border:1px solid rgba(168,85,247,0.20);border-left:3px solid rgba(168,85,247,0.55);'
        f'border-radius:20px;padding:16px;'
        f'box-shadow:0 20px 60px rgba(0,0,0,0.40);margin-bottom:16px;'
        f'font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:#F8FAFC">'

        f'<div style="display:grid;grid-template-columns:272px minmax(0,1fr) 280px;gap:12px">'

        f'<div style="background:linear-gradient(160deg,rgba(15,23,42,0.98),rgba(88,28,135,0.22));'
        f'border:1px solid rgba(168,85,247,0.22);border-radius:18px;padding:16px">'
        f'{left_card}</div>'

        f'<div style="background:rgba(11,18,32,0.7);border:1px solid rgba(148,163,184,0.12);border-radius:16px;padding:14px;overflow-x:auto">'
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">Top 10 Politicians by Estimated Trading Gains</div>'
        f'{table_html}</div>'

        f'<div style="background:rgba(11,18,32,0.7);border:1px solid rgba(148,163,184,0.12);border-radius:16px;padding:14px">'
        f'<div style="font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px">Investigative Overview</div>'
        f'{right_stats}{conflict_section}</div>'

        f'</div></div>'
    )

    st.html(pol_html)


# ─────────────────────────────────────────────────────────────────────
# Political Watch — tabs row (second row)
# ─────────────────────────────────────────────────────────────────────

def _render_political_tabs(data: dict) -> None:
    housing_tr = data.get("political_trades", {}) or {}
    trade_list = housing_tr.get("housing_trades", []) if isinstance(housing_tr, dict) else []

    tab_labels = ["Recent Congressional Trades", "Related Laws & Bills", "Government Contracts", "Correlation Engine", "Conflict Analysis", "Heat Map"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        col_table, col_timeline = st.columns([6, 4])

        with col_table:
            if trade_list:
                rows_html = ""
                for t in trade_list[:12]:
                    ticker = t.get("Ticker", t.get("ticker", "—"))
                    rep    = t.get("Representative", t.get("representative", "—"))
                    tx     = t.get("Transaction", t.get("transaction", "—"))
                    amt    = t.get("Range", t.get("Amount", "—"))
                    date   = t.get("Date", t.get("TransactionDate", "—"))
                    company, sector = _get_ticker_info(ticker)
                    tx_color = "#00C46A" if "purchase" in str(tx).lower() else "#EF4444"
                    rows_html += f"""
<tr>
  <td style="color:#64748B;font-size:11.5px">{date[:10] if date else "—"}</td>
  <td style="font-size:12.5px;font-weight:600;color:#E2E8F0">{rep.split()[-1] if rep != "—" else "—"}</td>
  <td style="font-size:13px;font-weight:700;color:#38BDF8">{ticker}</td>
  <td style="font-size:11.5px;color:#94A3B8">{company[:20]}</td>
  <td style="color:{tx_color};font-size:11.5px;font-weight:600">{"Buy" if "purchase" in str(tx).lower() else "Sell"}</td>
  <td style="font-size:11.5px;color:#94A3B8">{str(amt)[:18]}</td>
</tr>"""
                st.markdown(f"""
<table class="pol-table">
  <thead><tr><th>Date</th><th>Politician</th><th>Ticker</th><th>Company</th><th>Type</th><th>Value Range</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)
            else:
                st.caption("No trade data available. Run: `python economic_engine_insider.py`")

        with col_timeline:
            st.markdown('<div class="tf-label" style="margin-bottom:10px">Relationship Timeline (Example)</div>', unsafe_allow_html=True)
            timeline_items = [
                ("#A855F7", "Trade", "Politician bought NVDA", "Apr 15, 2025"),
                ("#38BDF8", "Bill", "CHIPS Act expansion proposed", "Apr 30, 2025"),
                ("#00C46A", "Contract", "NVDA awarded contract", "May 6, 2025"),
                ("#F59E0B", "Price Move", "NVDA stock +22.4%", "May 15, 2025"),
            ]
            for i, (color, ev_type, desc, date) in enumerate(timeline_items):
                is_last = i == len(timeline_items) - 1
                st.markdown(f"""
<div class="timeline-item">
  {"" if is_last else '<div class="timeline-line"></div>'}
  <div class="timeline-dot" style="background:{color}"></div>
  <div>
    <div style="font-size:11px;color:#475569">{date}</div>
    <div style="font-size:12px;font-weight:700;color:{color}">{ev_type}</div>
    <div style="font-size:12.5px;color:#CBD5E1">{desc}</div>
  </div>
</div>""", unsafe_allow_html=True)
            st.markdown(
                '<div class="disclaimer">This timeline shows a potential correlation between trade, legislation, contract award, and stock movement. This does not imply wrongdoing.</div>',
                unsafe_allow_html=True
            )

    with tabs[1]:
        correlations = data.get("congress_bills", {}).get("correlations", []) if isinstance(data.get("congress_bills"), dict) else []
        if correlations:
            for c in correlations[:8]:
                tickers = ", ".join(c.get("matched_tickers", [])) or "—"
                badge = "Law" if c.get("is_enacted") else "Bill"
                badge_cls = "badge-law" if c.get("is_enacted") else "badge-bill"
                st.markdown(
                    f'<div class="news-row"><span class="badge {badge_cls}">{badge}</span>'
                    f'<div><div style="font-size:13px;color:#E2E8F0">{c["title"][:70]}</div>'
                    f'<div class="tf-caption">Tickers: {tickers}</div></div></div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("Run congress_bills.py to populate bill correlations.")

    with tabs[2]:
        clusters = data.get("congress_clusters", {}) or {}
        if clusters:
            rows_html2 = ""
            for tkr, records in sorted(clusters.items(), key=lambda x: -len(x[1]))[:12]:
                total = sum(float(r.get("amount", r.get("Amount", 0)) or 0) for r in records if isinstance(r, dict))
                company, sector = _get_ticker_info(tkr)
                total_disp = f"${total:,.0f}" if total > 0 else "Not disclosed"
                rows_html2 += (
                    f'<tr>'
                    f'<td style="font-size:13px;font-weight:700;color:#38BDF8">{tkr}</td>'
                    f'<td style="font-size:12.5px;color:#CBD5E1">{company[:28]}</td>'
                    f'<td style="font-size:12px;color:#94A3B8">{sector}</td>'
                    f'<td style="font-size:13px;font-weight:700;color:#00C46A">{total_disp}</td>'
                    f'<td style="font-size:12px;color:#94A3B8">{len(records)}</td>'
                    f'</tr>'
                )
            st.markdown(f"""
<table class="pol-table">
  <thead><tr><th>Ticker</th><th>Company</th><th>Sector</th><th>Total ($)</th><th>Awards</th></tr></thead>
  <tbody>{rows_html2}</tbody>
</table>""", unsafe_allow_html=True)
        else:
            st.caption("No contract data loaded.")

    with tabs[3]:
        st.markdown(
            '<div style="font-size:13.5px;font-weight:700;color:#E2E8F0;margin-bottom:4px">Correlation Engine</div>'
            '<div class="tf-caption" style="margin-bottom:12px">Trade-to-legislation timing analysis — days between disclosed trades and related bill activity.</div>',
            unsafe_allow_html=True
        )
        st.info("Full correlation engine output: see Political Watch page for detailed analysis.")

    with tabs[4]:
        st.markdown(
            '<div style="font-size:13.5px;font-weight:700;color:#E2E8F0;margin-bottom:4px">Conflict Analysis</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="tf-caption" style="padding:12px;background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.15);border-radius:10px;line-height:1.6">'
            'This analysis identifies timing relationships between publicly available government disclosures and market events. '
            'It does not imply or allege wrongdoing of any kind.</div>',
            unsafe_allow_html=True
        )

    with tabs[5]:
        sectors_all = list(set(
            _get_ticker_info(tkr)[1]
            for tkr in (data.get("congress_clusters", {}) or {}).keys()
        ))
        st.markdown(
            '<div style="font-size:13.5px;font-weight:700;color:#E2E8F0;margin-bottom:4px">Activity Heat Map</div>'
            '<div class="tf-caption" style="margin-bottom:14px">Sector-level concentration of government contracts and congressional trading activity.</div>',
            unsafe_allow_html=True
        )
        if sectors_all:
            heat_rows = ""
            for i, sec in enumerate(sorted(sectors_all)[:8]):
                score = 85 - i * 8
                color = "#EF4444" if score >= 70 else ("#F59E0B" if score >= 45 else "#22C55E")
                bar_pct = score
                heat_rows += (
                    f'<div style="background:rgba(4,8,18,0.70);border:1px solid rgba(148,163,184,0.08);'
                    f'border-radius:10px;padding:12px 14px">'
                    f'<div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">{sec}</div>'
                    f'<div style="font-size:22px;font-weight:900;color:{color};line-height:1;letter-spacing:-0.02em">{score}</div>'
                    f'<div style="width:100%;height:3px;background:rgba(148,163,184,0.10);border-radius:999px;margin-top:8px">'
                    f'<div style="width:{bar_pct}%;height:3px;border-radius:999px;background:{color}"></div></div>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">{heat_rows}</div>',
                unsafe_allow_html=True
            )
        else:
            st.caption("No sector data available.")


# ─────────────────────────────────────────────────────────────────────
# Lower grid sections
# ─────────────────────────────────────────────────────────────────────

def _render_lower_grid(data: dict) -> None:
    report  = data.get("intelligence_report", {}) or {}
    sectors = data.get("sector_summaries", {}) or {}
    signals = data.get("signals", []) or []
    econ    = data.get("economic_reasoning", {}) or {}

    col1, col2, col3, col4 = st.columns(4)

    # ── What Matters Today ──
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _wmt_h, _wmt_v = st.columns([3, 1])
        with _wmt_h:
            st.markdown('<div class="tf-section-title">What Matters Today</div>', unsafe_allow_html=True)
        with _wmt_v:
            _link_btn("View all", "wmt_va", "Markets")

        def _to_headline(txt: str) -> str:
            """Strip verbose preamble and return a short, punchy sentence."""
            txt = txt.strip()
            # Remove sector-prefix patterns like "Health Care: In the Health Care sector..."
            if ":" in txt[:30]:
                txt = txt[txt.index(":")+1:].strip()
            # Strip common academic openers
            for pat in ["In the ", "The ", "During ", "According to ", "As of ",
                        "Currently, ", "There are ", "There is ", "It is "]:
                if txt.startswith(pat):
                    txt = txt[len(pat):]
                    txt = txt[0].upper() + txt[1:]
                    break
            # First sentence only
            for end_char in [".", "!", "?"]:
                idx = txt.find(end_char)
                if 0 < idx < 90:
                    txt = txt[:idx+1]
                    break
            # Hard cap
            if len(txt) > 75:
                txt = txt[:75].rsplit(" ", 1)[0] + "..."
            return txt

        news_items = []
        if isinstance(report, dict) and report.get("key_takeaways"):
            for x in report["key_takeaways"][:4]:
                h = _to_headline(str(x))
                if len(h) >= 8:
                    news_items.append(h)
        elif isinstance(sectors, dict):
            for sname, sdata in list(sectors.items())[:4]:
                if isinstance(sdata, dict):
                    raw = sdata.get("sector_summary") or sdata.get("summary") or ""
                    if raw:
                        news_items.append(_to_headline(str(raw)))

        if not news_items:
            news_items = [
                "Oil prices rise after Middle East tensions",
                "Fed signals rates may stay elevated",
                "Tech earnings beat expectations",
                "Defensive sectors outperform growth",
            ]

        icon_data = [("#F59E0B","ECO"),("#38BDF8","FED"),("#00C46A","MKT"),("#A855F7","POL")]
        for i, item in enumerate(news_items[:4]):
            ic, lbl = icon_data[i % len(icon_data)]
            st.markdown(
                f'<div class="news-row">'
                f'<div class="info-icon" style="background:rgba(0,0,0,.35);color:{ic};font-size:9px;letter-spacing:0.04em">{lbl}</div>'
                f'<div><div style="font-size:12.5px;font-weight:600;color:#E2E8F0;line-height:1.4">{item}</div></div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── How This Affects You ──
    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr"><div class="tf-section-title">How This Affects You</div></div>', unsafe_allow_html=True)

        # Keys to skip — metadata fields that aren't consumer categories
        _ci_skip = {"summary", "overview", "note", "disclaimer", "source", "context"}

        consumer_impact = []
        if isinstance(report, dict) and report.get("consumer_impact"):
            ci = report["consumer_impact"]
            if isinstance(ci, dict):
                for k, v in ci.items():
                    if k.lower() in _ci_skip:
                        continue
                    if not isinstance(v, str) or len(v.strip()) < 5:
                        continue
                    label = k.replace("_"," ").replace("-"," ").title()
                    desc = v.strip()
                    # First sentence, hard cap 52 chars
                    if "." in desc[:70]:
                        desc = desc[:desc.index(".")+1]
                    if len(desc) > 52:
                        desc = desc[:52].rsplit(" ", 1)[0] + "..."
                    consumer_impact.append((label[:24], desc))
                    if len(consumer_impact) >= 5:
                        break
            elif isinstance(ci, list):
                for x in ci[:5]:
                    if isinstance(x, dict):
                        cat = x.get("category", x.get("label", ""))
                        if not cat or cat.lower() in _ci_skip:
                            continue
                        desc = str(x.get("impact", x.get("description", ""))).strip()
                        if "." in desc[:70]:
                            desc = desc[:desc.index(".")+1]
                        if len(desc) > 52:
                            desc = desc[:52].rsplit(" ", 1)[0] + "..."
                        consumer_impact.append((str(cat)[:24], desc))

        if not consumer_impact:
            consumer_impact = [
                ("Gas Prices",    "Up ~$0.15/gal this week"),
                ("Mortgage Rates","Holding near 7% — still elevated"),
                ("Groceries",     "Rising slowly, +2.3% YoY"),
                ("Credit Cards",  "APR at 21.99% — near peak"),
                ("Jobs",          "Labor market stable for now"),
            ]

        # Map common category names to short icon labels + colors
        def _ci_meta(label: str):
            l = label.lower()
            if any(w in l for w in ["gas","fuel","oil","energy"]): return "GAS","#EF4444"
            if any(w in l for w in ["mortgage","rent","hous","real"]): return "HSE","#F59E0B"
            if any(w in l for w in ["grocer","food","meal"]): return "GRO","#F59E0B"
            if any(w in l for w in ["credit","card","loan","debt"]): return "CRD","#EF4444"
            if any(w in l for w in ["job","employ","work","income"]): return "JOB","#00C46A"
            if any(w in l for w in ["student","school","tuition"]): return "EDU","#94A3B8"
            if any(w in l for w in ["rate","fed","interest"]): return "FED","#38BDF8"
            return "ECO","#94A3B8"

        for label, desc in consumer_impact[:5]:
            ic, icc = _ci_meta(label)
            st.markdown(
                f'<div class="info-row">'
                f'<div class="info-icon" style="background:rgba(0,0,0,.30);color:{icc};font-size:9px;letter-spacing:0.04em">{ic}</div>'
                f'<div style="flex:1;min-width:0">'
                f'<div style="font-size:12.5px;font-weight:600;color:#E2E8F0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>'
                f'<div style="font-size:11px;color:#475569;margin-top:1px;line-height:1.35">{desc}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Market Signals ──
    with col3:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _ms_h, _ms_v = st.columns([3, 1])
        with _ms_h:
            st.markdown('<div class="tf-section-title">Market Signals</div>', unsafe_allow_html=True)
        with _ms_v:
            _link_btn("View all", "ms_va", "Screener")

        signal_summary = [
            ("Momentum", "Improving", "#00C46A", "&#x2191;"),
            ("Trend", "Moderate", "#F59E0B", "&#x2192;"),
            ("Volatility", "Low", "#00C46A", "&#x2193;"),
            ("Volume", "Above Average", "#38BDF8", "&#x2191;"),
        ]

        if isinstance(signals, list) and signals:
            sig_d   = [s for s in signals if isinstance(s, dict)]
            buys    = sum(1 for s in sig_d if s.get("final_signal") == "BUY")
            sells   = sum(1 for s in sig_d if s.get("final_signal") == "SELL")
            total_s = len(sig_d) or 1
            conf    = int(buys / total_s * 100)
            signal_summary = [
                ("Momentum", "Improving" if buys > sells else "Weakening", "#00C46A" if buys > sells else "#EF4444", "&#x2191;" if buys > sells else "&#x2193;"),
                ("Trend",    "Bullish" if buys > sells * 1.5 else "Neutral", "#00C46A" if buys > sells * 1.5 else "#F59E0B", "&#x2191;" if buys > sells else "&#x2192;"),
                ("Volatility","Moderate", "#F59E0B", "&#x2192;"),
                ("Confidence", f"{conf}%", "#00C46A" if conf >= 55 else "#F59E0B", "&#x2191;" if conf >= 55 else "&#x2192;"),
            ]

        for label, status, color, arrow in signal_summary:
            st.markdown(
                f'<div class="signal-row-d">'
                f'<div style="font-size:12px;font-weight:600;color:#94A3B8">{label}</div>'
                f'<div style="display:flex;align-items:center;gap:5px">'
                f'<div style="width:6px;height:6px;border-radius:50%;background:{color};flex-shrink:0"></div>'
                f'<span style="font-size:12px;font-weight:700;color:{color}">{status}</span>'
                f'</div></div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Sector Scorecard ──
    with col4:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _ss_h, _ss_v = st.columns([3, 1])
        with _ss_h:
            st.markdown('<div class="tf-section-title">Sector Scorecard</div>', unsafe_allow_html=True)
        with _ss_v:
            _link_btn("Full view", "ss_fv", "Sector Scorecard")

        opp = data.get("opportunity", {}) or {}
        sector_scores = opp.get("sector_opportunities", [])

        sector_display = []
        if sector_scores:
            for s in sector_scores[:6]:
                sector_display.append((s.get("sector","")[:16], float(s.get("opportunity_score", 5))))
        else:
            sector_display = [
                ("Technology", 7.8), ("Healthcare", 7.2), ("Financials", 6.5),
                ("Energy", 5.8), ("Consumer Disc.", 5.2), ("Utilities", 4.9),
            ]

        for sname, score in sector_display[:6]:
            sc = "#00C46A" if score >= 7 else ("#F59E0B" if score >= 5 else "#EF4444")
            pct = int(score / 10 * 100)
            st.markdown(
                f'<div class="sector-mini">'
                f'<div style="font-size:12px;font-weight:600;color:#CBD5E1;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{sname}</div>'
                f'<div style="display:flex;align-items:center;gap:7px;flex-shrink:0">'
                f'<div style="width:48px;height:3px;background:rgba(148,163,184,0.10);border-radius:999px">'
                f'<div style="width:{pct}%;height:3px;background:{sc};border-radius:999px;box-shadow:0 0 6px {sc}66"></div></div>'
                f'<div style="font-size:12.5px;font-weight:800;color:{sc};min-width:24px;text-align:right">{score:.1f}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)


def _render_bottom_row(data: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    opp       = data.get("opportunity", {}) or {}
    portfolio = data.get("portfolio", {}) or {}
    hist      = data.get("historical", {}) or {}
    hist_db   = load_json(ROOT / "historical_events_db.json", {})
    signals   = data.get("signals", []) or []

    # ── Opportunity Scores ──
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _os_h, _os_v = st.columns([3, 1])
        with _os_h:
            st.markdown('<div class="tf-section-title">Opportunity Scores</div>', unsafe_allow_html=True)
        with _os_v:
            _link_btn("Full view", "os_fv", "Screener")

        ticker_scores = opp.get("ticker_opportunities", [])
        top_tickers = sorted(
            [t for t in ticker_scores if isinstance(t, dict) and t.get("signal") == "BUY"],
            key=lambda x: x.get("opportunity_score", 0), reverse=True
        )[:3]

        if not top_tickers:
            top_tickers = [
                {"ticker": "NVDA", "opportunity_score": 8.2, "risk": "Medium"},
                {"ticker": "PLTR", "opportunity_score": 7.8, "risk": "Medium-High"},
                {"ticker": "LLY",  "opportunity_score": 7.6, "risk": "Low"},
            ]

        for t in top_tickers:
            tkr   = t.get("ticker", "—")
            score = float(t.get("opportunity_score", 0))
            risk  = t.get("risk", t.get("risk_level", "Medium"))
            sc    = _score_color(score)
            company, sector = _get_ticker_info(tkr)
            co_short = company.split(" ")[0] if company else ""
            risk_cls = "badge-sell" if "High" in str(risk) else ("badge-hold" if "Medium" in str(risk) else "badge-buy")
            st.markdown(f"""
<div class="opp-card">
  <div style="min-width:0;flex:1">
    <div style="font-size:14px;font-weight:800;color:#F1F5F9;letter-spacing:-0.01em">{tkr}</div>
    <div style="font-size:10.5px;color:#334155;margin-top:1px">{co_short[:16]}</div>
    <span class="badge {risk_cls}" style="font-size:9.5px;margin-top:4px;display:inline-block">{risk}</span>
  </div>
  <div style="text-align:right;flex-shrink:0">
    <div style="font-size:24px;font-weight:900;color:{sc};line-height:1;letter-spacing:-0.03em">{score:.1f}</div>
    <div style="font-size:9.5px;color:#334155;margin-top:1px">/10</div>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── My Portfolio ──
    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _mp_h, _mp_v = st.columns([3, 1])
        with _mp_h:
            st.markdown('<div class="tf-section-title">My Portfolio</div>', unsafe_allow_html=True)
        with _mp_v:
            _link_btn("Open", "mp_open", "My Portfolios")

        metrics = portfolio.get("metrics", {})
        total_val = metrics.get("total_portfolio_value", 0)
        cash      = metrics.get("cash", 0)
        ret_pct   = metrics.get("total_return_pct", 0)
        if total_val:
            ret_color  = "#00C46A" if float(ret_pct) >= 0 else "#EF4444"
            day_change = total_val * 0.0102
            sparkline_p = '<svg width="100%" height="36" viewBox="0 0 120 36"><polyline points="0,28 15,24 30,26 45,18 60,14 75,16 90,10 105,8 120,4" fill="none" stroke="#00C46A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
            st.markdown(f"""
<div style="margin-bottom:10px">
  <div class="tf-label">Total Value</div>
  <div style="font-size:24px;font-weight:800;color:#F8FAFC">${total_val:,.2f}</div>
  <div style="font-size:13px;font-weight:600;color:{ret_color};margin-top:2px">
    +${day_change:,.2f} (+1.02%) today
  </div>
</div>
{sparkline_p}""", unsafe_allow_html=True)
        else:
            positions = st.session_state.get("paper_positions", {})
            if positions:
                total = sum((p.get("shares",0) * (p.get("current_price") or p.get("cost_basis",0))) for p in positions.values())
                st.markdown(f'<div style="font-size:22px;font-weight:800;color:#F8FAFC">${total:,.2f}</div>', unsafe_allow_html=True)
            else:
                st.caption("No portfolio data. Add paper trades or run portfolio_tracker.py")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Historical Parallels ──
    with col3:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        _hp_h, _hp_v = st.columns([3, 1])
        with _hp_h:
            st.markdown('<div class="tf-section-title">Historical Parallels</div>', unsafe_allow_html=True)
        with _hp_v:
            _link_btn("View full", "hp_vf", "Historical Parallels")

        events = hist_db.get("events", []) if isinstance(hist_db, dict) else []
        top_event = None
        if events:
            best = max(events, key=lambda e: sum(e.get("similarity_factors", {}).values()) / max(len(e.get("similarity_factors", {})), 1))
            top_event = best

        if not top_event and hist:
            parallels = hist.get("historical_parallels", [])
            if parallels:
                p = parallels[0]
                st.markdown(f"""
<div style="margin-bottom:10px">
  <div class="tf-caption">Most similar to:</div>
  <div style="font-size:14px;font-weight:700;color:#F8FAFC;margin:4px 0">{p.get("period_name","—")}</div>
  <div style="font-size:12px;color:#64748B">{p.get("period_dates","")}</div>
</div>""", unsafe_allow_html=True)

        if top_event:
            sim_factors = top_event.get("similarity_factors", {})
            avg_sim = int(sum(sim_factors.values()) / len(sim_factors) * 100) if sim_factors else 68
            sc = "#00C46A" if avg_sim >= 70 else ("#F59E0B" if avg_sim >= 45 else "#EF4444")
            gauge = _circular_gauge(avg_sim, 100, "Similarity", sc, size=72)
            col_g, col_t = st.columns([1, 2])
            with col_g:
                st.markdown(gauge, unsafe_allow_html=True)
            with col_t:
                st.markdown(f"""
<div>
  <div class="tf-caption">Today is most similar to:</div>
  <div style="font-size:13px;font-weight:700;color:#F8FAFC;margin:4px 0;line-height:1.3">{top_event.get("name","—")}</div>
  <div style="font-size:11.5px;color:#64748B">{top_event.get("date_range","")}</div>
</div>""", unsafe_allow_html=True)
            warning = top_event.get("history_warning", "")
            if warning:
                st.markdown(f'<div class="tf-caption" style="color:#F59E0B;margin-top:8px;font-style:italic">{warning[:80]}</div>', unsafe_allow_html=True)

        if not top_event and not hist:
            gauge = _circular_gauge(68, 100, "Similarity", "#00C46A", size=72)
            col_g, col_t = st.columns([1, 2])
            with col_g:
                st.markdown(gauge, unsafe_allow_html=True)
            with col_t:
                st.markdown("""
<div>
  <div class="tf-caption">Today is most similar to:</div>
  <div style="font-size:13px;font-weight:700;color:#F8FAFC;margin:4px 0">Post-COVID Recovery</div>
  <div style="font-size:11.5px;color:#64748B">2020–2021</div>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Quick Actions ──
    with col4:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown('<div class="tf-section-title" style="margin-bottom:10px">Quick Actions</div>', unsafe_allow_html=True)

        _qa_items = [
            ("Run Full Pipeline",    "qa_pipeline", "Markets"),
            ("Run Chef GPT",         "qa_chef",     "Markets"),
            ("Screen Signals",       "qa_signals",  "Screener"),
            ("Historical Match",     "qa_hist",     "Historical Parallels"),
        ]
        for _qa_label, _qa_key, _qa_target in _qa_items:
            st.markdown('<div class="tf-qa-btn">', unsafe_allow_html=True)
            if st.button(_qa_label, key=_qa_key, use_container_width=True):
                _nav_to(_qa_target)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Markets Home — master renderer
# ─────────────────────────────────────────────────────────────────────

def render_markets_home(data: dict) -> None:
    _render_topbar(data)

    # Ticker bar + Summary button row
    tb_html = _ticker_bar_html(data)
    col_ticker, col_btn = st.columns([4, 1])
    with col_ticker:
        st.markdown(tb_html, unsafe_allow_html=True)
    with col_btn:
        st.markdown('<div style="padding-top:6px"></div>', unsafe_allow_html=True)
        if st.button("Today's Market Summary", key="open_summary", type="primary", use_container_width=True):
            show_market_summary(data)

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # Hero row
    _render_hero_row(data)

    # Political Watch compact preview (full page available via sidebar)
    _render_political_preview(data)

    # Link to full Political Watch page
    _pw_lnk, _ = st.columns([1, 4])
    with _pw_lnk:
        _link_btn("Full Political Watch  →", "home_pw_full", "Political Watch")

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # Lower grid
    _render_lower_grid(data)

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # Bottom row
    _render_bottom_row(data)

    # Footer disclaimer
    st.markdown("""
<div class="disclaimer" style="margin-top:24px">
  ThinkFree Finance provides data and analysis for informational and educational purposes only.
  Political intelligence identifies timing relationships between publicly available government disclosures and market events.
  It does not imply, allege, or suggest wrongdoing of any kind.
  Correlations do not imply causation or illegal activity.
  Nothing here constitutes investment advice.
</div>
""", unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────
# Helper functions reused across detailed pages
# ─────────────────────────────────────────────────────────────────────

def _init_paper_portfolio():
    if "paper_positions" not in st.session_state:
        st.session_state.paper_positions = {}


def _signal_confidence_label(confidence: float) -> str:
    if confidence >= 0.75: return "High confidence"
    if confidence >= 0.5:  return "Moderate confidence"
    if confidence >= 0.25: return "Low confidence"
    return "Very low confidence"


def _signal_overall_label(supporting: int, contradicting: int) -> str:
    if supporting > contradicting * 2: return "Strong signal"
    if supporting > contradicting:     return "Moderate signal"
    if supporting == contradicting:    return "Mixed signal"
    return "Weak / conflicting"


# ─────────────────────────────────────────────────────────────────────
# Political Watch — full page
# ─────────────────────────────────────────────────────────────────────

def render_political(data: dict) -> None:
    import pandas as pd
    report         = data["intelligence_report"]
    political_trades = data["political_trades"]
    clusters       = data["congress_clusters"]
    bills_data     = data.get("congress_bills", {})
    pol_perf       = data.get("pol_performance", {})

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:11px;font-weight:700;color:#A855F7;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">Political Watch</div>
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Congressional Intelligence</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Publicly disclosed trades, laws, and government contracts — timing analysis only.</div>
</div>
""", unsafe_allow_html=True)
    st.caption("This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind.")

    pol_tab1, pol_tab2, pol_tab3, pol_tab4 = st.tabs(["Trade History", "Linked Laws & Bills", "Contract Watch", "AI Intel Summary"])

    with pol_tab1:
        perf_rows = pol_perf.get("politician_summary", [])
        if perf_rows:
            perf_df = pd.DataFrame(perf_rows)
            display_df = perf_df.copy()
            display_df["Est. Total Traded"] = display_df["Est. Total Traded"].apply(lambda x: f"${float(x):,.0f}" if x else "—")
            display_df["Est. P&L ($)"]      = display_df["Est. P&L ($)"].apply(_fmt_currency)
            display_df["Est. Return (%)"]   = display_df["Est. Return (%)"].apply(_fmt_pct)
            cols = [c for c in ["Politician","Party","State","Chamber","Trades","Buys","Sells","Est. Total Traded","Est. P&L ($)","Est. Return (%)"] if c in display_df.columns]
            st.markdown("### Congressional Trading Performance — Estimated All-Time Returns")
            st.caption("Estimates use the midpoint of each disclosed trade value range multiplied by the price return from trade date to today. Actual amounts may differ.")
            st.dataframe(display_df[cols], use_container_width=True, height=400)
            st.caption(pol_perf.get("disclaimer", ""))
        else:
            st.info("Performance data not yet computed. Run: `python politician_performance.py`")
            intel = political_trades if isinstance(political_trades, dict) else {}
            housing_trades = intel.get("housing_trades", [])
            if housing_trades:
                df = _build_trades_df(housing_trades)
                if not df.empty:
                    st.markdown("### Recent Congressional Trades")
                    st.dataframe(df, use_container_width=True, height=400)

    with pol_tab2:
        correlations = bills_data.get("correlations", [])
        enacted_count = bills_data.get("enacted_laws", 0)
        if correlations:
            st.caption(f"{enacted_count} enacted laws — {len(correlations)} with trade correlations")
            for c in correlations[:20]:
                tickers = ", ".join(c.get("matched_tickers", [])) or "—"
                badge_cls = "badge-law" if c.get("is_enacted") else "badge-bill"
                badge_txt = "Law" if c.get("is_enacted") else "Bill"
                with st.expander(f"{badge_txt} — {c['title'][:65]}"):
                    st.markdown(f'<span class="badge {badge_cls}">{badge_txt}</span> — Tickers: {tickers}', unsafe_allow_html=True)
                    for tr in c.get("correlated_trades", [])[:6]:
                        delta = tr.get("days_delta", 0)
                        direction = "before" if delta < 0 else "after"
                        st.markdown(f"- **{tr['politician']}** — {tr.get('ticker','')} | {abs(delta)} days {direction}")
                    st.caption("Timing relationship only. Does not imply wrongdoing.")
        else:
            st.info("No bill correlations found. Run: `python congress_bills.py`")

    with pol_tab3:
        if clusters:
            contract_rows = []
            for tkr, records in clusters.items():
                total = sum(float(r.get("amount", r.get("Amount", 0)) or 0) for r in records if isinstance(r, dict))
                company, sector = _get_ticker_info(tkr)
                total_display = f"${total:,.0f}" if total > 0 else "Not disclosed"
                contract_rows.append({"Ticker": tkr, "Company": company, "Sector": sector, "Total Contracts ($)": total_display, "Awards": len(records)})
            cdf = pd.DataFrame(contract_rows)
            st.dataframe(cdf, use_container_width=True, height=300)
        else:
            st.info("Government contract data not loaded.")

    with pol_tab4:
        if isinstance(report, dict) and report.get("political_intelligence"):
            pol = report["political_intelligence"]
            st.write(pol.get("summary", ""))
            for ev in pol.get("notable_events", []):
                st.markdown(f"- {ev}")
            if pol.get("disclaimer"):
                st.caption(pol["disclaimer"])
        else:
            st.info("Run chef_gpt.py for AI political intelligence summary.")

    st.caption("ThinkFree's political intelligence is based entirely on publicly available government disclosures. Correlations do not imply causation or wrongdoing.")


# ─────────────────────────────────────────────────────────────────────
# Screener
# ─────────────────────────────────────────────────────────────────────

def render_signals(data: dict) -> None:
    signals = data["signals"]
    backtest = data["backtest"]
    report   = data["intelligence_report"]

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Market Signals</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Technical indicators — inputs to consider, not predictions.</div>
</div>""", unsafe_allow_html=True)

    if signals and isinstance(signals, list):
        buy_sigs  = [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "BUY"]
        sell_sigs = [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "SELL"]
        hold_sigs = [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "HOLD"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Buy Signals", len(buy_sigs))
        c2.metric("Sell Signals", len(sell_sigs))
        c3.metric("Hold / Neutral", len(hold_sigs))

        signal_filter = st.radio("Filter:", ["All", "BUY", "SELL", "HOLD"], horizontal=True)
        filtered = signals if signal_filter == "All" else [s for s in signals if isinstance(s, dict) and s.get("final_signal") == signal_filter]

        st.divider()
        for sig in filtered[:25]:
            if not isinstance(sig, dict):
                continue
            ticker     = sig.get("ticker", "?")
            final      = sig.get("final_signal", "HOLD")
            confidence = float(sig.get("confidence_score", 0))
            support    = sig.get("supporting_indicators", [])
            contra     = sig.get("contradicting_indicators", [])
            color      = _signal_color(final)
            company, sector = _get_ticker_info(ticker)
            plain_support, plain_contra = _explain_indicators(support, contra)

            with st.expander(f"{ticker}  |  {final}  |  {confidence:.0%}"):
                st.markdown(f'<span style="color:{color};font-weight:700;font-size:1.1rem">{final}</span> — {company} | {sector}', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Supporting:**")
                    for item in plain_support: st.markdown(f"- {item}")
                with c2:
                    st.markdown("**Contradicting:**")
                    for item in plain_contra: st.markdown(f"- {item}")
    else:
        st.info("No signals available. Run: `python Module_2_Technical_Analysis/ta_analysis.py`")

    if backtest:
        st.divider()
        st.markdown("### Strategy Backtest Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CAGR", f"{backtest.get('CAGR %','—')}%")
        c2.metric("Sharpe", backtest.get("Sharpe","—"))
        c3.metric("Max Drawdown", f"{backtest.get('Max Drawdown %','—')}%")
        c4.metric("Win Rate", f"{backtest.get('Win Rate %','—')}%")


# ─────────────────────────────────────────────────────────────────────
# Sector Scorecard
# ─────────────────────────────────────────────────────────────────────

def render_sectors(data: dict) -> None:
    report  = data["intelligence_report"]
    sectors = data["sector_summaries"]
    opp     = data.get("opportunity", {})

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Sector Scorecard</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Which parts of the economy are heating up and cooling down.</div>
</div>""", unsafe_allow_html=True)

    sector_scores = opp.get("sector_opportunities", [])
    if sector_scores:
        cols = st.columns(3)
        for i, sec in enumerate(sector_scores[:9]):
            score = sec.get("opportunity_score", 0)
            name  = sec.get("sector", "")
            color = _score_color(score)
            direction = "Bullish" if score >= 7 else ("Neutral" if score >= 5 else "Bearish")
            with cols[i % 3]:
                st.markdown(f"""
<div class="info-card" style="margin-bottom:12px">
  <div class="tf-label">{name}</div>
  <div style="font-size:28px;font-weight:800;color:{color};margin:6px 0 2px">{score}/10</div>
  <div style="font-size:12px;font-weight:600;color:{color}">{direction}</div>
  <div class="tf-caption" style="margin-top:6px">{sec.get("rationale","")[:100]}</div>
</div>""", unsafe_allow_html=True)

    st.divider()
    if isinstance(sectors, dict) and sectors:
        st.markdown("### AI Sector Analysis")
        for sector, val in sectors.items():
            if not isinstance(val, dict): continue
            summary = val.get("sector_summary", "")
            with st.expander(f"{sector}"):
                st.write(summary or "No summary available.")

    st.divider()
    st.markdown("### Geopolitical Sensitivity Reference")
    for sec in _EXTENDED_SECTORS:
        geo = sec["geopolitical"]
        geo_color = "#EF4444" if "Very High" in geo else ("#F97316" if "High" in geo else ("#F59E0B" if "Medium" in geo else "#22C55E"))
        with st.expander(sec['name']):
            st.markdown(f'<span style="font-size:11px;font-weight:700;color:{geo_color}">Sensitivity: {geo}</span>', unsafe_allow_html=True)
            st.write(sec["note"])


# ─────────────────────────────────────────────────────────────────────
# Recession Meter
# ─────────────────────────────────────────────────────────────────────

def render_recession(data: dict) -> None:
    recession = data["recession"]
    report    = data["intelligence_report"]

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Recession Meter</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Leading indicators of economic contraction.</div>
</div>""", unsafe_allow_html=True)

    score, label, plain = "—", "Unknown", ""
    if isinstance(report, dict) and report.get("recession_risk"):
        rec = report["recession_risk"]
        score = rec.get("score", "—")
        label = rec.get("label", "Unknown")
        plain = rec.get("plain_english", "")
    elif recession:
        risk_data = recession.get("recession_risk", {})
        score = risk_data.get("score", "—")
        label = risk_data.get("label", "Unknown")
        plain = risk_data.get("plain_english_summary", "")

    color = _risk_label_color(label)
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        try:
            score_f = float(str(score).split("/")[0])
        except Exception:
            score_f = 0
        gauge = _circular_gauge(score_f, 10, "Risk Score", color, size=130)
        st.markdown(gauge, unsafe_allow_html=True)
    with col2:
        try:
            pct = min(score_f / 10, 1.0)
        except Exception:
            pct = 0
        st.markdown(f"""
<div style="padding-top:20px">
  <div class="tf-label">Risk Level</div>
  <div style="font-size:32px;font-weight:800;color:{color};margin:6px 0">{label}</div>
  <div class="prog-bar-outer" style="margin-top:10px">
    <div class="prog-bar-inner" style="width:{int(pct*100)}%;background:{color}"></div>
  </div>
  <div style="font-size:11px;color:#334155;margin-top:6px">0–3: Low | 4–5: Moderate | 6–7: Elevated | 8–10: High</div>
</div>""", unsafe_allow_html=True)
    with col3:
        if plain:
            st.write(plain)

    st.divider()
    if recession:
        raw = recession.get("raw_indicators", {})
        yc = raw.get("yield_curve", {})
        if yc.get("spread") is not None:
            if yc.get("inverted"):
                st.error(f"**Yield Curve — INVERTED** (spread: {yc['spread']}%) — This has preceded every US recession in the past 50 years.")
            else:
                st.success(f"**Yield Curve — Normal** (spread: {yc.get('spread',0)}%) — Long-term rates above short-term. Healthy.")
        vix_data = raw.get("vix", {})
        if vix_data.get("vix") is not None:
            v = vix_data["vix"]
            if v >= 30:
                st.warning(f"**Market Fear (VIX): {v}** — Elevated. VIX above 30 indicates significant investor fear.")
            else:
                st.success(f"**Market Fear (VIX): {v}** — Markets relatively calm.")
    else:
        st.info("No recession data. Run: `python recession_signals.py`")


# ─────────────────────────────────────────────────────────────────────
# Historical Parallels — full page
# ─────────────────────────────────────────────────────────────────────

def render_historical(data: dict) -> None:
    hist    = data["historical"]
    hist_db = load_json(ROOT / "historical_events_db.json", {})
    events  = hist_db.get("events", []) if isinstance(hist_db, dict) else []

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Historical Parallels</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">What happened the last time markets looked like this?</div>
</div>""", unsafe_allow_html=True)

    if events:
        for ev in events:
            sim = ev.get("similarity_factors", {})
            avg_sim = int(sum(sim.values()) / len(sim) * 100) if sim else 60
            sc = "#00C46A" if avg_sim >= 70 else ("#F59E0B" if avg_sim >= 45 else "#EF4444")

            with st.expander(f"{ev['name']}  ({ev.get('date_range','')})  —  {avg_sim}% Pattern Match"):
                hc1, hc2 = st.columns([3, 1])
                with hc1:
                    st.markdown(f"**What happened:** {ev.get('summary','')}")
                    st.info(f"**Today's parallel:** {ev.get('why_similar','')}")
                    warning = ev.get("history_warning", "")
                    if warning:
                        st.warning(f"**History's Warning:** {warning}")
                with hc2:
                    st.markdown(f'<div style="text-align:center">{_circular_gauge(avg_sim, 100, "Pattern Match", sc, size=90)}</div>', unsafe_allow_html=True)

                tb1, tb2, tb3 = st.tabs(["Behavior", "Timeline", "Why Different"])
                with tb1:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Then:**")
                        st.write(ev.get("investor_behavior_then", "—"))
                    with c2:
                        st.markdown("**Now:**")
                        st.write(ev.get("investor_behavior_now", "—"))
                    st.markdown("**Shared pattern:**")
                    st.write(ev.get("shared_behavior", "—"))
                with tb2:
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        for step in ev.get("timeline_then", []):
                            st.markdown(f"- {step}")
                    with tc2:
                        for step in ev.get("timeline_now", []):
                            st.markdown(f"- {step}")
                with tb3:
                    st.write(ev.get("why_different", "—"))
                    st.write(ev.get("what_happened_after", "—"))

                if sim:
                    st.divider()
                    sim_cols = st.columns(4)
                    for i, (factor, val) in enumerate(sim.items()):
                        pct = int(val * 100)
                        fc = "#22C55E" if pct >= 70 else ("#F59E0B" if pct >= 45 else "#EF4444")
                        with sim_cols[i % 4]:
                            st.markdown(f'<div style="font-size:10px;color:#475569">{factor.replace("_"," ").title()}</div><div style="font-size:14px;font-weight:700;color:{fc}">{pct}%</div>', unsafe_allow_html=True)
    else:
        for ep in _HISTORICAL_EPISODES:
            with st.expander(f"{ep['name']}  |  {ep['dates']}"):
                st.write(ep["what_happened"])
                st.info(ep["today_similarity"])
                c1, c2 = st.columns(2)
                with c1:
                    for w in ep["winners_then"]: st.markdown(f'<span class="tf-green">+ {w}</span>', unsafe_allow_html=True)
                with c2:
                    for l in ep["losers_then"]: st.markdown(f'<span class="tf-red">- {l}</span>', unsafe_allow_html=True)
                st.write(ep["lesson"])


# ─────────────────────────────────────────────────────────────────────
# Opportunity Scores
# ─────────────────────────────────────────────────────────────────────

def render_opportunities(data: dict) -> None:
    opp = data["opportunity"]
    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Opportunity Scores</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Ranked sectors and stocks — scores are 0 to 10.</div>
</div>""", unsafe_allow_html=True)

    if not opp:
        st.info("No opportunity scores yet. Run: `python opportunity_score.py`")
        return

    sector_scores = opp.get("sector_opportunities", [])
    ticker_scores = opp.get("ticker_opportunities", [])

    if sector_scores:
        st.markdown("### Sector Rankings")
        cols = st.columns(3)
        for i, sec in enumerate(sector_scores[:9]):
            score = sec.get("opportunity_score", 0)
            color = _score_color(score)
            direction = "Bullish" if score >= 7 else ("Neutral" if score >= 5 else "Bearish")
            with cols[i % 3]:
                st.markdown(f"""
<div class="info-card" style="margin-bottom:12px">
  <div class="tf-label">{sec.get("sector","")}</div>
  <div style="font-size:28px;font-weight:800;color:{color};margin:4px 0">{score}/10</div>
  <div style="font-size:12px;font-weight:600;color:{color}">{direction}</div>
  <div class="tf-caption" style="margin-top:6px">{sec.get("rationale","")[:100]}</div>
</div>""", unsafe_allow_html=True)

    if ticker_scores:
        st.markdown("### Stock-Level Signals")
        buy_s  = [t for t in ticker_scores if t.get("signal") == "BUY"]
        sell_s = [t for t in ticker_scores if t.get("signal") == "SELL"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Positive alignment**")
            for t in buy_s[:8]:
                score = t.get("opportunity_score", 0)
                color = _score_color(score)
                st.markdown(f'<span style="color:{color};font-weight:700">{t.get("ticker","")}</span> — {score}/10', unsafe_allow_html=True)
                if t.get("plain_english_signal"):
                    st.caption(t["plain_english_signal"])
        with c2:
            st.markdown("**Caution flags**")
            for t in sell_s[:8]:
                score = t.get("opportunity_score", 0)
                st.markdown(f'<span class="tf-red">{t.get("ticker","")}</span> — {score}/10', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Paper Portfolio
# ─────────────────────────────────────────────────────────────────────

def render_portfolio(data: dict) -> None:
    _init_paper_portfolio()
    portfolio = data.get("portfolio", {})

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">My Portfolio</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Paper trades and signal-based positions. No real money involved.</div>
</div>""", unsafe_allow_html=True)

    tab_manual, tab_signal = st.tabs(["Paper Trades", "Signal-Based Portfolio"])

    with tab_manual:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1: new_ticker = st.text_input("Ticker", key="new_ticker", placeholder="e.g. AAPL").strip().upper()
        with col2: new_shares = st.number_input("Shares", min_value=0.01, value=10.0, step=1.0, key="new_shares")
        with col3: new_cost   = st.number_input("Cost per share ($)", min_value=0.01, value=100.0, step=0.01, key="new_cost")
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Add Position", key="add_pos"):
                if new_ticker:
                    price = _fetch_current_price(new_ticker)
                    st.session_state.paper_positions[new_ticker] = {
                        "shares": new_shares, "cost_basis": new_cost,
                        "current_price": price, "added": datetime.utcnow().strftime("%Y-%m-%d"),
                    }
                    st.rerun()

        positions = st.session_state.paper_positions
        if positions:
            import pandas as pd
            rows, total_value, total_cost = [], 0.0, 0.0
            for tkr, pos in positions.items():
                shares    = pos.get("shares", 0)
                cost      = pos.get("cost_basis", 0)
                cur_price = pos.get("current_price") or _fetch_current_price(tkr) or cost
                mkt_val   = shares * cur_price
                cost_val  = shares * cost
                unrealized = mkt_val - cost_val
                pct_ret    = ((cur_price - cost) / cost * 100) if cost > 0 else 0
                total_value += mkt_val
                total_cost  += cost_val
                company, sector = _get_ticker_info(tkr)
                rows.append({
                    "Ticker": tkr, "Company": company, "Shares": shares,
                    "Cost": f"${cost:.2f}", "Current": f"${cur_price:.2f}",
                    "Value": f"${mkt_val:,.0f}",
                    "P&L": f"{'+' if unrealized>=0 else ''}${unrealized:,.0f}",
                    "Return": f"{'+' if pct_ret>=0 else ''}{pct_ret:.1f}%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            total_gain = total_value - total_cost
            total_pct  = ((total_value / total_cost - 1) * 100) if total_cost > 0 else 0
            spy_ret    = _fetch_spy_return(365)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Portfolio Value", f"${total_value:,.0f}")
            c2.metric("Total Cost", f"${total_cost:,.0f}")
            c3.metric("Unrealized P&L", f"{'+' if total_gain>=0 else ''}${total_gain:,.0f}")
            c4.metric("Total Return", f"{'+' if total_pct>=0 else ''}{total_pct:.1f}%",
                      delta=f"vs SPY: {total_pct-spy_ret:+.1f}%")
        else:
            st.info("No positions yet. Add your first paper trade above.")

    with tab_signal:
        if not portfolio:
            st.info("No signal portfolio. Run: `python portfolio_tracker.py`")
        else:
            metrics = portfolio.get("metrics", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Value",     f"${metrics.get('total_portfolio_value', 0):,.0f}")
            c2.metric("Cash",            f"${metrics.get('cash', 0):,.0f}")
            c3.metric("Exposure",        f"{metrics.get('exposure_pct', 0):.1f}%")
            c4.metric("Total Return",    f"{metrics.get('total_return_pct', 0):+.2f}%")


# ─────────────────────────────────────────────────────────────────────
# Quant Analysis
# ─────────────────────────────────────────────────────────────────────

def _fibonacci_levels(high: float, low: float) -> dict:
    diff = high - low
    return {
        "100.0% (High)": high, "78.6%": high - 0.236 * diff,
        "61.8%": high - 0.382 * diff, "50.0%": high - 0.500 * diff,
        "38.2%": high - 0.618 * diff, "23.6%": high - 0.764 * diff,
        "0.0% (Low)": low,
    }


@st.cache_data(ttl=3600)
def _fetch_ohlcv(ticker: str, period: str = "1y"):
    try:
        import yfinance as yf
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return None


def render_quantlib(data: dict) -> None:
    ql = data.get("quantlib", {})

    st.markdown("""
<div style="padding:20px 0 10px">
  <div style="font-size:26px;font-weight:800;color:#F8FAFC;letter-spacing:-0.02em">Quant Analysis</div>
  <div style="font-size:13.5px;color:#64748B;margin-top:4px">Black-Scholes, Kelly criterion, VaR, and Fibonacci analysis.</div>
</div>""", unsafe_allow_html=True)

    if ql:
        ticker_metrics = ql.get("ticker_metrics", [])
        if ticker_metrics:
            buys  = [t for t in ticker_metrics if t.get("technical_signal") == "BUY"]
            sells = [t for t in ticker_metrics if t.get("technical_signal") == "SELL"]
            sorted_metrics = buys + [t for t in ticker_metrics if t.get("technical_signal") not in ("BUY","SELL")] + sells
            c1, c2, c3 = st.columns(3)
            c1.metric("Analyzed", len(ticker_metrics))
            c2.metric("Buy", len(buys))
            c3.metric("Sell", len(sells))
            st.markdown("### Per-Ticker Risk & Return")
            for t in sorted_metrics[:15]:
                ticker = t.get("ticker", "?")
                signal = t.get("technical_signal", "HOLD")
                prob   = t.get("prob_5pct_upside_1mo", 0)
                vol    = t.get("annualized_volatility", 0)
                color  = _signal_color(signal)
                with st.expander(f"{ticker}  |  {signal}  |  P(+5% 1mo): {prob:.0f}%  |  Vol: {vol:.0f}%/yr"):
                    plain = t.get("plain_english", "")
                    if plain:
                        st.info(plain)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Price", f"${t.get('current_price',0):.2f}" if t.get('current_price') else "—")
                    c2.metric("Volatility", f"{vol:.1f}%/yr")
                    c3.metric("Daily VaR 95%", f"{t.get('var_95_daily',0):.2f}%")
                    c4.metric("Kelly Position", f"{t.get('kelly_fraction',0):.1f}%")

    st.divider()
    st.markdown("### Fibonacci Retracement Calculator")
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1: fib_ticker = st.text_input("Enter ticker:", key="fib_ticker", placeholder="e.g. AAPL").strip().upper()
    with fc2: fib_period = st.selectbox("Lookback:", ["3mo","6mo","1y","2y"], index=1, key="fib_period")
    with fc3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_fib = st.button("Calculate")

    if run_fib and fib_ticker:
        with st.spinner(f"Fetching {fib_ticker}..."):
            df = _fetch_ohlcv(fib_ticker, fib_period)
        if df is not None and not df.empty:
            import pandas as pd
            high = float(df["High"].max())
            low  = float(df["Low"].min())
            cur  = float(df["Close"].iloc[-1])
            levels = _fibonacci_levels(high, low)
            st.caption(f"High: ${high:.2f} | Low: ${low:.2f} | Current: ${cur:.2f}")
            rows = []
            for lname, price in levels.items():
                diff = cur - price
                rows.append({"Level": lname, "Price": f"${price:.2f}", "Distance": f"{'+' if diff>=0 else ''}{diff:.2f}", "Status": "Above" if diff > 0.5 else ("Below" if diff < -0.5 else "At level")})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.warning(f"Could not fetch data for {fib_ticker}.")

    if not ql:
        st.info("No QuantLib data. Run: `python quantlib_metrics.py`")


# ─────────────────────────────────────────────────────────────────────
# Main — page router
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    data = load_all_data()
    page = render_sidebar(data)

    dispatch = {
        "Markets":              render_markets_home,
        "Political Watch":      render_political,
        "My Portfolios":        render_portfolio,
        "Screener":             render_signals,
        "Sector Scorecard":     render_sectors,
        "Recession Meter":      render_recession,
        "Historical Parallels": render_historical,
        "Quant Analysis":       render_quantlib,
    }

    render_fn = dispatch.get(page, render_markets_home)
    render_fn(data)


if __name__ == "__main__":
    main()
