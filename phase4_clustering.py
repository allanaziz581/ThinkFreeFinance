#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 4: Article Scoring & Clustering

Takes enriched articles from Phase 3 and:
  1. Generates sentence embeddings
  2. Clusters similar articles (removes information overload)
  3. Assigns GICS sector labels to each cluster
  4. Scores each article by impact (|sentiment| × credibility × keyword_weight × profile_match)
  5. Selects the top 1-2 representative articles per cluster
  6. Outputs clustered_summaries.json for downstream GPT summarization

Input:  news_output/enriched_news_sentiment.json
        user_profile.json (for profile_match scoring)
Output: news_output/clustered_summaries.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
NEWS_DIR  = BASE_DIR / "news_output"
INPUT_PATH  = NEWS_DIR / "enriched_news_sentiment.json"
OUTPUT_PATH = NEWS_DIR / "clustered_summaries.json"

# ---------------------------------------------------------------------------
# Optional ML imports — graceful degradation
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("[WARN] sentence-transformers not installed. Clustering will use keyword fallback.")

try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARN] scikit-learn not installed. Will use simple deduplication instead.")

# ---------------------------------------------------------------------------
# GICS sector classification
# ---------------------------------------------------------------------------

GICS_SECTORS = {
    "Information Technology": [
        "ai", "artificial intelligence", "semiconductor", "chip", "cloud", "software",
        "tech", "technology", "nvidia", "apple", "microsoft", "google", "meta",
        "algorithm", "data center", "cybersecurity", "robot", "autonomous",
    ],
    "Health Care": [
        "pharma", "drug", "fda", "clinical trial", "biotech", "hospital", "health",
        "medical", "vaccine", "treatment", "cancer", "diabetes", "pfizer", "moderna",
        "johnson", "abbvie", "merck", "eli lilly",
    ],
    "Financials": [
        "bank", "fed", "federal reserve", "interest rate", "mortgage", "credit",
        "insurance", "wall street", "jpmorgan", "goldman", "blackrock", "fintech",
        "loan", "debt", "bond", "yield", "inflation", "monetary policy",
    ],
    "Energy": [
        "oil", "gas", "petroleum", "opec", "energy", "renewable", "solar", "wind",
        "exxon", "chevron", "bp", "shell", "natural gas", "pipeline", "crude",
    ],
    "Consumer Discretionary": [
        "retail", "consumer", "amazon", "tesla", "auto", "car", "restaurant",
        "entertainment", "travel", "hotel", "airline", "luxury", "spending",
    ],
    "Consumer Staples": [
        "food", "beverage", "grocery", "walmart", "costco", "procter", "colgate",
        "household", "staple", "necessit",
    ],
    "Industrials": [
        "manufacturing", "industrial", "aerospace", "defense", "caterpillar",
        "boeing", "construction", "logistics", "transport", "supply chain",
    ],
    "Materials": [
        "mining", "steel", "aluminum", "copper", "gold", "silver", "chemical",
        "material", "commodity", "rare earth", "lithium",
    ],
    "Real Estate": [
        "real estate", "reit", "housing", "property", "mortgage rate", "home price",
        "commercial real estate", "residential",
    ],
    "Utilities": [
        "utility", "electric", "water", "power grid", "dominion", "duke energy",
        "nuclear", "natural gas utility",
    ],
    "Communication Services": [
        "media", "telecom", "streaming", "netflix", "disney", "comcast",
        "advertising", "social media", "broadband", "5g", "verizon", "at&t",
    ],
}

CREDIBILITY_SCORES: dict[str, float] = {
    "reuters": 0.95,
    "bloomberg": 0.95,
    "wsj": 0.90,
    "wall street journal": 0.90,
    "ft": 0.90,
    "financial times": 0.90,
    "cnbc": 0.85,
    "marketwatch": 0.80,
    "yahoo": 0.70,
    "seekingalpha": 0.65,
    "finnhub": 0.75,
    "default": 0.60,
}

HIGH_IMPACT_KEYWORDS = [
    "earnings", "revenue", "profit", "loss", "guidance", "forecast",
    "fed", "rate", "inflation", "gdp", "unemployment", "recession",
    "acquisition", "merger", "buyout", "ipo", "bankruptcy",
    "record", "all-time", "historic", "massive", "surge", "crash",
    "tariff", "sanction", "executive order", "regulation",
    "layoff", "job cut", "hiring", "expansion",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assign_sector(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for sector, keywords in GICS_SECTORS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[sector] = score
    if not scores:
        return "General Market"
    return max(scores, key=lambda s: scores[s])


def get_credibility(source: str) -> float:
    src = str(source).lower()
    for key, score in CREDIBILITY_SCORES.items():
        if key in src:
            return score
    return CREDIBILITY_SCORES["default"]


def keyword_weight(text: str) -> float:
    text_lower = text.lower()
    hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in text_lower)
    return min(1.0, hits / 5.0)


def profile_match_score(article: dict, profile: dict) -> float:
    """Score how well an article matches the user's investment profile."""
    if not profile:
        return 0.5

    risk_tolerance = profile.get("risk_tolerance", "moderate")
    goal = profile.get("investment_goal", "growth")

    text = (article.get("title", "") + " " + article.get("summary", "")).lower()
    score = 0.5

    if risk_tolerance == "high":
        if any(w in text for w in ["growth", "momentum", "tech", "ai", "innovation"]):
            score += 0.3
        if any(w in text for w in ["volatile", "speculative", "high-risk"]):
            score += 0.2
    elif risk_tolerance == "low":
        if any(w in text for w in ["dividend", "stable", "utility", "bond", "defensive"]):
            score += 0.3
        if any(w in text for w in ["recession", "safe haven", "gold", "treasury"]):
            score += 0.2
    else:  # moderate
        score = 0.5

    if goal == "income":
        if any(w in text for w in ["dividend", "yield", "income", "payout"]):
            score += 0.2
    elif goal == "growth":
        if any(w in text for w in ["growth", "expansion", "revenue growth", "market share"]):
            score += 0.2

    return min(1.0, score)


def compute_impact_score(article: dict, profile: dict) -> float:
    """
    impact = |sentiment| × credibility × keyword_weight × profile_match
    Range: 0.0 – 1.0
    """
    sentiment = abs(article.get("sentiment", {}).get("compound", 0.0))
    credibility = get_credibility(article.get("source", ""))
    kw = keyword_weight(article.get("title", "") + " " + article.get("summary", ""))
    pm = profile_match_score(article, profile)
    richness = article.get("data_richness_score", 0.5)

    impact = sentiment * credibility * (kw * 0.4 + pm * 0.3 + richness * 0.3)
    return round(min(1.0, impact), 4)


# ---------------------------------------------------------------------------
# Embedding + clustering
# ---------------------------------------------------------------------------

def embed_articles(articles: list[dict]) -> np.ndarray | None:
    if not EMBEDDINGS_AVAILABLE:
        return None

    texts = [
        (a.get("title", "") + " " + a.get("summary", ""))[:512]
        for a in articles
    ]
    print(f"  Generating embeddings for {len(texts)} articles...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.astype("float32")


def cluster_with_embeddings(articles: list[dict], embeddings: np.ndarray) -> dict[int, list[int]]:
    n = len(articles)
    n_clusters = max(5, min(n // 10, 50))  # 5–50 clusters

    print(f"  Clustering into {n_clusters} groups...")
    model = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric="cosine",
        linkage="average",
    )
    labels = model.fit_predict(embeddings)

    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(idx)
    return clusters


def cluster_by_sector(articles: list[dict]) -> dict[int, list[int]]:
    """Fallback: group by sector when ML clustering unavailable."""
    sector_groups: dict[str, list[int]] = {}
    for idx, article in enumerate(articles):
        sector = article.get("gics_sector", "General Market")
        sector_groups.setdefault(sector, []).append(idx)

    # Convert to integer-keyed dict
    return {i: idxs for i, (_, idxs) in enumerate(sector_groups.items())}


def deduplicate_within_cluster(cluster_articles: list[dict]) -> list[dict]:
    """Remove near-duplicate articles based on title similarity."""
    seen_titles: set[str] = set()
    unique = []
    for art in cluster_articles:
        # Normalize title: lowercase, remove punctuation
        normalized = re.sub(r"[^a-z0-9 ]", "", art.get("title", "").lower())
        words = frozenset(normalized.split())
        # Check overlap with seen titles
        is_dupe = False
        for seen in seen_titles:
            seen_words = frozenset(seen.split())
            if len(words) > 0 and len(words & seen_words) / max(len(words), len(seen_words)) > 0.7:
                is_dupe = True
                break
        if not is_dupe:
            unique.append(art)
            seen_titles.add(normalized)
    return unique


import re as _re_module


def re_sub_helper(pattern: str, repl: str, text: str) -> str:
    return _re_module.sub(pattern, repl, text)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_clustering() -> dict:
    print("=== ThinkFree — Phase 4: Article Clustering ===")

    if not INPUT_PATH.exists():
        print(f"[ERROR] {INPUT_PATH} not found. Run phase3_extraction.py first.")
        return {}

    print(f"Loading enriched articles from {INPUT_PATH.name}...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        articles: list[dict] = json.load(f)
    print(f"Loaded {len(articles)} enriched articles.")

    if not articles:
        print("[WARN] No articles to cluster.")
        return {}

    # Load user profile for impact scoring
    profile_path = BASE_DIR / "user_profile.json"
    profile = {}
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        print(f"Loaded user profile: {profile.get('profile_id', 'unknown')}")

    # Assign sector labels and impact scores
    print("Assigning sectors and computing impact scores...")
    for article in articles:
        text = article.get("title", "") + " " + article.get("summary", "")
        article["gics_sector"] = assign_sector(text)
        article["impact_score"] = compute_impact_score(article, profile)

    # Generate embeddings and cluster
    if EMBEDDINGS_AVAILABLE and SKLEARN_AVAILABLE:
        embeddings = embed_articles(articles)
        if embeddings is not None:
            raw_clusters = cluster_with_embeddings(articles, embeddings)
            method = "embedding+agglomerative"
        else:
            raw_clusters = cluster_by_sector(articles)
            method = "sector_fallback"
    else:
        raw_clusters = cluster_by_sector(articles)
        method = "sector_fallback"

    print(f"Clustering method: {method}")
    print(f"Found {len(raw_clusters)} clusters.")

    # Build output structure
    output: dict[str, list[dict]] = {}

    for cluster_id, indices in raw_clusters.items():
        cluster_articles = [articles[i] for i in indices]

        # Deduplicate
        cluster_articles = deduplicate_within_cluster(cluster_articles)

        if not cluster_articles:
            continue

        # Sort by impact score descending
        cluster_articles.sort(key=lambda a: a.get("impact_score", 0), reverse=True)

        # Assign cluster-level sector (most common sector in cluster)
        sectors = [a.get("gics_sector", "General Market") for a in cluster_articles]
        cluster_sector = max(set(sectors), key=sectors.count)

        # Select top representative articles (max 2 per cluster)
        top_articles = cluster_articles[:2]

        for art in cluster_articles:
            art["cluster_id"] = cluster_id
            art["cluster_sector"] = cluster_sector

        label = str(cluster_id)
        output[label] = cluster_articles

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_articles = sum(len(v) for v in output.values())
    print(f"\nClustering complete:")
    print(f"  Clusters: {len(output)}")
    print(f"  Articles retained: {total_articles}")
    print(f"  Method: {method}")
    print(f"\nSaved to: {OUTPUT_PATH}")

    return output


if __name__ == "__main__":
    run_clustering()
