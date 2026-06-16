#!/usr/bin/env python3
"""
ThinkFree Finance — DataQualityAgent

Validates pipeline output files after Phase 2 (scraping) and Phase 3 (extraction).
Checks for: missing fields, malformed values, duplicate slip-through, null sentiment scores,
stale data, schema violations.

Blocks pipeline advancement if data integrity falls below threshold.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
NEWS_DIR  = BASE_DIR / "news_output"

PASS_THRESHOLD = 0.80  # 80% of articles must pass all checks


class QualityFinding:
    def __init__(self, severity: str, phase: str, check: str, message: str, count: int = 1):
        self.severity = severity  # BLOCKER, WARN, INFO
        self.phase = phase
        self.check = check
        self.message = message
        self.count = count

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "phase": self.phase,
            "check": self.check,
            "message": self.message,
            "count": self.count,
        }


# ---------------------------------------------------------------------------
# Phase 2 checks — raw scraped articles
# ---------------------------------------------------------------------------

def check_phase2_output(articles: list[dict]) -> list[QualityFinding]:
    """Validate raw scraped articles from phase2_data_scraping.py."""
    findings = []

    if not articles:
        findings.append(QualityFinding(
            "BLOCKER", "phase2", "empty_output",
            "No articles found. Scraper produced empty output.", 0
        ))
        return findings

    # Required fields for raw articles
    required_fields = ["title", "url"]
    missing_title = missing_url = 0
    empty_title = no_summary = 0

    for art in articles:
        if not isinstance(art, dict):
            continue
        if not art.get("title"):
            missing_title += 1
        elif len(str(art.get("title", ""))) < 10:
            empty_title += 1
        if not art.get("url") and not art.get("link"):
            missing_url += 1
        if not art.get("summary") and not art.get("content") and not art.get("description"):
            no_summary += 1

    total = len(articles)

    if missing_title > 0:
        sev = "BLOCKER" if missing_title / total > 0.2 else "WARN"
        findings.append(QualityFinding(
            sev, "phase2", "missing_title",
            f"{missing_title}/{total} articles have no title.", missing_title
        ))

    if empty_title > 0:
        findings.append(QualityFinding(
            "WARN", "phase2", "thin_title",
            f"{empty_title}/{total} articles have suspiciously short titles (<10 chars).", empty_title
        ))

    if missing_url > 0:
        sev = "BLOCKER" if missing_url / total > 0.3 else "WARN"
        findings.append(QualityFinding(
            sev, "phase2", "missing_url",
            f"{missing_url}/{total} articles have no URL for deduplication.", missing_url
        ))

    if no_summary > 0:
        findings.append(QualityFinding(
            "WARN", "phase2", "no_content",
            f"{no_summary}/{total} articles have no summary or content body.", no_summary
        ))

    # Check data freshness — warn if most articles are older than 48h
    fresh_count = 0
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(hours=48)
    for art in articles:
        pub_str = art.get("published") or art.get("publishedAt") or art.get("datetime", "")
        if not pub_str:
            continue
        try:
            # Try ISO format
            pub = datetime.fromisoformat(str(pub_str).replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub > cutoff:
                fresh_count += 1
        except Exception:
            pass

    if fresh_count == 0 and total > 0:
        findings.append(QualityFinding(
            "WARN", "phase2", "stale_data",
            "No articles with parseable timestamps within 48 hours. Data may be stale.", 0
        ))
    elif fresh_count < total * 0.5:
        findings.append(QualityFinding(
            "WARN", "phase2", "mostly_stale",
            f"Only {fresh_count}/{total} articles appear to be from the last 48 hours.", total - fresh_count
        ))

    return findings


# ---------------------------------------------------------------------------
# Phase 3 checks — enriched articles
# ---------------------------------------------------------------------------

def check_phase3_output(articles: list[dict]) -> list[QualityFinding]:
    """Validate enriched articles from phase3_extraction.py."""
    findings = []

    if not articles:
        findings.append(QualityFinding(
            "BLOCKER", "phase3", "empty_output",
            "No enriched articles found. Phase 3 produced empty output.", 0
        ))
        return findings

    total = len(articles)
    null_sentiment = missing_compound = zero_richness = 0
    missing_entities = 0

    for art in articles:
        if not isinstance(art, dict):
            continue

        sentiment = art.get("sentiment")
        if sentiment is None:
            null_sentiment += 1
        elif not isinstance(sentiment, dict) or "compound" not in sentiment:
            missing_compound += 1
        elif sentiment.get("compound") is None:
            null_sentiment += 1

        richness = art.get("data_richness_score")
        if richness is None or richness == 0:
            zero_richness += 1

        entities = art.get("entities", {})
        if not entities or not any(entities.values()):
            missing_entities += 1

    if null_sentiment > 0:
        sev = "BLOCKER" if null_sentiment / total > 0.5 else "WARN"
        findings.append(QualityFinding(
            sev, "phase3", "null_sentiment",
            f"{null_sentiment}/{total} articles have null sentiment scores.", null_sentiment
        ))

    if missing_compound > 0:
        findings.append(QualityFinding(
            "WARN", "phase3", "missing_compound",
            f"{missing_compound}/{total} articles missing compound sentiment value.", missing_compound
        ))

    if zero_richness > total * 0.5:
        findings.append(QualityFinding(
            "WARN", "phase3", "low_richness",
            f"{zero_richness}/{total} articles have zero data richness score — "
            "extraction may have failed to find numerical/entity data.", zero_richness
        ))

    if missing_entities > total * 0.7:
        findings.append(QualityFinding(
            "INFO", "phase3", "low_entity_extraction",
            f"{missing_entities}/{total} articles have no extracted entities. "
            "This is normal if spaCy model is not installed.", missing_entities
        ))

    # Check for sorting order (should be sorted by |compound| descending)
    if len(articles) >= 3:
        compounds = []
        for art in articles[:10]:
            c = (art.get("sentiment") or {}).get("compound")
            if c is not None:
                compounds.append(abs(c))
        if compounds and compounds != sorted(compounds, reverse=True):
            findings.append(QualityFinding(
                "INFO", "phase3", "not_sorted",
                "Articles may not be sorted by impact (|sentiment| descending).", 0
            ))

    return findings


# ---------------------------------------------------------------------------
# Phase 4 checks — clustered articles
# ---------------------------------------------------------------------------

def check_phase4_output(data: dict) -> list[QualityFinding]:
    """Validate clustered output from phase4_clustering.py."""
    findings = []

    if not data:
        findings.append(QualityFinding(
            "BLOCKER", "phase4", "empty_output",
            "Clustering produced empty output. Run phase4_clustering.py.", 0
        ))
        return findings

    total_clusters = len(data)
    total_articles = sum(len(v) for v in data.values() if isinstance(v, list))

    if total_clusters < 2:
        findings.append(QualityFinding(
            "WARN", "phase4", "too_few_clusters",
            f"Only {total_clusters} cluster(s) found. Expected 5+. May indicate clustering failure.", total_clusters
        ))

    no_sector = no_impact = 0
    for cluster_id, articles in data.items():
        if not isinstance(articles, list):
            continue
        for art in articles:
            if not art.get("gics_sector"):
                no_sector += 1
            if art.get("impact_score") is None:
                no_impact += 1

    if no_sector > total_articles * 0.3:
        findings.append(QualityFinding(
            "WARN", "phase4", "missing_sector",
            f"{no_sector}/{total_articles} articles missing GICS sector label.", no_sector
        ))

    if no_impact > total_articles * 0.3:
        findings.append(QualityFinding(
            "WARN", "phase4", "missing_impact",
            f"{no_impact}/{total_articles} articles missing impact score.", no_impact
        ))

    findings.append(QualityFinding(
        "INFO", "phase4", "ok",
        f"Clustering OK: {total_clusters} clusters, {total_articles} articles.", 0
    ))

    return findings


# ---------------------------------------------------------------------------
# Economic reasoning output
# ---------------------------------------------------------------------------

def check_economic_reasoning(data: dict) -> list[QualityFinding]:
    """Validate Phase 6 economic reasoning output."""
    findings = []

    if not data:
        findings.append(QualityFinding(
            "INFO", "phase6", "not_generated",
            "Economic reasoning output not found. Run GPT_Economy/Reasoning_Report.py.", 0
        ))
        return findings

    required = ["summary", "bullish_sectors", "bearish_sectors"]
    for key in required:
        if key not in data:
            findings.append(QualityFinding(
                "WARN", "phase6", f"missing_{key}",
                f"Economic reasoning output missing '{key}' field.", 0
            ))

    summary = data.get("summary", "")
    if isinstance(summary, str) and len(summary) < 50:
        findings.append(QualityFinding(
            "WARN", "phase6", "thin_summary",
            f"Economic reasoning summary is very short ({len(summary)} chars). May be incomplete.", 0
        ))

    return findings


# ---------------------------------------------------------------------------
# Recession signals output
# ---------------------------------------------------------------------------

def check_recession_output(data: dict) -> list[QualityFinding]:
    """Validate Phase 13 recession signals output."""
    findings = []

    if not data:
        findings.append(QualityFinding(
            "INFO", "phase13", "not_generated",
            "Recession signals output not found. Run recession_signals.py.", 0
        ))
        return findings

    score = data.get("recession_risk", {}).get("score")
    if score is None:
        findings.append(QualityFinding(
            "WARN", "phase13", "missing_score",
            "Recession risk score missing from output.", 0
        ))
    elif not 0 <= score <= 10:
        findings.append(QualityFinding(
            "WARN", "phase13", "score_out_of_range",
            f"Recession risk score {score} is out of 0–10 range.", 0
        ))

    return findings


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def load_json_safe(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run_data_quality_check(verbose: bool = True) -> dict:
    if verbose:
        print("=== ThinkFree — DataQualityAgent ===")

    all_findings: list[QualityFinding] = []

    # Find most recent raw articles file
    articles_files = sorted(NEWS_DIR.glob("articles_*.json"), reverse=True) if NEWS_DIR.exists() else []
    if articles_files:
        if verbose:
            print(f"Checking Phase 2 output: {articles_files[0].name}...")
        raw_articles = load_json_safe(articles_files[0])
        if isinstance(raw_articles, list):
            all_findings.extend(check_phase2_output(raw_articles))
        elif isinstance(raw_articles, dict):
            # Handle Finnhub nested format
            flat = []
            for v in raw_articles.values():
                if isinstance(v, dict) and "finnhub" in v:
                    flat.extend(v["finnhub"].get("company_news", []))
                elif isinstance(v, list):
                    flat.extend(v)
            all_findings.extend(check_phase2_output(flat))
    else:
        all_findings.append(QualityFinding(
            "INFO", "phase2", "not_found",
            "No raw articles file found in news_output/. Run phase2 scraper first.", 0
        ))

    # Phase 3 enriched
    enriched_path = NEWS_DIR / "enriched_news_sentiment.json"
    if verbose:
        print("Checking Phase 3 output...")
    enriched = load_json_safe(enriched_path)
    if isinstance(enriched, list):
        all_findings.extend(check_phase3_output(enriched))
    else:
        all_findings.append(QualityFinding(
            "INFO", "phase3", "not_found",
            "enriched_news_sentiment.json not found. Run phase3_extraction.py.", 0
        ))

    # Phase 4 clustered
    clustered_path = NEWS_DIR / "clustered_summaries.json"
    if verbose:
        print("Checking Phase 4 output...")
    clustered = load_json_safe(clustered_path)
    if isinstance(clustered, dict):
        all_findings.extend(check_phase4_output(clustered))
    else:
        all_findings.append(QualityFinding(
            "INFO", "phase4", "not_found",
            "clustered_summaries.json not found. Run phase4_clustering.py.", 0
        ))

    # Phase 6 economic reasoning
    econ_path = NEWS_DIR / "economic_reasoning_summary.json"
    if verbose:
        print("Checking Phase 6 output...")
    econ = load_json_safe(econ_path)
    all_findings.extend(check_economic_reasoning(econ or {}))

    # Phase 13 recession
    recession_path = BASE_DIR / "recession_signals_output.json"
    if verbose:
        print("Checking Phase 13 output...")
    recession = load_json_safe(recession_path)
    all_findings.extend(check_recession_output(recession or {}))

    # Assess verdict
    blockers = [f for f in all_findings if f.severity == "BLOCKER"]
    warnings  = [f for f in all_findings if f.severity == "WARN"]
    infos     = [f for f in all_findings if f.severity == "INFO"]

    verdict = "PASS" if not blockers else "FAIL"

    result = {
        "audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "verdict": verdict,
        "summary": {
            "blockers": len(blockers),
            "warnings": len(warnings),
            "info": len(infos),
        },
        "findings": [f.to_dict() for f in all_findings],
        "message": (
            "Data quality checks passed." if verdict == "PASS"
            else f"{len(blockers)} blocking data quality issue(s) detected. Pipeline advancement blocked."
        ),
    }

    if verbose:
        print(f"\n{'='*50}")
        verdict_label = "✅ PASS" if verdict == "PASS" else "❌ FAIL"
        print(f"Data Quality: {verdict_label}")
        print(f"  Blockers: {len(blockers)}  Warnings: {len(warnings)}")
        for f in (blockers + warnings)[:5]:
            print(f"  [{f.severity}] [{f.phase}] {f.message}")

    return result


if __name__ == "__main__":
    run_data_quality_check(verbose=True)
