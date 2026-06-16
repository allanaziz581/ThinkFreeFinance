#!/usr/bin/env python3
import os
import sys
import feedparser
import hashlib
import json
import requests
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import concurrent.futures
import re
from difflib import get_close_matches
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

SEC_API_KEY     = os.getenv("SEC_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

if not FINNHUB_API_KEY:
    print("[WARN] FINNHUB_API_KEY not set — Finnhub data will be skipped. Add it to .env")
headers         = {"Authorization": f"Bearer {SEC_API_KEY}"}
finnhub_headers = {"X-Finnhub-Token": FINNHUB_API_KEY}
finnhub_base    = "https://finnhub.io/api/v1"

# Rate limiting setup
RATE_LIMIT_DELAY = 1.1  # seconds between requests
rate_lock = Lock()

def rate_limited_request(*args, **kwargs):
    with rate_lock:
        time.sleep(RATE_LIMIT_DELAY)
        return requests.get(*args, **kwargs)

# Setup output directory and seen-hashes file
script_dir       = os.path.dirname(os.path.abspath(__file__))
project_root     = os.path.abspath(os.path.join(script_dir, os.pardir))
output_dir       = os.path.join(project_root, "news_output")
os.makedirs(output_dir, exist_ok=True)
SEEN_HASHES_FILE = os.path.join(script_dir, "seen_hashes.json")

seen_hashes = set()
if os.path.exists(SEEN_HASHES_FILE):
    with open(SEEN_HASHES_FILE, "r") as f:
        seen_hashes = set(json.load(f))

# Helper: generate a stable hash for an article
def hash_article(title, link):
    return hashlib.sha256((title + link).encode("utf-8")).hexdigest()

# Load S&P 500 tickers & name→symbol map (filtered)
sp500_path   = os.path.join(script_dir, "sp500_tickers.json")
company_path = os.path.join(script_dir, "company_tickers.json")

with open(sp500_path, "r") as f:
    sp500_tickers = set(json.load(f))
print(f"Loaded {len(sp500_tickers)} S&P tickers")

sp500_names = {}
with open(company_path, "r") as f:
    raw = json.load(f)
for entry in raw.values():
    sym = entry.get("ticker", "").upper().strip()
    if sym in sp500_tickers:
        title = entry.get("title", "").strip().lower()
        if title:
            sp500_names[title] = sym
print(f"Loaded {len(sp500_names)} name mappings")

# Build symbol map from S&P 500 tickers and names
symbol_map = {s: s for s in sp500_tickers}
for name, sym in sp500_names.items():
    symbol_map[name] = sym

# Extract tickers from RSS

def extract_tickers_from_text(text):
    tickers = set()
    words = re.findall(r'\b[A-Z]{1,5}\b', text.upper())
    for word in words:
        if word in sp500_tickers:
            tickers.add(word)

    # Fuzzy match full company names
    for word in re.findall(r'\b\w+\b', text.lower()):
        match = get_close_matches(word, sp500_names.keys(), n=1, cutoff=0.9)
        if match:
            tickers.add(sp500_names[match[0]])
    return tickers

# Fallback if no tickers are extracted
def fallback_tickers(min_count=5):
    return list(sp500_tickers)[:min_count]

# Fetch data from Finnhub

def fetch_finnhub_data(symbol):
    endpoints = {
        "company_news": f"/company-news?symbol={symbol}&from={(datetime.now()-timedelta(days=7)).date()}&to={datetime.now().date()}",
        "quote": f"/quote?symbol={symbol}",
        "earnings": f"/stock/earnings?symbol={symbol}",
        "metric": f"/stock/metric?symbol={symbol}&metric=all",
    }
    results = {}
    for name, endpoint in endpoints.items():
        url = f"{finnhub_base}{endpoint}"
        try:
            resp = rate_limited_request(url, headers=finnhub_headers, timeout=10)
            resp.raise_for_status()
            results[name] = resp.json()
        except Exception as e:
            print(f"Error fetching {name} for {symbol}: {e}")
    return results

# RSS scraping
RSS_FEEDS = [
    # Yahoo & Google
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=aapl,msft,goog,meta,tsla&region=US&lang=en-US",
    "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
    # CNBC
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    # MarketWatch
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
]

articles = []
for url in RSS_FEEDS:
    feed = feedparser.parse(url)
    for entry in feed.entries:
        article_hash = hash_article(entry.title, entry.link)
        if article_hash not in seen_hashes:
            seen_hashes.add(article_hash)
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published": entry.get("published", "")
            })

# Process articles and extract tickers
extracted_tickers = set()
for article in articles:
    title = article.get("title", "")
    summary = article.get("summary", "")
    tickers = extract_tickers_from_text(title + " " + summary)
    extracted_tickers.update(tickers)

# Optional: override to extract full S&P 500 tickers
if os.getenv("FORCE_ALL_TICKERS") == "1":
    print("Force mode: Scraping all S&P 500 tickers")
    extracted_tickers = sp500_tickers
elif len(extracted_tickers) < 5:
    print("Fallback to default tickers.")
    extracted_tickers.update(fallback_tickers())

print(f"Extracted tickers: {sorted(extracted_tickers)}")

# Compile all data
compiled_data = []
for ticker in sorted(extracted_tickers):
    finnhub_data = fetch_finnhub_data(ticker)
    record = {"symbol": ticker, "finnhub": finnhub_data}
    compiled_data.append(record)

# Save results to timestamped JSON
output_file = os.path.join(
    output_dir,
    f"articles_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(compiled_data, f, indent=2)
print(f"Scraping complete. Wrote {len(compiled_data)} records to {output_file}")
