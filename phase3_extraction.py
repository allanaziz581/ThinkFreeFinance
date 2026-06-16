#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 3: NLP Data Extraction & Structuring

Reads raw scraped articles and extracts machine-readable intelligence:
  - Percentages, dollar values, dates
  - Named companies and tickers
  - Economic indicators (CPI, GDP, unemployment, etc.)
  - Sentiment scores (VADER)
  - Comparison phrases ("beat expectations", "missed estimates")

Input:  news_output/articles_*.json  (most recent)
Output: news_output/enriched_news_sentiment.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
NEWS_DIR = BASE_DIR / "news_output"
OUTPUT_PATH = NEWS_DIR / "enriched_news_sentiment.json"

# ---------------------------------------------------------------------------
# Optional NLP imports — graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    print("[WARN] vaderSentiment not installed. Sentiment scoring will be skipped.")

try:
    import spacy
    try:
        NLP = spacy.load("en_core_web_sm")
        SPACY_AVAILABLE = True
    except OSError:
        NLP = None
        SPACY_AVAILABLE = False
        print("[WARN] spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
except ImportError:
    NLP = None
    SPACY_AVAILABLE = False
    print("[WARN] spaCy not installed. Named entity extraction will be limited.")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

PERCENT_RE   = re.compile(r"[-+]?\d+(?:\.\d+)?\s*%")
DOLLAR_RE    = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|trillion|B|M|T))?", re.IGNORECASE)
DATE_RE      = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|Q[1-4]\s+\d{4}"
    r"|FY\s*\d{4})\b",
    re.IGNORECASE
)

ECON_INDICATORS = {
    "cpi":          re.compile(r"\b(?:CPI|consumer price index)\b", re.I),
    "gdp":          re.compile(r"\bGDP\b|\bgross domestic product\b", re.I),
    "unemployment": re.compile(r"\bunemployment\b|\bjobless rate\b", re.I),
    "fed_rate":     re.compile(r"\bfederal funds rate\b|\bfed rate\b|\bFFR\b", re.I),
    "inflation":    re.compile(r"\binflation\b|\bprice level\b|\bPCE\b", re.I),
    "interest_rate":re.compile(r"\binterest rate[s]?\b|\brate hike\b|\brate cut\b", re.I),
    "recession":    re.compile(r"\brecession\b|\beconomic contraction\b", re.I),
    "earnings":     re.compile(r"\bearnings\b|\bEPS\b|\brevenue\b|\bprofit\b|\bloss\b", re.I),
    "tariff":       re.compile(r"\btariff[s]?\b|\bimport duty\b|\btrade war\b", re.I),
    "layoff":       re.compile(r"\blayoff[s]?\b|\bjob cut[s]?\b|\bdownsiz\w+\b|\brestructur\w+\b", re.I),
}

COMPARISON_PHRASES = [
    "beat expectations", "missed estimates", "exceeded forecasts", "fell short",
    "above consensus", "below consensus", "raised guidance", "lowered guidance",
    "better than expected", "worse than expected", "topped estimates",
    "cut outlook", "raised outlook", "record high", "record low",
    "all-time high", "all-time low", "year-over-year", "quarter-over-quarter",
]

COMPARISON_RE = re.compile(
    "|".join(re.escape(p) for p in COMPARISON_PHRASES), re.IGNORECASE
)

SENTIMENT_KEYWORDS = {
    "positive": [
        "surge", "soar", "rally", "gain", "rise", "jump", "beat", "record",
        "growth", "profit", "upgrade", "outperform", "bullish", "strong",
        "expansion", "accelerat", "robust", "exceed", "top",
    ],
    "negative": [
        "fall", "drop", "decline", "crash", "plunge", "miss", "loss", "cut",
        "downgrade", "underperform", "bearish", "weak", "contraction",
        "recession", "layoff", "default", "crisis", "concern", "risk", "warn",
    ],
}

# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_percentages(text: str) -> list[str]:
    return PERCENT_RE.findall(text)


def extract_dollar_values(text: str) -> list[str]:
    return DOLLAR_RE.findall(text)


def extract_dates(text: str) -> list[str]:
    return DATE_RE.findall(text)


def extract_economic_indicators(text: str) -> list[str]:
    found = []
    for name, pattern in ECON_INDICATORS.items():
        if pattern.search(text):
            found.append(name)
    return found


def extract_comparison_phrases(text: str) -> list[str]:
    return COMPARISON_RE.findall(text)


def extract_companies_spacy(text: str) -> list[str]:
    if not SPACY_AVAILABLE or NLP is None:
        return []
    doc = NLP(text[:5000])  # limit to avoid slow processing
    orgs = list({ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"})
    return orgs[:20]


def score_sentiment_vader(text: str) -> dict:
    if not VADER_AVAILABLE:
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
    analyzer = SentimentIntensityAnalyzer()
    return analyzer.polarity_scores(text)


def score_sentiment_keyword(text: str) -> dict:
    """Keyword-based fallback when VADER unavailable."""
    text_lower = text.lower()
    pos = sum(1 for w in SENTIMENT_KEYWORDS["positive"] if w in text_lower)
    neg = sum(1 for w in SENTIMENT_KEYWORDS["negative"] if w in text_lower)
    total = max(pos + neg, 1)
    compound = (pos - neg) / total
    return {
        "compound": round(compound, 4),
        "pos": round(pos / total, 4),
        "neg": round(neg / total, 4),
        "neu": round(1 - abs(compound), 4),
    }


def determine_sentiment_label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# Article loader
# ---------------------------------------------------------------------------

def find_latest_articles_file() -> Path | None:
    """Return the most recent articles JSON in news_output/."""
    files = sorted(
        NEWS_DIR.glob("articles_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def load_articles(path: Path) -> list[dict]:
    """Parse the articles file. Handles Finnhub nested, headline-keyed, and title-keyed formats."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    articles: list[dict] = []

    if isinstance(raw, list):
        for record in raw:
            if not isinstance(record, dict):
                continue
            # Finnhub format: {"symbol": ..., "finnhub": {"company_news": [...], ...}}
            if "finnhub" in record:
                symbol = record.get("symbol", "")
                finnhub = record["finnhub"]
                news_items = finnhub.get("company_news", [])
                if isinstance(news_items, list):
                    for item in news_items:
                        articles.append({
                            "title":     item.get("headline", ""),
                            "summary":   item.get("summary", ""),
                            "link":      item.get("url", ""),
                            "published": item.get("datetime", ""),
                            "source":    item.get("source", "finnhub"),
                            "ticker":    symbol,
                        })
            # headline-keyed format (summaries.json from Phase 2)
            elif "headline" in record:
                articles.append({
                    **record,
                    "title": record.get("headline", ""),
                })
            # Plain article format with title key
            elif "title" in record:
                articles.append(record)

    return articles


def load_articles_with_fallback() -> list[dict]:
    """Try articles_*.json first; fall back to summaries.json."""
    articles_file = find_latest_articles_file()
    if articles_file:
        result = load_articles(articles_file)
        if result:
            return result
    # Fallback to summaries.json
    fallback = NEWS_DIR / "summaries.json"
    if fallback.exists():
        print(f"[INFO] Falling back to {fallback.name}")
        return load_articles(fallback)
    return []


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------

def enrich_article(article: dict) -> dict:
    title   = str(article.get("title", ""))
    summary = str(article.get("summary", ""))
    full_text = f"{title}. {summary}"

    # Extract structured data
    percentages  = extract_percentages(full_text)
    dollar_vals  = extract_dollar_values(full_text)
    dates        = extract_dates(full_text)
    indicators   = extract_economic_indicators(full_text)
    comparisons  = extract_comparison_phrases(full_text)
    companies    = extract_companies_spacy(full_text)

    # Sentiment
    if VADER_AVAILABLE:
        sentiment = score_sentiment_vader(full_text)
    else:
        sentiment = score_sentiment_keyword(full_text)

    label = determine_sentiment_label(sentiment["compound"])

    # Data richness score (0–1): how much structured data was extracted
    richness_items = len(percentages) + len(dollar_vals) + len(dates) + len(indicators) * 2
    richness_score = min(1.0, richness_items / 10.0)

    return {
        **article,
        "extracted": {
            "percentages":   percentages,
            "dollar_values": dollar_vals,
            "dates":         dates,
            "economic_indicators": indicators,
            "comparison_phrases": comparisons,
            "companies_mentioned": companies,
        },
        "sentiment": {
            "compound": sentiment["compound"],
            "positive": sentiment.get("pos", 0.0),
            "negative": sentiment.get("neg", 0.0),
            "neutral":  sentiment.get("neu", 1.0),
            "label":    label,
        },
        "data_richness_score": round(richness_score, 3),
        "enriched_at": datetime.utcnow().isoformat() + "Z",
    }


def run_extraction() -> list[dict]:
    print("=== ThinkFree — Phase 3: NLP Extraction ===")

    raw_articles = load_articles_with_fallback()
    print(f"Loaded {len(raw_articles)} articles.")

    if not raw_articles:
        print("[WARN] No articles parsed. Check the articles file format.")
        return []

    enriched = []
    for i, article in enumerate(raw_articles):
        if i % 100 == 0:
            print(f"  Processing {i}/{len(raw_articles)}...")
        try:
            enriched.append(enrich_article(article))
        except Exception as e:
            print(f"  [WARN] Failed to enrich article {i}: {e}")

    # Sort by sentiment magnitude (most impactful first)
    enriched.sort(key=lambda a: abs(a["sentiment"]["compound"]), reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    positive = sum(1 for a in enriched if a["sentiment"]["label"] == "positive")
    negative = sum(1 for a in enriched if a["sentiment"]["label"] == "negative")
    neutral  = sum(1 for a in enriched if a["sentiment"]["label"] == "neutral")

    print(f"\nExtraction complete:")
    print(f"  Total articles: {len(enriched)}")
    print(f"  Positive: {positive}  Negative: {negative}  Neutral: {neutral}")
    print(f"  spaCy NER: {'enabled' if SPACY_AVAILABLE else 'disabled'}")
    print(f"  VADER sentiment: {'enabled' if VADER_AVAILABLE else 'keyword fallback'}")
    print(f"\nSaved to: {OUTPUT_PATH}")

    return enriched


if __name__ == "__main__":
    run_extraction()
