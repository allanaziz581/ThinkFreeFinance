#!/usr/bin/env python3
"""
ThinkFree Finance, Phase 6: Economic Reasoning Engine
Queries FAISS economic knowledge base and generates plain-English sector analysis.
"""

from __future__ import annotations

import json
import os
import faiss
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS as LCFAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

SECTOR_SUMMARY_PATH = BASE_DIR / "news_output" / "sector_summaries.json"
FAISS_INDEX_PATH    = BASE_DIR / "Economic_Books" / "FAISS_Store"
FAISS_INDEX_FILE    = "economic_knowledge_index.faiss"
FAISS_METADATA_FILE = "economic_knowledge_metadata.json"
OUTPUT_PATH         = BASE_DIR / "news_output" / "economic_reasoning_summary.json"

MODULE_FOLDER_PATHS = {
    "Economics Fundamentals (Macro & Micro)": str(BASE_DIR / "Economic_Books" / "Economics Fundamentals (Macro & Micro)"),
    "Behavioral, Fiscal, and Modern Policy":  str(BASE_DIR / "Economic_Books" / "Behavioral, Fiscal, and Modern Policy"),
    "Investing and Market Behavior":           str(BASE_DIR / "Economic_Books" / "Investing and Market Behavior"),
}

# Titles below are the EXACT `title` values stored in the FAISS metadata
# (economic_knowledge_metadata.json), matching is done case-insensitively and
# whitespace-stripped (see _title_to_module_map). Each is assigned the module of
# the physical Economic_Books/ subfolder it was embedded from. Keeping these in
# sync with the embedded titles is what makes module-filtered retrieval work;
# a mismatch silently collapses everything to "Uncategorized".
BOOK_METADATA = [
    # Economics Fundamentals (Macro & Micro)
    {"title": "Principles_of_Economics_Mankiw",                               "module": "Economics Fundamentals (Macro & Micro)"},
    {"title": "Macroeconomics_Krugman",                                       "module": "Economics Fundamentals (Macro & Micro)"},
    {"title": "Wealth-Nations_Smith",                                         "module": "Economics Fundamentals (Macro & Micro)"},
    {"title": "Economics-in-One-Lesson_Hazlitt",                             "module": "Economics Fundamentals (Macro & Micro)"},
    {"title": "Freakonomics_Levitt_Dubner",                                   "module": "Economics Fundamentals (Macro & Micro)"},
    # Behavioral, Fiscal, and Modern Policy
    {"title": "Daniel Kahneman-Thinking, Fast and Slow",                      "module": "Behavioral, Fiscal, and Modern Policy"},
    {"title": "Misbehaving-The-Making-of-Behavioral-Economics-Richard-H-Thaler", "module": "Behavioral, Fiscal, and Modern Policy"},
    {"title": "The Deficit Myth Modern Monetary Theory and the Birth of the Peoples Economy by Stephanie Kelton", "module": "Behavioral, Fiscal, and Modern Policy"},
    {"title": "Lords_of_Finance_Liaquat_Ahamed",                             "module": "Behavioral, Fiscal, and Modern Policy"},
    # Investing and Market Behavior
    {"title": "security-analysis-benjamin-graham",                           "module": "Investing and Market Behavior"},
    {"title": "Intelligent_Investor_Graham",                                 "module": "Investing and Market Behavior"},
    {"title": "A-random-walk-down-wall-street_malkiel",                       "module": "Investing and Market Behavior"},
    {"title": "Irrational_Exuberance_Shiller",                               "module": "Investing and Market Behavior"},
    {"title": "Edwin_LeFevre_Reminiscences_of_a_Stock_Operator",             "module": "Investing and Market Behavior"},
]

MODULE_KEYWORDS = {
    "Economics Fundamentals (Macro & Micro)": [
        "inflation", "interest rate", "interest rates", "gdp", "monetary", "fiscal",
        "unemployment", "employment", "job market", "labor market", "supply", "demand",
        "aggregate", "productivity", "price level", "recession", "growth", "trade balance",
        "rate hike", "cpi", "federal reserve", "central bank",
    ],
    "Behavioral, Fiscal, and Modern Policy": [
        "sentiment", "bias", "expectations", "behavioral", "consumer confidence", "fiscal deficit",
        "budget deficit", "gov spending", "stimulus", "fiscal policy", "irrational", "nudge",
        "modern monetary theory", "mmt", "confidence", "psychology",
    ],
    "Investing and Market Behavior": [
        "stock", "stocks", "bond", "bonds", "portfolio", "volatility", "dividend", "etf", "yield",
        "valuation", "capital", "market", "hedge", "asset", "beta", "alpha", "mutual fund",
        "price to earnings", "pe ratio", "equity", "equities", "securities", "market cap",
    ],
}


def _title_to_module_map() -> dict[str, str]:
    return {b["title"].strip().lower(): b["module"] for b in BOOK_METADATA}


def classify_modules(text: str) -> list[str]:
    text_lower = text.lower()
    return [
        module for module, keywords in MODULE_KEYWORDS.items()
        if any(kw in text_lower for kw in keywords)
    ]


def load_sector_summaries() -> dict:
    with open(SECTOR_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_multi_module_retriever(modules: list[str]):
    embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")

    faiss_file = FAISS_INDEX_PATH / FAISS_INDEX_FILE
    meta_file  = FAISS_INDEX_PATH / FAISS_METADATA_FILE

    if not faiss_file.exists():
        raise FileNotFoundError(f"FAISS index not found: {faiss_file}")
    if not meta_file.exists():
        raise FileNotFoundError(f"FAISS metadata not found: {meta_file}")

    index = faiss.read_index(str(faiss_file))
    with open(meta_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    title_map = _title_to_module_map()
    for m in metadata:
        m["module"] = title_map.get(m.get("title", "").strip().lower(), "Uncategorized")

    documents = [Document(page_content=m["text"], metadata=m) for m in metadata]
    docstore  = InMemoryDocstore({str(i): doc for i, doc in enumerate(documents)})

    if modules:
        filtered = [d for d in documents if d.metadata.get("module") in modules]
        if not filtered:
            filtered = documents
        retriever_db = LCFAISS.from_documents(filtered, embedding_model)
        return retriever_db.as_retriever(search_kwargs={"k": 6})

    return LCFAISS(embedding_model, index, docstore, {}).as_retriever(search_kwargs={"k": 6})


def run_reasoning_on_summaries() -> str:
    summaries = load_sector_summaries()
    all_text  = "\n\n".join(v["sector_summary"] for v in summaries.values())

    matched_modules = classify_modules(all_text)
    retriever = get_multi_module_retriever(matched_modules)

    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

    reasoning_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=False,
    )

    prompt = f"""
You are an experienced financial advisor and economist trained in classical economic principles.
Based only on the provided economic textbook material, read the following sector summaries from different parts of the market.

Create a summarized and unified explanation of what is happening in the economy right now.
Make it as detailed as possible, but less than 800 words, using the sector summaries provided.

Write clearly in plain English so the average person can understand. Focus on:
- What trends are emerging?
- If there is any political or war news, how it could affect the economy?
- What sectors are being affected, and how?
- Why are these things happening (the economic causes)?
- What are the consequences so far, and what might happen next?
- Which sectors may be positively or negatively affected by current events, and which are unaffected?

Explain what is happening and why it matters to an ordinary person's finances. Do NOT
recommend specific stocks to buy or sell; ThinkFree explains the economy, it is not a
stock-picking service.

At the very end, list the bullish and bearish sectors in this exact format:

Bullish: [comma-separated sectors]
Bearish: [comma-separated sectors]

SECTOR DATA:
---
{all_text}
---
"""

    result = reasoning_chain.invoke({"query": prompt})
    return result["result"] if isinstance(result, dict) and "result" in result else str(result)


def extract_bull_bear(summary_text: str) -> tuple[list[str], list[str]]:
    bullish, bearish = [], []
    for line in summary_text.strip().splitlines()[-5:]:
        if line.lower().startswith("bullish:"):
            bullish = [s.strip().title() for s in line.split(":", 1)[1].split(",") if s.strip()]
        elif line.lower().startswith("bearish:"):
            bearish = [s.strip().title() for s in line.split(":", 1)[1].split(",") if s.strip()]
    return bullish, bearish


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Add it to your .env file.")

    print("Running economic reasoning analysis...")
    report = run_reasoning_on_summaries()

    bullish_sectors, bearish_sectors = extract_bull_bear(report)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": report, "bullish_sectors": bullish_sectors, "bearish_sectors": bearish_sectors}, f, indent=2)

    print(f"Economic reasoning summary saved to: {OUTPUT_PATH}")
    print(f"Bullish sectors: {bullish_sectors}")
    print(f"Bearish sectors: {bearish_sectors}")
    return report


if __name__ == "__main__":
    main()
