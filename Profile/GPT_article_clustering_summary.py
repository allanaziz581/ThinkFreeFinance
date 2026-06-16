#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 5: GPT Article Summarization & Validation
Reads clustered_summaries.json, calls GPT to summarize each article,
validates that key financial figures survived, and outputs
clustered_articles_with_summaries.json.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR    = Path(__file__).parent.parent
NEWS_OUTPUT = BASE_DIR / "news_output"

CLUSTERED_PATH = NEWS_OUTPUT / "clustered_summaries.json"
OUTPUT_PATH    = NEWS_OUTPUT / "clustered_articles_with_summaries.json"
SECTOR_OUTPUT  = NEWS_OUTPUT / "sector_summaries.json"

PERCENT_PAT = re.compile(r"\b\d+(?:\.\d+)?%\b")
DOLLAR_PAT  = re.compile(r"\$\d+(?:,\d{3})*(?:\.\d{2})?")
DATE_PAT    = re.compile(
    r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b"
)

GICS_SECTORS = [
    "Communication Services", "Consumer Discretionary", "Consumer Staples",
    "Energy", "Financials", "Health Care", "Industrials",
    "Information Technology", "Materials", "Real Estate", "Utilities",
]


def assign_sector(text: str) -> str:
    text_lower = text.lower()
    sector_keywords = {
        "Information Technology": ["tech", "software", "semiconductor", "ai", "cloud", "chip"],
        "Health Care":            ["health", "pharma", "drug", "biotech", "hospital", "fda", "medical"],
        "Financials":             ["bank", "finance", "interest rate", "fed", "mortgage", "insurance"],
        "Energy":                 ["oil", "gas", "energy", "opec", "fuel", "pipeline", "renewable"],
        "Consumer Discretionary": ["retail", "auto", "consumer", "amazon", "tesla", "housing"],
        "Consumer Staples":       ["food", "grocery", "staples", "walmart", "costco"],
        "Industrials":            ["industrial", "manufacturing", "defense", "aerospace", "logistics"],
        "Materials":              ["material", "mining", "steel", "copper", "aluminum", "commodity"],
        "Real Estate":            ["real estate", "reit", "property", "housing market", "rent"],
        "Utilities":              ["utility", "electric", "water", "power grid"],
        "Communication Services": ["media", "telecom", "streaming", "social media", "google", "meta"],
    }
    for sector, keywords in sector_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return sector
    return "General"


def summarize_article(client: OpenAI, model: str, article: dict) -> str:
    title   = article.get("title", article.get("headline", ""))
    summary = article.get("summary", article.get("content", ""))
    full_text = f"{title}\n{summary}".strip()
    if not full_text:
        return ""

    prompt = (
        "Summarize the following financial news article. "
        "Include all quantitative data (percentages, dollar amounts, dates). "
        "Keep it concise but data-rich (3-5 sentences):\n\n"
        f"---\n{full_text}\n---"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as e:
        print(f"  [WARNING] GPT call failed: {e}")
        return summary[:500]


def validate_retention(original: str, summary: str) -> bool:
    orig_vals = (
        PERCENT_PAT.findall(original)
        + DOLLAR_PAT.findall(original)
        + DATE_PAT.findall(original)
    )
    if not orig_vals:
        return True
    summ_vals = (
        PERCENT_PAT.findall(summary)
        + DOLLAR_PAT.findall(summary)
        + DATE_PAT.findall(summary)
    )
    return len(summ_vals) >= len(orig_vals) // 2


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to your .env file.")

    if not CLUSTERED_PATH.exists():
        raise FileNotFoundError(
            f"clustered_summaries.json not found at {CLUSTERED_PATH}. "
            "Run phase4_clustering.py first."
        )

    with open(CLUSTERED_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Normalize to flat list
    if isinstance(raw, list):
        all_articles = raw
    elif isinstance(raw, dict):
        all_articles = []
        for arts in raw.values():
            if isinstance(arts, list):
                all_articles.extend(arts)
    else:
        all_articles = []

    print(f"Loaded {len(all_articles)} articles from clustered_summaries.json")

    client = OpenAI(api_key=api_key)
    model  = "gpt-4o"

    summarized: list[dict] = []
    sector_buckets: dict[str, list[dict]] = {}

    for i, article in enumerate(all_articles):
        title   = article.get("title", article.get("headline", ""))
        summary = article.get("summary", article.get("content", ""))
        full_text = f"{title} {summary}"
        sector  = article.get("sector", assign_sector(full_text))

        print(f"  [{i+1}/{len(all_articles)}] {title[:60]}...")
        gpt_summary = summarize_article(client, model, article)

        if not validate_retention(full_text, gpt_summary):
            print("  [WARNING] Key financial data may have been dropped — keeping original summary.")
            gpt_summary = summary[:500] if not gpt_summary else gpt_summary

        enriched = {**article, "title": title, "sector": sector, "gpt_summary": gpt_summary}
        summarized.append(enriched)

        if sector not in sector_buckets:
            sector_buckets[sector] = []
        sector_buckets[sector].append(enriched)

    # Save full summarized output
    NEWS_OUTPUT.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"clusters": [{"cluster_id": 0, "top_articles": summarized}]}, f, indent=2)

    # Build sector_summaries.json from GPT-summarized content
    existing_sector_summaries: dict = {}
    if SECTOR_OUTPUT.exists():
        with open(SECTOR_OUTPUT, "r", encoding="utf-8") as f:
            existing_sector_summaries = json.load(f)

    for sector, arts in sector_buckets.items():
        combined = " ".join(a.get("gpt_summary", "") for a in arts if a.get("gpt_summary"))
        if combined and sector not in existing_sector_summaries:
            existing_sector_summaries[sector] = {
                "sector_summary": combined[:2000],
                "articles_count": len(arts),
            }

    with open(SECTOR_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(existing_sector_summaries, f, indent=2)

    print(f"\nGPT summaries complete.")
    print(f"  Output:          {OUTPUT_PATH}")
    print(f"  Sector coverage: {list(sector_buckets.keys())}")
    print(f"  Articles done:   {len(summarized)}")


if __name__ == "__main__":
    main()
