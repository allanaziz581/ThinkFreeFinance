# Part 7B — Supporting Engines: Economic Reasoning, Clustering, Technical Analysis & Backtesting

This document is an exhaustive technical reference for every Python file that powers the non-scraping, non-UI pipeline stages of ThinkFree Finance. Each section covers: the file's role and phase, all external library dependencies, every function (signature, parameters, return value, behavior, files read/written), and verbatim reproduction of scoring formulas, indicator parameters, and GPT prompt templates found in the source code.

---

## Table of Contents

1. [GPT_Economy/economic_engine.py](#1-gpt_economyeconomic_enginepy) — Phase 6 FAISS Index Builder
2. [GPT_Economy/Reasoning_Report.py](#2-gpt_economyreasoning_reportpy) — Phase 6 Economic Reasoning Engine
3. [Profile/article_clustering.py](#3-profilearticle_clusteringpy) — Phase 5 GPT Article Summarization & Validation
4. [Profile/GPT_article_clustering_summary.py](#4-profilegpt_article_clustering_summarypy) — Phase 4 Sector Summary Generator
5. [Module_2_Technical_Analysis/ta_analysis.py](#5-module_2_technical_analysista_analysispy) — Technical Analysis Engine
6. [Module_2_Technical_Analysis/phase_2_q_lib.py](#6-module_2_technical_analysisphase_2_q_libpy) — Qlib Feature Export
7. [Module_2_Technical_Analysis/phase_3_signal.py](#7-module_2_technical_analysisphase_3_signalpy) — Signal Generation
8. [Module_2_Technical_Analysis/pipeline_alpha.py](#8-module_2_technical_analysispipeline_alphapy) — Qlib LightGBM Pipeline
9. [Module_2_Technical_Analysis/prepare_qlib_data.py](#9-module_2_technical_analysisprepare_qlib_datapy) — Qlib Data Formatter
10. [Module_2_Technical_Analysis/phase_4_backtrader.py](#10-module_2_technical_analysisphase_4_backtraderpy) — Phase 9 Backtesting Engine
11. [validate_env.py](#11-validate_envpy) — Environment Validation Script

---

## 1. `GPT_Economy/economic_engine.py`

### Role and Phase

**Phase 6 — Economic Reasoning Engine (FAISS index build step).**
This is the *index construction* script. It walks a directory of economics PDF textbooks, extracts all page text, embeds each page using a local sentence-transformer model, and persists a FAISS flat L2 index alongside a JSON metadata file. The resulting index is later queried by `Reasoning_Report.py` to answer economic questions grounded in textbook knowledge.

> **macOS segfault constraint:** This file calls `SentenceTransformer(EMBEDDING_MODEL)` at module level (line 19). On macOS with `torch==2.2.2`, this causes a segfault when the object is instantiated at import time. The known workaround (documented in `MEMORY.md`) is to avoid loading the model at runtime and instead use keyword-scan on FAISS metadata. The `economic_engine_insider.py` variant applies this workaround.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `fitz` (PyMuPDF) | `import fitz` | PDF page text extraction |
| `faiss` | `import faiss` | Vector index construction and persistence |
| `numpy` | `import numpy as np` | Float32 array coercion |
| `tqdm` | `from tqdm import tqdm` | Progress bar over book files |
| `sentence_transformers` | `from sentence_transformers import SentenceTransformer` | Local embedding model |
| `os`, `json` | stdlib | Directory walking, JSON serialisation |

### Configuration Constants

```
ECON_BOOK_DIR   = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/Economic_Books"
FAISS_STORE_DIR = <ECON_BOOK_DIR>/FAISS_Store
EMBEDDING_MODEL = "all-MiniLM-L6-v2"          # 384-dimensional embeddings
INDEX_OUTPUT    = <FAISS_STORE_DIR>/economic_knowledge_index.faiss
METADATA_OUTPUT = <FAISS_STORE_DIR>/economic_knowledge_metadata.json
```

The FAISS index is a `faiss.IndexFlatL2(384)` — exact brute-force L2 search, no quantization, 384 dimensions to match `all-MiniLM-L6-v2` output.

### Functions

---

#### `extract_full_pages`

```python
def extract_full_pages(pdf_path: str) -> list[str]
```

**Parameters:**
- `pdf_path` — absolute path to a `.pdf` file.

**Returns:** A list of stripped page-text strings, one element per page that contains non-whitespace text. Empty or whitespace-only pages are skipped. Pages that throw an extraction error are silently skipped; books that fail to open are silently skipped.

**Behavior:**
1. Opens the PDF with `fitz.open(pdf_path)`.
2. Iterates over every page index `page_number` from 0 to `len(doc) - 1`.
3. Calls `page.get_text("text")` in plain-text mode.
4. If the result is non-empty after `.strip()`, appends to the return list.
5. Per-page and per-book exceptions are caught and printed; the loop continues.

**Files read:** one PDF file per call.
**Files written:** none.

---

#### `embed_texts`

```python
def embed_texts(texts: List[str]) -> np.ndarray
```

**Parameters:**
- `texts` — a list of strings to embed (typically a batch of 10 pages).

**Returns:** A `np.ndarray` of shape `(len(texts), 384)` and dtype `float32`. On error, returns an empty array of shape `(0, 384)`.

**Behavior:**
1. Calls `model.encode(texts, convert_to_numpy=True)` where `model` is the module-level `SentenceTransformer("all-MiniLM-L6-v2")` instance (line 19).
2. Casts result to `float32` via `np.asarray(..., dtype="float32")`.
3. On any exception, prints the error and returns the empty fallback array.

**Files read/written:** none.

---

#### `main`

```python
def main() -> None
```

**Parameters:** none.

**Returns:** none (side-effect: writes two files).

**Behavior:**
1. Creates a `faiss.IndexFlatL2(384)` index and an empty `metadata` list.
2. Walks `ECON_BOOK_DIR` recursively with `os.walk`, collecting all `.pdf` paths (case-insensitive suffix check).
3. For each PDF, derives a `title` from the filename stem (`os.path.splitext(os.path.basename(...))[0]`).
4. Calls `extract_full_pages` to get all page texts.
5. Processes pages in **batches of 10** (`range(0, len(pages), 10)`).
6. Calls `embed_texts(batch)` on each batch.
7. Validates: the result must be a 2-D `np.ndarray` with at least one row.
8. Adds valid embeddings to the FAISS index with `index.add(embeddings)`.
9. For each page in the batch, appends a metadata entry:
   ```json
   {"title": "<stem>", "page_index": <i+j>, "text": "<page_text>"}
   ```
10. Writes the FAISS index to `INDEX_OUTPUT` with `faiss.write_index`.
11. Writes all metadata to `METADATA_OUTPUT` as pretty-printed JSON.

**Files read:** all `.pdf` files under `ECON_BOOK_DIR`.
**Files written:**
- `Economic_Books/FAISS_Store/economic_knowledge_index.faiss`
- `Economic_Books/FAISS_Store/economic_knowledge_metadata.json`

---

## 2. `GPT_Economy/Reasoning_Report.py`

### Role and Phase

**Phase 6 — Economic Reasoning Engine (query and synthesis step).**
Reads pre-computed sector summaries, loads the FAISS index built by `economic_engine.py`, selects the most relevant textbook modules using keyword classification, runs a LangChain `RetrievalQA` chain backed by GPT-4o, and writes a JSON report containing a plain-English economic analysis plus bullish/bearish sector lists.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `faiss` | `import faiss` | Reading the persisted FAISS index |
| `numpy` | `import numpy as np` | Array handling |
| `python-dotenv` | `from dotenv import load_dotenv` | `.env` API key loading |
| `langchain_community` | `FAISS as LCFAISS`, `InMemoryDocstore` | LangChain vector store wrapper |
| `langchain` | `Document`, `RetrievalQA` | Document schema and QA chain |
| `langchain_openai` | `OpenAIEmbeddings`, `ChatOpenAI` | OpenAI embedding + chat model integration |
| `os`, `json`, `pathlib` | stdlib | File I/O |

### Path Constants

```
BASE_DIR           = <repo_root>
SECTOR_SUMMARY_PATH = <BASE_DIR>/news_output/sector_summaries.json        (read)
FAISS_INDEX_PATH    = <BASE_DIR>/Economic_Books/FAISS_Store                (read)
FAISS_INDEX_FILE    = "economic_knowledge_index.faiss"
FAISS_METADATA_FILE = "economic_knowledge_metadata.json"
OUTPUT_PATH         = <BASE_DIR>/news_output/economic_reasoning_summary.json (written)
```

### Book Catalogue

`BOOK_METADATA` (lines 37-53) is a list of 15 dicts mapping book title stems to one of three modules:
- `"Economics Fundamentals (Macro & Micro)"` — Keynes, Friedman, Piketty, Dalio, Minsky, Kindleberger
- `"Behavioral, Fiscal, and Modern Policy"` — Kahneman, Shiller, Thaler, Krugman
- `"Investing and Market Behavior"` — Graham, Taleb, Malkiel, Lewis, Soros

### Module Keyword Mapping

`MODULE_KEYWORDS` (lines 55-72) maps each module name to a keyword list used for automatic module selection:

```python
"Economics Fundamentals (Macro & Micro)": [
    "inflation", "interest rate", "interest rates", "gdp", "monetary", "fiscal",
    "unemployment", "employment", "job market", "labor market", "supply", "demand",
    "aggregate", "productivity", "price level", "recession", "growth", "trade balance",
    "rate hike", "cpi", "federal reserve", "central bank",
]
"Behavioral, Fiscal, and Modern Policy": [
    "sentiment", "bias", "expectations", "behavioral", "consumer confidence",
    "fiscal deficit", "budget deficit", "gov spending", "stimulus", "fiscal policy",
    "irrational", "nudge", "modern monetary theory", "mmt", "confidence", "psychology",
]
"Investing and Market Behavior": [
    "stock", "stocks", "bond", "bonds", "portfolio", "volatility", "dividend",
    "etf", "yield", "valuation", "capital", "market", "hedge", "asset", "beta",
    "alpha", "mutual fund", "price to earnings", "pe ratio", "equity", "equities",
    "securities", "market cap",
]
```

### Functions

---

#### `_title_to_module_map`

```python
def _title_to_module_map() -> dict[str, str]
```

**Returns:** A dict mapping lowercased, stripped book title stems to their module name, derived from `BOOK_METADATA`.

**Behavior:** Pure computation over the module-level constant list. No I/O.

---

#### `classify_modules`

```python
def classify_modules(text: str) -> list[str]
```

**Parameters:**
- `text` — any string (typically the concatenation of all sector summaries).

**Returns:** A list of module name strings (0–3 elements) for which at least one keyword appears in `text.lower()`. The order mirrors `MODULE_KEYWORDS` iteration order.

**Behavior:** Simple substring membership test; no regex or NLP. All three modules can be returned simultaneously.

---

#### `load_sector_summaries`

```python
def load_sector_summaries() -> dict
```

**Returns:** The parsed JSON object from `SECTOR_SUMMARY_PATH`. Expected structure: `{sector_name: {"sector_summary": str, "articles_count": int}}`.

**Files read:** `news_output/sector_summaries.json`

---

#### `get_multi_module_retriever`

```python
def get_multi_module_retriever(modules: list[str]) -> langchain VectorStoreRetriever
```

**Parameters:**
- `modules` — list of module name strings (output of `classify_modules`).

**Returns:** A LangChain retriever configured with `k=6` (return 6 documents per query).

**Behavior:**
1. Instantiates `OpenAIEmbeddings(model="text-embedding-ada-002")`.
2. Reads the FAISS index from disk with `faiss.read_index(str(faiss_file))`.
3. Reads metadata JSON and enriches each entry with its `module` field using `_title_to_module_map()`.
4. Wraps metadata entries as `langchain.schema.Document` objects (`page_content=m["text"]`, `metadata=m`).
5. Builds an `InMemoryDocstore` keyed by string integer index.
6. If `modules` is non-empty: filters `documents` to only those whose `metadata["module"]` is in `modules`. If filtering yields an empty set, falls back to all documents. Builds a new `LCFAISS` vector store from filtered docs using `LCFAISS.from_documents(filtered, embedding_model)`.
7. If `modules` is empty: constructs a full `LCFAISS(embedding_model, index, docstore, {})` directly from the pre-built FAISS index.
8. Returns `.as_retriever(search_kwargs={"k": 6})`.

**Files read:**
- `Economic_Books/FAISS_Store/economic_knowledge_index.faiss`
- `Economic_Books/FAISS_Store/economic_knowledge_metadata.json`

---

#### `run_reasoning_on_summaries`

```python
def run_reasoning_on_summaries() -> str
```

**Returns:** The GPT-4o response string (the economic analysis report, up to ~800 words).

**Behavior:**
1. Calls `load_sector_summaries()` and concatenates all `sector_summary` values with double newlines: `"\n\n".join(v["sector_summary"] for v in summaries.values())`.
2. Calls `classify_modules(all_text)` to identify relevant knowledge modules.
3. Calls `get_multi_module_retriever(matched_modules)`.
4. Constructs `ChatOpenAI(model="gpt-4o", temperature=0.3)`.
5. Builds a `RetrievalQA.from_chain_type(llm=llm, retriever=retriever, return_source_documents=False)`.
6. Invokes the chain with the full prompt (see below).
7. Returns `result["result"]` if the response is a dict with a `"result"` key, otherwise `str(result)`.

**GPT-4o Prompt Template (verbatim, lines 139-164):**

```
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
- What stocks would be good to buy right now, and which ones to avoid?

At the very end, list the bullish and bearish sectors in this exact format:

Bullish: [comma-separated sectors]
Bearish: [comma-separated sectors]

SECTOR DATA:
---
{all_text}
---
```

**Model/settings:** `gpt-4o`, temperature `0.3`, `return_source_documents=False`.

---

#### `extract_bull_bear`

```python
def extract_bull_bear(summary_text: str) -> tuple[list[str], list[str]]
```

**Parameters:**
- `summary_text` — the full GPT output string.

**Returns:** A tuple `(bullish_sectors, bearish_sectors)` where each element is a list of title-cased sector name strings.

**Behavior:**
1. Takes the last 5 lines of `summary_text.strip().splitlines()`.
2. For each line, checks if it starts with `"bullish:"` (case-insensitive) or `"bearish:"` (case-insensitive).
3. Splits on `:` once, then splits the right side on `,`, strips whitespace, and applies `.title()` to each token.
4. Returns `(bullish, bearish)`.

---

#### `main`

```python
def main() -> None
```

**Behavior:**
1. Guards on `OPENAI_API_KEY` environment variable; raises `RuntimeError` if absent.
2. Calls `run_reasoning_on_summaries()` to get the report.
3. Calls `extract_bull_bear(report)`.
4. Creates `news_output/` if not present.
5. Writes JSON to `OUTPUT_PATH`:
   ```json
   {
     "summary": "<800-word report>",
     "bullish_sectors": ["Financials", ...],
     "bearish_sectors": ["Energy", ...]
   }
   ```

**Files written:** `news_output/economic_reasoning_summary.json`

---

## 3. `Profile/article_clustering.py`

### Role and Phase

**Phase 5 — GPT Article Summarization & Validation.**
Despite the filename (`article_clustering.py`), this script is the GPT summarization and fact-retention validation layer. It reads clustered article data, calls GPT-4o to summarize each article in 3–5 data-rich sentences, validates that key numeric figures survived the summarization, assigns GICS sectors via keyword matching, and writes two output files: a full summarized article list and an updated `sector_summaries.json`.

> Note: Phase 4 article clustering (KMeans/Agglomerative) is not present in this file. This script begins downstream of the clustering output and performs Phase 5 GPT summarization.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `openai` | `from openai import OpenAI` | GPT-4o API calls |
| `python-dotenv` | `from dotenv import load_dotenv` | `.env` API key loading |
| `re` | stdlib | Regex patterns for numeric retention check |
| `json`, `os`, `pathlib` | stdlib | File I/O |

### Regex Patterns

```python
PERCENT_PAT = re.compile(r"\b\d+(?:\.\d+)?%\b")
DOLLAR_PAT  = re.compile(r"\$\d+(?:,\d{3})*(?:\.\d{2})?")
DATE_PAT    = re.compile(
    r"\b(?:\d{1,2}[/-])?\d{1,2}[/-]\d{2,4}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b"
)
```

These three patterns are used in `validate_retention` to count numeric facts before and after summarization.

### GICS Sector Definitions

```python
GICS_SECTORS = [
    "Communication Services", "Consumer Discretionary", "Consumer Staples",
    "Energy", "Financials", "Health Care", "Industrials",
    "Information Technology", "Materials", "Real Estate", "Utilities",
]
```

### Sector Keyword Map (used in `assign_sector`)

```python
{
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
```

Falls back to `"General"` if no keyword matches.

### Functions

---

#### `assign_sector`

```python
def assign_sector(text: str) -> str
```

**Parameters:**
- `text` — raw article text (title + summary concatenated).

**Returns:** A GICS sector name string, or `"General"` if no keyword matches.

**Behavior:** Lowercases `text`, iterates the sector keyword map in definition order. Returns the first matching sector. Does not handle multiple-sector assignment.

---

#### `summarize_article`

```python
def summarize_article(client: OpenAI, model: str, article: dict) -> str
```

**Parameters:**
- `client` — an initialized `OpenAI` client instance.
- `model` — the model name string (hardcoded as `"gpt-4o"` at call site in `main`).
- `article` — a dict with keys `"title"` (or `"headline"`), `"summary"` (or `"content"`).

**Returns:** A stripped GPT response string (3–5 sentences). On API failure, returns up to the first 500 characters of the original `summary`.

**GPT Prompt Template (verbatim, lines 70-76):**

```
Summarize the following financial news article.
Include all quantitative data (percentages, dollar amounts, dates).
Keep it concise but data-rich (3-5 sentences):

---
{full_text}
---
```

**Model/settings:** `model` parameter (caller passes `"gpt-4o"`), `temperature=0.3`.

---

#### `validate_retention`

```python
def validate_retention(original: str, summary: str) -> bool
```

**Parameters:**
- `original` — the source text (title + summary joined by space).
- `summary` — the GPT-produced summary.

**Returns:** `True` if the summary retains at least half the numeric values found in the original, or if the original contains no numeric values. `False` otherwise.

**Retention formula:**

```
orig_vals = PERCENT_PAT.findall(original)
          + DOLLAR_PAT.findall(original)
          + DATE_PAT.findall(original)

summ_vals = PERCENT_PAT.findall(summary)
          + DOLLAR_PAT.findall(summary)
          + DATE_PAT.findall(summary)

passes = len(summ_vals) >= len(orig_vals) // 2
```

If `orig_vals` is empty, returns `True` unconditionally. Note: this uses integer floor division (`// 2`), so 1 value retained out of 2 original passes (0 >= 1 → fails; but 1 >= 1 passes).

---

#### `main`

```python
def main() -> None
```

**Behavior:**
1. Reads `OPENAI_API_KEY` from environment; raises `RuntimeError` if absent.
2. Reads `clustered_summaries.json` — raises `FileNotFoundError` if missing.
3. Normalizes the raw JSON to a flat list of article dicts (handles both `list` and `dict` input shapes).
4. Initializes `OpenAI(api_key=api_key)` and sets `model = "gpt-4o"`.
5. For each article:
   - Calls `assign_sector(title + " " + summary)` if no `sector` key is already present.
   - Calls `summarize_article(client, model, article)`.
   - Calls `validate_retention(full_text, gpt_summary)`. If it fails, prints a warning and falls back to `summary[:500]` (or the GPT result if non-empty).
   - Builds `enriched` dict by spreading all original article fields plus `"title"`, `"sector"`, `"gpt_summary"`.
   - Adds to `summarized` list and to `sector_buckets[sector]`.
6. Writes `clustered_articles_with_summaries.json`:
   ```json
   {"clusters": [{"cluster_id": 0, "top_articles": [<enriched article dicts>]}]}
   ```
7. Reads existing `sector_summaries.json` if present (to avoid overwriting sectors already summarized).
8. For each new sector bucket: joins all `gpt_summary` strings, truncates to 2000 characters, and writes to `sector_summaries.json` only if the sector key is not already present.

**Files read:**
- `news_output/clustered_summaries.json`
- `news_output/sector_summaries.json` (if exists, for merge)

**Files written:**
- `news_output/clustered_articles_with_summaries.json`
- `news_output/sector_summaries.json` (merged update)

---

## 4. `Profile/GPT_article_clustering_summary.py`

### Role and Phase

**Phase 4 (sector-level GPT summarization) — runs after Phase 4 clustering.**
Takes the `clustered_summaries.json` (output of article clustering), groups articles by GICS sector (`gics_sector` field), and runs a two-pass GPT summarization pipeline: first chunking articles into intermediate 4-sentence summaries, then combining intermediates into a single 12+ sentence sector overview with numeric retention validation. Writes `sector_summaries.json`.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `openai` | `from openai import OpenAI` | Chat completion API |
| `python-dotenv` | `from dotenv import load_dotenv` | `.env` loading |
| `re` | stdlib | Numeric retention regex |
| `itertools` | `from itertools import islice` | Chunking helper |
| `os`, `json` | stdlib | File I/O |

### Configuration Constants

```python
BASE_DIR    = <repo_root>
NEWS_DIR    = <BASE_DIR>/news_output
INPUT_FILE  = <NEWS_DIR>/clustered_summaries.json      (read)
OUTPUT_FILE = <NEWS_DIR>/sector_summaries.json         (written)

API_KEY     = os.getenv("OPENAI_API_KEY")
MODEL       = os.getenv("MODEL", "gpt-3.5-turbo")     # default: gpt-3.5-turbo
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.3))
CHUNK_SIZE  = int(os.getenv("CHUNK_SIZE", 50))         # max articles per chunk
```

### Regex Patterns (Retention Check)

```python
percent_re = re.compile(r"\b\d+(?:\.\d+)?%\b")
dollar_re  = re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?")
```

### GPT Prompt Templates (verbatim, lines 32-47)

**Phase 1 — Chunk summarization:**

System:
```
You are a professional financial analyst. Summarize the following article summaries into exactly 4 sentences,
including every percentage and dollar figure.
```

User:
```
Chunk of {n} article summaries:
{entries}
Please summarize into 4 sentences, preserving all numeric details.
```

**Phase 2 — Final sector overview:**

System:
```
You are a professional financial analyst. Combine the intermediate summaries into a comprehensive sector overview.
Your response must be at least 12 sentences long and include all percentages and dollar figures.
```

User:
```
Combine {n} intermediate summaries for the {sector} sector into a cohesive overview of at least 12 sentences,
preserving all numeric data:
{chunks}
```

### Functions

---

#### `chunked`

```python
def chunked(seq, size) -> Generator[list, None, None]
```

**Parameters:**
- `seq` — any iterable.
- `size` — chunk size (int).

**Returns:** Generator yielding lists of up to `size` elements.

**Behavior:** Uses `itertools.islice` to consume the iterator in fixed-size windows. Each yielded list is `[first] + list(islice(it, size-1))`.

---

### Module-Level Pipeline (not wrapped in a `main` function)

The summarization pipeline runs at module import time (no `if __name__ == "__main__"` guard beyond the execution context). The sequence is:

1. **Load input:** Opens `INPUT_FILE`. Normalizes to a dict `clusters` keyed by cluster label. If the raw JSON is a list, wraps it as `{'0': raw}`.
2. **Group by sector:** Iterates all articles; extracts `gics_sector` (default `'Unknown'`) and builds `sector_articles: dict[str, list[str]]`. Each article becomes the string `"- {summary} (URL: {url})"`.
3. **Per-sector two-pass summarization:**
   - **Pass 1 (chunking):** Splits the article list into chunks of `CHUNK_SIZE` (default 50). For each chunk, calls the OpenAI chat API (MODEL, TEMPERATURE, chunk prompt). Collects responses as `intermediate: list[str]`.
   - **Pass 2 (final overview):** Joins intermediates as `"- {s}"` lines and calls the final-overview prompt. Collects `final_text`.
   - **Retention check:** Counts `orig_vals = percent_re.findall(chunks_joined) + dollar_re.findall(chunks_joined)` and `found_vals` in `final_text`. Prints a warning if `len(found_vals) < len(orig_vals) * 0.8` (i.e., less than 80% of numeric tokens retained).
   - Stores `output[sector] = {"sector_summary": final_text.strip(), "articles_count": len(lines)}`.
4. **Save:** Writes `OUTPUT_FILE` as pretty-printed JSON.

**Retention threshold formula:**
```
warn if len(found_vals) < len(orig_vals) * 0.8
```
(80% numeric retention threshold; only a warning, not a regeneration trigger.)

**Files read:** `news_output/clustered_summaries.json`
**Files written:** `news_output/sector_summaries.json`

---

## 5. `Module_2_Technical_Analysis/ta_analysis.py`

### Role and Phase

**Phase 5/6 bridge — Technical Analysis Engine.**
Downloads 1-year daily OHLCV data for all tickers in bullish and bearish sectors (from the economic reasoning output), computes four technical indicators (MACD, RSI, SMA50, SMA200) using either `talib` (preferred) or the `ta` library fallback, derives three binary signal flags, and saves a unified CSV for downstream use by `phase_3_signal.py`, `prepare_qlib_data.py`, and `phase_4_backtrader.py`.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `yfinance` | `import yfinance as yf` | OHLCV data download |
| `pandas` | `import pandas as pd` | DataFrame operations |
| `numpy` | `import numpy as np` | Array operations |
| `talib` | `import talib as _talib` | TA-Lib C-extension indicators (optional) |
| `ta` | `import ta as _ta` | Pure-Python TA fallback |
| `tqdm` | `from tqdm import tqdm` | Progress bar |
| `concurrent.futures` | `ThreadPoolExecutor`, `as_completed` | Parallel ticker downloads (5 workers) |
| `json`, `os`, `warnings`, `pathlib` | stdlib | I/O and suppression of FutureWarnings |

### Configuration Constants

```python
LOOKBACK_DAYS = 365
BASE_DIR      = <repo_root>
OUTPUT_DIR    = Module_2_Technical_Analysis/
RAW_DATA_DIR  = <BASE_DIR>/raw_data/
MAPPING_PATH  = <BASE_DIR>/Profile/flat-ui__data-Sun Jun 15 2025.csv
REASONING_PATH = <BASE_DIR>/news_output/economic_reasoning_summary.json
OUTPUT_CSV    = Module_2_Technical_Analysis/ta_analysis_detailed.csv
```

### Indicator Parameters

| Indicator | Period / Setting |
|-----------|-----------------|
| MACD (fast) | 12 |
| MACD (slow) | 26 |
| MACD (signal) | 9 |
| RSI | 14 |
| SMA (short) | 50 |
| SMA (long) | 200 |

### Signal Derivation Rules

```
rsi_signal   = -1 if RSI > 70  (overbought)
             =  1 if RSI < 30  (oversold)
             =  0 otherwise
macd_signal  =  1 if MACD line > MACD signal line  (bullish)
             = -1 if MACD line <= MACD signal line  (bearish)
trend_signal =  1 if SMA50 > SMA200  (golden cross / uptrend)
             = -1 if SMA50 < SMA200  (death cross / downtrend)
```

### Functions

---

#### `load_sector_mapping`

```python
def load_sector_mapping() -> pd.DataFrame
```

**Returns:** A DataFrame with at minimum columns `ticker` (str) and `sector` (str). Ticker symbols have `.` replaced with `-` for yfinance compatibility (e.g., `BRK.B` → `BRK-B`).

**Files read:** `Profile/flat-ui__data-Sun Jun 15 2025.csv` (S&P 500 constituent list with GICS sectors).

---

#### `load_bullish_bearish`

```python
def load_bullish_bearish() -> tuple[list[str], list[str]]
```

**Returns:** A tuple `(bullish_sectors, bearish_sectors)`. Returns `([], [])` on any error or if `REASONING_PATH` does not exist.

**Files read:** `news_output/economic_reasoning_summary.json` (output of `Reasoning_Report.py`).

---

#### `save_raw_csv`

```python
def save_raw_csv(ticker: str, df_raw: pd.DataFrame) -> None
```

**Parameters:**
- `ticker` — ticker symbol string.
- `df_raw` — raw OHLCV DataFrame from yfinance.

**Behavior:** Creates `RAW_DATA_DIR` if needed, then saves `df_raw` to `<RAW_DATA_DIR>/<ticker>.csv` with index.

**Files written:** `raw_data/<ticker>.csv`

---

#### `compute_indicators`

```python
def compute_indicators(df_close: pd.Series) -> pd.DataFrame
```

**Parameters:**
- `df_close` — a pandas Series of closing prices, indexed by date.

**Returns:** A DataFrame indexed identically to `df_close`, containing columns:
- `macd` — MACD line value (float)
- `macd_signal_line` — MACD signal line value (float)
- `rsi` — RSI value (float, 0–100)
- `sma_50` — 50-day simple moving average (float)
- `sma_200` — 200-day simple moving average (float)
- `rsi_signal` — integer signal flag (-1, 0, 1)
- `macd_signal` — integer signal flag (1 or -1)
- `trend_signal` — integer signal flag (1 or -1)

**Behavior (TA-Lib path, `_TALIB=True`):**
```python
close = np.ascontiguousarray(s.values)
macd_line, macd_signal_line, _ = _talib.MACD(close)      # default: 12/26/9
rsi_arr     = _talib.RSI(close)                            # default: 14
sma_50_arr  = _talib.SMA(close, timeperiod=50)
sma_200_arr = _talib.SMA(close, timeperiod=200)
```

**Behavior (ta fallback, `_TALIB=False`):**
```python
macd_obj = _ta.trend.MACD(s)             # default: fast=12, slow=26, signal=9
macd     = macd_obj.macd().values
macd_sig = macd_obj.macd_signal().values
rsi      = _ta.momentum.RSIIndicator(s).rsi().values       # default window: 14
sma_50   = _ta.trend.SMAIndicator(s, window=50).sma_indicator().values
sma_200  = _ta.trend.SMAIndicator(s, window=200).sma_indicator().values
```

Signal rules applied via `numpy.where` (vectorized, lines 92-94):
```python
rsi_signal   = np.where(rsi > 70, -1, np.where(rsi < 30, 1, 0))
macd_signal  = np.where(macd > macd_signal_line, 1, -1)
trend_signal = np.where(sma_50 > sma_200, 1, -1)
```

---

#### `run_ta_analysis`

```python
def run_ta_analysis(ticker: str) -> pd.DataFrame | None
```

**Parameters:**
- `ticker` — a ticker symbol string.

**Returns:** A DataFrame of the last `LOOKBACK_DAYS` (365) rows of indicators with a prepended `ticker` column, or `None` on any error.

**Behavior:**
1. Downloads 1 year of daily OHLCV with `yf.download(ticker, period="1y", interval="1d", progress=False)`.
2. If the result has a `pd.MultiIndex` column (multiple tickers in one download), extracts the `"Close"` slice with `df.xs("Close", axis=1, level=0)`.
3. Drops NaN close prices.
4. Calls `compute_indicators(df_close)`.
5. Takes `df_ind.tail(LOOKBACK_DAYS)`.
6. Inserts `ticker` as the first column.
7. Saves raw OHLCV to `raw_data/<ticker>.csv` via `save_raw_csv`.
8. Returns the trimmed indicator DataFrame. Returns `None` on any exception.

---

#### `main`

```python
def main() -> None
```

**Behavior:**
1. Loads the sector mapping CSV and the bullish/bearish sector lists.
2. If either sector list is non-empty, filters the S&P 500 constituent list to tickers in those sectors only. Otherwise processes all S&P 500 tickers.
3. Runs `run_ta_analysis` concurrently using `ThreadPoolExecutor(max_workers=5)`.
4. Concatenates all non-None results, drops all-NaN rows, resets the index, and renames `"Date"` → `"date"` for downstream compatibility.
5. Writes the combined DataFrame to `OUTPUT_CSV`.

**Files read:**
- `Profile/flat-ui__data-Sun Jun 15 2025.csv`
- `news_output/economic_reasoning_summary.json` (if exists)

**Files written:**
- `Module_2_Technical_Analysis/ta_analysis_detailed.csv`
- `raw_data/<ticker>.csv` for each successfully downloaded ticker

---

## 6. `Module_2_Technical_Analysis/phase_2_q_lib.py`

### Role and Phase

**Qlib feature export — bridge between legacy `ta_analysis_results.json` and Qlib's CSV format.**
This is an early-stage utility script (not integrated with the newer `ta_analysis_detailed.csv` flow). It reads a now-superseded `ta_analysis_results.json`, converts signal strings to integers, generates a single-day synthetic datetime row per ticker, and writes a Qlib-compatible CSV.

> Note: This script uses hardcoded absolute paths and processes only the latest day's data (`dates[-1:]`). It is a proof-of-concept bridge, predating the `prepare_qlib_data.py` + `pipeline_alpha.py` flow.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `pandas` | `import pandas as pd` | DataFrame operations |
| `json` | stdlib | Reading TA results |
| `os` | stdlib | Directory creation |
| `datetime`, `timedelta` | stdlib | Synthetic date generation |

### Module-Level Pipeline (no functions defined)

1. **Load:** Reads `/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/news_output/ta_analysis_results.json` (hardcoded path).
2. **Combine:** Concatenates `ta_data["bullish_analysis"]` and `ta_data["bearish_analysis"]`.
3. **Date range:** Generates 365 dates going back from today; uses only the last date (`dates[-1:]`).
4. **Row construction:** For each stock in `combined`, creates one row:
   ```python
   {
       "datetime": date.strftime("%Y-%m-%d"),
       "instrument": ticker.upper(),
       "rsi": stock["rsi"],
       "macd": stock["macd"],
       "sma_50": stock["sma_50"],
       "sma_200": stock["sma_200"],
       "close": stock["close"],
       "rsi_signal":   1 if "oversold"   else -1 if "overbought" else 0,
       "macd_signal":  1 if "bullish"    else -1,
       "trend_signal": 1 if "bullish"    else -1,
       "label": None,
   }
   ```
5. **Save:** Writes `qlib_data/qlib_feature_data.csv` (no index).

**Files read:** `news_output/ta_analysis_results.json`
**Files written:** `qlib_data/qlib_feature_data.csv`

---

## 7. `Module_2_Technical_Analysis/phase_3_signal.py`

### Role and Phase

**Phase 3b — Multi-indicator signal generation and voting.**
Reads `ta_analysis_detailed.csv`, takes the most recent row per ticker (representing the current signal state), applies a weighted voting logic across RSI, MACD, SMA golden/death cross, OBV, ADX, and CCI, and outputs a `signal_output_phase3.json` with per-ticker BUY/SELL/HOLD verdicts and confidence scores.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `pandas` | `import pandas as pd` | CSV reading and DataFrame operations |
| `json`, `os`, `pathlib` | stdlib | File I/O |

### Configuration Constants

```python
LOOKBACK_DAYS = 5          # Not used in current logic (groupby tail(1) used instead)
TA_CSV_PATH  = Module_2_Technical_Analysis/ta_analysis_detailed.csv
OUTPUT_PATH  = Module_2_Technical_Analysis/signal_output_phase3.json
```

### Signal Voting Algorithm

The `confidence` score is an integer that increments/decrements per indicator:

| Indicator | Condition | Effect |
|-----------|-----------|--------|
| RSI | < 30 (oversold) | confidence += 1, added to support |
| RSI | > 70 (overbought) | confidence -= 1, added to support |
| RSI | 30–70 | added to contradiction |
| MACD vs Signal | MACD > signal line | confidence += 1 ("bullish crossover") |
| MACD vs Signal | MACD < signal line | confidence -= 1 ("bearish crossover") |
| MACD vs Signal | equal | added to contradiction |
| SMA50 vs SMA200 | SMA50 > SMA200 | confidence += 1 ("golden cross") |
| SMA50 vs SMA200 | SMA50 < SMA200 | confidence -= 1 ("death cross") |
| OBV | > 0 | confidence += 1 |
| OBV | <= 0 | added to contradiction |
| ADX | < 20 | added to contradiction ("weak trend") |
| ADX | >= 20 | added to support |
| CCI | abs(CCI) < 100 | added to contradiction ("neutral zone") |
| CCI | abs(CCI) >= 100 | added to support |

**Final signal rule:**
```
if confidence >= 2:  signal = "BUY"
elif confidence <= -2: signal = "SELL"
else:                signal = "HOLD"
```

Note: OBV, ADX, and CCI are handled if present in the CSV but are not computed by `ta_analysis.py`. They would be `NaN` in the standard pipeline, so their contributions default to contradiction or are skipped.

### Functions

---

#### `analyze_row`

```python
def analyze_row(row: pd.Series) -> dict
```

**Parameters:**
- `row` — a single row from the TA CSV as a pandas Series, expected to contain: `rsi`, `macd`, `macd_signal_line`, `sma_50`, `sma_200`, `obv`, `adx`, `cci`, `date`, `ticker`.

**Returns:** A dict:
```json
{
  "date": "YYYY-MM-DD",
  "ticker": "AAPL",
  "final_signal": "BUY" | "SELL" | "HOLD",
  "confidence_score": -3..+3,
  "supporting_indicators": ["RSI (oversold at 28.3)", "MACD bullish crossover"],
  "contradicting_indicators": ["CCI in neutral zone"],
  "reasoning": "Indicators suggest a bullish setup. Supporting: ... Conflicting: ..."
}
```

**Behavior:** Implements the voting table documented above. `NaN` values are handled via `pd.isna()` checks before each indicator block. The `macd_signal_line` column name is used (not `macd_signal`) to avoid confusion with the binary flag.

---

#### `main`

```python
def main() -> None
```

**Behavior:**
1. Checks `TA_CSV_PATH` existence; prints error and returns if absent.
2. Reads CSV; if no `"date"` column, renames the first column to `"date"`.
3. Sorts by `["ticker", "date"]`; takes the most recent row per ticker with `groupby("ticker").tail(1)`.
4. Applies `analyze_row` to each row via list comprehension.
5. Writes the resulting list to `OUTPUT_PATH`.
6. Prints summary counts: BUY / SELL / HOLD totals.

**Files read:** `Module_2_Technical_Analysis/ta_analysis_detailed.csv`
**Files written:** `Module_2_Technical_Analysis/signal_output_phase3.json`

---

## 8. `Module_2_Technical_Analysis/pipeline_alpha.py`

### Role and Phase

**Qlib LightGBM Alpha Signal Pipeline.**
Loads the Qlib-formatted data pickle produced by `prepare_qlib_data.py`, constructs a `DataHandlerLP` with Fillna and DropnaLabel processors, automatically splits dates into train/test segments (train to second-last date, test on last two dates), trains a LightGBM gradient-boosting model for 1000 rounds, generates next-day return predictions, and saves them to `predictions.csv`.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `qlib` | `import qlib` | Quantitative research library initialization |
| `qlib.config` | `REG_CN` | Region configuration (China region used as structural template) |
| `qlib.data.dataset.loader` | `StaticDataLoader` | In-memory data loader |
| `qlib.data.dataset.handler` | `DataHandlerLP` | Feature processing pipeline |
| `qlib.data.dataset` | `DatasetH` | Segmented dataset |
| `qlib.contrib.model.gbdt` | `LGBModel` | LightGBM model |
| `pandas` | `import pandas as pd` | DataFrame handling |
| `os` | stdlib | Path construction |

### Configuration

```python
provider_uri = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data"
data_path    = <provider_uri>/formatted/data.pkl
```

Qlib is initialized with `REG_CN` (China region) for structural compatibility, not because the data is Chinese.

### Functions

---

#### `to_iso`

```python
def to_iso(val) -> str
```

**Parameters:**
- `val` — a datetime-like value.

**Returns:** ISO date string (`"YYYY-MM-DD"`) if `val` has a `.date()` method, otherwise `str(val)`.

**Behavior:** Used to convert min/max datetime index values to handler date bounds.

---

### Module-Level Pipeline (not wrapped in a function)

The entire pipeline executes at module level:

1. **Qlib init:** `qlib.init(provider_uri=provider_uri, region=REG_CN)`
2. **Load data:** `pd.read_pickle(data_path)` — expects a DataFrame with a `(datetime, instrument)` MultiIndex.
3. **DateTime dtype fix:** If the `datetime` index level is not already `datetime64`, converts it.
4. **MultiIndex column construction:** If the DataFrame columns are not already a MultiIndex with `feature`/`label` levels:
   - Wraps all existing columns under `feature` level.
   - Creates a next-day return label: `close.pct_change().shift(-1)` wrapped under the `label` level.
   - Concatenates feature and label DataFrames.
5. **DataHandlerLP construction:**
   - `infer_processors`: `[{"class": "Fillna", "kwargs": {"fields_group": "feature"}}]`
   - `learn_processors`: `[{"class": "DropnaLabel", "kwargs": {}}]`
   - `process_type`: `"append"`
6. **Auto-segment dates:**
   ```python
   train = (dates[0],  dates[-2])   # all dates except last
   test  = (dates[-2], dates[-1])   # second-to-last and last date
   ```
   Fallback: if fewer than 3 unique dates, both segments use `dates[0]`.
7. **DatasetH creation:** `DatasetH(handler=handler, segments=segments)`
8. **LightGBM training:** `model = LGBModel(); model.fit(dataset)` — 1000 boosting rounds, L2 loss.
9. **Prediction:** `preds = model.predict(dataset)` — shape `(n_test_rows,)`, values are predicted next-day relative returns.
10. **Save:** `preds.to_csv(<provider_uri>/predictions.csv)`

**Files read:** `qlib_data/formatted/data.pkl`
**Files written:** `qlib_data/predictions.csv`

---

## 9. `Module_2_Technical_Analysis/prepare_qlib_data.py`

### Role and Phase

**Qlib data formatting — prerequisite for `pipeline_alpha.py`.**
Converts the TA analysis CSV (output of `ta_analysis.py`) into Qlib's required pickle format: a DataFrame with a `(datetime, instrument)` MultiIndex, sorted ascending.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `pandas` | `import pandas as pd` | CSV reading, DataFrame transformation, pickle serialization |
| `os` | stdlib | Directory creation |

### Configuration Constants

```python
CSV_PATH       = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data/formatted/ta_analysis_detailed.csv"
QLIB_OUTPUT_DIR = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data/formatted"
OUTPUT_FILE    = <QLIB_OUTPUT_DIR>/data.pkl
```

Note: The hardcoded CSV path points to a copy of `ta_analysis_detailed.csv` placed in `qlib_data/formatted/`, not the original output location (`Module_2_Technical_Analysis/ta_analysis_detailed.csv`). Manual copying is required between these runs.

### Functions

---

#### `convert_to_qlib_format`

```python
def convert_to_qlib_format() -> None
```

**Parameters:** none.

**Returns:** none (side-effect: writes a `.pkl` file).

**Behavior:**
1. Reads `CSV_PATH` with `pd.read_csv`.
2. Drops entirely empty rows with `df.dropna(how="all")`.
3. Ensures a date column exists (`"date"`, `"datetime"`, or `"Date"`). Raises `ValueError` if none found.
4. Renames `"ticker"` → `"instrument"` if present.
5. Renames the date column to `"datetime"`.
6. Converts `"datetime"` to `datetime64` with `pd.to_datetime`.
7. Sets the MultiIndex: `df.set_index(["datetime", "instrument"]).sort_index()`.
8. Creates `QLIB_OUTPUT_DIR` if needed.
9. Serializes with `df.to_pickle(OUTPUT_FILE)`.

**Files read:** `qlib_data/formatted/ta_analysis_detailed.csv`
**Files written:** `qlib_data/formatted/data.pkl`

---

## 10. `Module_2_Technical_Analysis/phase_4_backtrader.py`

### Role and Phase

**Phase 9 — Backtesting Engine.**
The core simulation layer. Reads the TA signal CSV, downloads full OHLCV history for all tickers in the signal universe, recomputes RSI/MACD/SMA/ATR indicators for validation, feeds data into a Backtrader `Cerebro` instance, runs either the improved long-only strategy (`ImprovedLongOnlyStrategy`) or the legacy long/short strategy (`MultiTickerSignalStrategy`), computes a full suite of performance metrics (CAGR, Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, expectancy, time in market, average bars held), and writes equity curve, trade log, and summary metrics JSON.

The engine supports configuration via JSON file (`results_run/backtest_config.json`) that overrides CLI arguments, enabling reproducible runs without command-line juggling.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `backtrader` | `import backtrader as bt` | Strategy execution engine |
| `yfinance` | `import yfinance as yf` | OHLCV history download |
| `pandas` | `import pandas as pd` | DataFrames and time series |
| `numpy` | `import numpy as np` | Numerical operations |
| `argparse`, `json`, `os`, `math`, `pathlib` | stdlib | Configuration, I/O, math |
| `dataclasses` | `@dataclass` | Typed configuration and metrics containers |

### Global Configuration Defaults

```python
DEFAULT_INITIAL_CASH: float = 100_000.0
DEFAULT_MAX_POSITIONS: int  = 10
DEFAULT_COMMISSION: float   = 0.0005      # 5 basis points per side
DEFAULT_SLIPPAGE_PCT: float = 0.0005      # 5 basis points
DEFAULT_RISK_FREE: float    = 0.0
MIN_BARS_WARMUP: int        = 220         # bars required before SMA200 is valid

# Indicator periods
RSI_PERIOD: int    = 14
MACD_FAST: int     = 12
MACD_SLOW: int     = 26
MACD_SIGNAL: int   = 9
SMA_SHORT: int     = 50
SMA_LONG: int      = 200
ATR_PERIOD: int    = 14

MAX_PORTFOLIO_DRAWDOWN: float = 0.35      # 35% portfolio-level hard stop
```

### Column Alias Map

```python
COLUMN_ALIASES = {
    'MACD': 'macd',
    'MACD_Signal': 'macd_signal',
    'macd_signal_line': 'macd_signal',
    'macd_sig': 'macd_signal_flag',
    'macd_signal': 'macd_signal_flag',
    'RSI': 'rsi',
    'SMA50': 'sma_50',
    'SMA200': 'sma_200',
    'rsi_sig': 'rsi_signal',
    'trend_sig': 'trend_signal',
    'Ticker': 'ticker',
    'SYMBOL': 'ticker',
    'symbol': 'ticker',
    'DATE': 'Date',
    'date': 'Date',
    'timestamp': 'Date',
}
```

Applied by `normalize_columns` to handle CSV column naming variants from different upstream sources.

### Functions

---

#### `ensure_dir`

```python
def ensure_dir(path: str) -> None
```

Creates `path` and all parents with `os.makedirs(path, exist_ok=True)`.

---

#### `log`

```python
def log(msg: str) -> None
```

Prints `msg` with `flush=True` for real-time output in long-running backtest runs.

---

#### `to_float_scalar`

```python
def to_float_scalar(x: Any, default: float = 0.0) -> float
```

**Purpose:** Safe coercion of Pandas/NumPy scalars and Series objects to Python `float`. Handles: `pd.Series` (takes first element), `np.generic`/`np.number` (via `.item()`), and anything else via `float(x)`. Returns `default` on any exception.

---

#### `to_int_scalar`

```python
def to_int_scalar(x: Any, default: int = 0) -> int
```

Same as `to_float_scalar` but coerces to `int`. Used for signal values (-1, 0, 1) and position sizes.

---

#### `normalize_columns`

```python
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame
```

**Parameters:** A DataFrame with potentially variant column names.

**Returns:** The same DataFrame with columns renamed per `COLUMN_ALIASES`. All column names are coerced to `str`. Unrecognized columns are left unchanged.

---

#### `load_signals`

```python
def load_signals(signals_csv: str) -> Dict[str, pd.DataFrame]
```

**Parameters:**
- `signals_csv` — absolute path to the signal CSV (e.g., `ta_analysis_detailed.csv`).

**Returns:** A dict mapping ticker symbols (str) to DatetimeIndex-indexed DataFrames of their signals. Each DataFrame has at minimum columns: `rsi_signal`, `macd_signal_flag`, `trend_signal` (defaulting to 0 if absent in source CSV).

**Behavior:**
1. Reads CSV; applies `normalize_columns`.
2. Validates presence of `"Date"` and `"ticker"` columns; raises `ValueError` if absent.
3. Converts `"Date"` to `datetime64`.
4. Ensures `rsi_signal`, `macd_signal_flag`, `trend_signal` columns exist (fills with 0 if missing).
5. Sorts by `["ticker", "Date"]`.
6. Groups by ticker; for each group, sets `"Date"` as index.
7. Returns `{ticker_str: group_df}`.

**Files read:** the signals CSV path argument.

---

#### `ta_validate`

```python
def ta_validate(price_df: pd.DataFrame) -> pd.DataFrame
```

**Parameters:**
- `price_df` — a DataFrame with OHLCV columns (`Open`, `High`, `Low`, `Close`, `Volume`) indexed by date.

**Returns:** The same DataFrame with appended recalculation columns:

| Column | Formula |
|--------|---------|
| `rsi_recalc` | Wilder RSI(14) via EWM: `100 - 100/(1+RS)`, where `RS = gain_ewm / loss_ewm`, `alpha=1/14` |
| `macd_recalc` | `EMA(close, 12) - EMA(close, 26)` |
| `macd_signal_recalc` | `EMA(macd_recalc, 9)` |
| `sma50_recalc` | `close.rolling(50).mean()` |
| `sma200_recalc` | `close.rolling(200).mean()` |
| `atr_recalc` | Wilder ATR(14): `EWM(TR, span=14)` where `TR = max(H-L, |H-prevC|, |L-prevC|)` |
| `rsi_signal_recalc` | 1 if `rsi_recalc < 30`, -1 if `> 70`, else 0 |
| `macd_signal_flag_recalc` | 1 if `macd_recalc > macd_signal_recalc`, -1 if `<`, else 0 |
| `trend_signal_recalc` | 1 if `sma50 > sma200`, -1 if `<`, else 0 |

**RSI formula (Wilder EWM, lines 228-233):**
```python
delta = close.diff()
up    = delta.clip(lower=0.0)
down  = -delta.clip(upper=0.0)
gain  = up.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
loss  = down.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
rs    = gain / loss.replace(0, np.nan)
rsi   = 100 - (100 / (1 + rs))
```

**ATR formula (lines 248-255):**
```python
tr = max(|High - Low|, |High - prev_Close|, |Low - prev_Close|)
atr = tr.ewm(span=ATR_PERIOD, adjust=False).mean()
```

**Behavior notes:** Handles MultiIndex columns defensively by flattening to level-0. Validates required OHLCV columns; raises `ValueError` if any are missing.

---

### Class: `PandasDataAdj`

```python
class PandasDataAdj(bt.feeds.PandasData)
```

A Backtrader data feed subclass that maps standard OHLCV column names to Backtrader line names:

```python
params = (
    ('datetime', None),    # from DataFrame index
    ('open',    'Open'),
    ('high',    'High'),
    ('low',     'Low'),
    ('close',   'Close'),
    ('volume',  'Volume'),
    ('openinterest', -1),  # not used
)
```

---

### Dataclass: `StrategyConfig`

```python
@dataclass
class StrategyConfig:
    max_positions:   int   = 10
    hard_dd_stop:    float = 0.20     # 20% portfolio drawdown halt
    risk_free:       float = 0.0
    min_align:       int   = 2        # 2 of 3 signals must agree
    use_recalc:      bool  = True     # use recomputed indicators
    min_price:       float = 5.0      # skip stocks below $5
    min_volume:      int   = 200_000  # skip stocks below 200k avg volume
    risk_pct:        float = 0.015    # 1.5% of portfolio equity risked per trade
    atr_stop_mult:   float = 2.0      # initial stop = entry - 2×ATR
    atr_trail_mult:  float = 2.5      # trailing stop = peak - 2.5×ATR
    long_only:       bool  = True     # no short selling
    trend_filter:    bool  = True     # only enter above SMA200
```

---

### Class: `ImprovedLongOnlyStrategy`

```python
class ImprovedLongOnlyStrategy(bt.Strategy)
```

**The primary production strategy.** Long-only, ATR-risk-sized, with trailing stop and trend filter.

**params:**
- `signals_map` — `Dict[str, pd.DataFrame]` keyed by ticker.
- `config` — a `StrategyConfig` instance.
- `final_date` — the last date of the signal CSV (triggers forced liquidation).

**State tracking:**
- `equity_curve` — list of `(date, portfolio_value)` tuples.
- `days_in_market` — count of calendar days with at least one open position.
- `max_equity_seen` — running maximum portfolio value (for drawdown calculation).
- `hard_stop_triggered` — boolean; prevents re-entry after drawdown halt.
- `open_info` — dict of open position metadata keyed by ticker.
- `trades_log` — list of closed trade dicts.
- `_peak_since_entry` — dict of per-ticker highest close since entry (trailing stop reference).

#### `__init__`

Initializes all state. Sets `max_equity_seen` from `broker.getvalue()` at construction time.

---

#### `_today_signals`

```python
def _today_signals(self, tkr: str, dt: pd.Timestamp) -> Tuple[int, int, int]
```

**Returns:** `(rsi_signal, macd_signal_flag, trend_signal)` for ticker `tkr` on date `dt`. Returns `(0, 0, 0)` if the ticker or date is not found. Prefers `*_recalc` columns when `use_recalc=True`.

---

#### `_get_atr`

```python
def _get_atr(self, tkr: str, dt: pd.Timestamp) -> float
```

**Returns:** ATR value for `tkr` on `dt` from the `atr_recalc` column of `signals_map[tkr]`. Returns `0.0` if unavailable, non-finite, or zero.

---

#### `_get_sma200`

```python
def _get_sma200(self, tkr: str, dt: pd.Timestamp) -> float
```

**Returns:** SMA200 value. Checks `sma200_recalc` first, then `sma_200`. Returns `0.0` if unavailable.

---

#### `_long_vote`

```python
def _long_vote(self, sigs: Tuple[int, int, int]) -> bool
```

**Returns:** `True` if at least `min_align` of the three signals equal `+1` (bullish).

```
bullish = sum(s == 1 for s in sigs)
return bullish >= cfg.min_align
```

---

#### `_exit_vote`

```python
def _exit_vote(self, sigs: Tuple[int, int, int]) -> bool
```

**Returns:** `True` if at least `min_align` of the three signals equal `-1` (bearish) — triggers position exit.

---

#### `_open_positions_count`

```python
def _open_positions_count(self) -> int
```

**Returns:** Count of data feeds with non-zero position size.

---

#### `_risk_sized_shares`

```python
def _risk_sized_shares(self, data: bt.feeds.PandasData, tkr: str, dt: pd.Timestamp) -> int
```

**Returns:** Number of shares to buy, sized so that a `2×ATR` adverse move equals `risk_pct` of portfolio.

**ATR-based sizing formula:**
```
risk_dollars   = equity × risk_pct              # e.g., $100,000 × 0.015 = $1,500
stop_distance  = ATR × atr_stop_mult            # e.g., ATR × 2.0
shares         = int(risk_dollars / stop_distance)

# Fallback if ATR is zero:
stop_distance  = price × 0.05                   # 5% of price

# Hard cap: no single position > 25% of portfolio
max_shares     = int((equity × 0.25) / price)
shares         = max(0, min(shares, max_shares))
```

---

#### `next`

Called by Backtrader once per bar. Core execution logic:

1. Appends `(current_date, portfolio_value)` to `equity_curve`.
2. Increments `days_in_market` if any position is open.
3. Updates `max_equity_seen`; computes rolling drawdown:
   ```
   dd = 1 - (pv / max_equity_seen)
   ```
4. If `dd >= hard_dd_stop (20%)` and `hard_stop_triggered` is False: closes all positions and sets `hard_stop_triggered = True`.
5. For each data feed:
   - Skips if no new bar since last check.
   - Liquidates on `final_date`.
   - Skips all processing if `hard_stop_triggered`.
   - Applies `min_price` and `min_volume` filters (closes existing position if ticker falls below filter).
   - **If long position exists:**
     - Updates trailing stop peak: `_peak_since_entry[ticker] = max(prev_peak, close_px)`.
     - ATR trailing stop check: if `close_px < peak - ATR × atr_trail_mult (2.5)`, closes position.
     - Signal exit: if `_exit_vote` is True, closes position.
   - **If no position:**
     - Checks `_open_positions_count() < max_positions`.
     - Checks `_long_vote` returns True (at least 2 of 3 signals bullish).
     - Trend filter: requires `close_px > SMA200`.
     - Sizes via `_risk_sized_shares`; calls `self.buy(data=data, size=size)`.

---

#### `notify_order`

```python
def notify_order(self, order: bt.Order) -> None
```

No-op override (order confirmations are not logged individually).

---

#### `notify_trade`

```python
def notify_trade(self, trade: bt.Trade) -> None
```

**On trade open:** Stores `{entry_date, entry_price, size, side: "Long"}` in `open_info[ticker]`.

**On trade close:** Computes and appends to `trades_log`:
```python
{
    "ticker":      str,
    "side":        "Long",
    "entry_date":  "YYYY-MM-DD",
    "exit_date":   "YYYY-MM-DD",
    "entry_price": float (6 decimals),
    "exit_price":  float (6 decimals) | null,
    "pnl":         float (2 decimals),
    "bars_held":   int,
    "pnl_pct":     float (2 decimals) | null,
}
```

Exit price formula: `exit_price = entry_price + (pnl / size)`.

PnL% formula: `pnl_pct = (pnl / (entry_price × abs(size))) × 100`.

---

### Class: `MultiTickerSignalStrategy`

```python
class MultiTickerSignalStrategy(bt.Strategy)
```

**Legacy long/short strategy — kept for backwards compatibility.** Used automatically when `long_only=False`.

Key differences from `ImprovedLongOnlyStrategy`:
- Supports short selling: `sell(data=data, size=size)` when `vote == -1`.
- Uses equal-weight position sizing (portfolio value divided by `max_positions`).
- No ATR trailing stop; exits only on signal vote reversal.
- No trend filter (no SMA200 entry guard).
- `_aligned_vote` requires zero opposing signals (stricter): `pos >= min_align AND neg == 0` for long; `neg >= min_align AND pos == 0` for short.

#### `_aligned_vote`

```python
def _aligned_vote(self, sigs: Tuple[int, int, int]) -> int
```

**Returns:** `+1` for long vote (bullish majority, zero bearish), `-1` for short vote (bearish majority, zero bullish), `0` for hold. Stricter than `ImprovedLongOnlyStrategy._long_vote`.

#### `_target_shares`

```python
def _target_shares(self, data: bt.feeds.PandasData) -> int
```

Equal-weight sizing formula:
```
alloc_value = portfolio_equity / max_positions
shares      = int(alloc_value // close_price)
```

---

### Dataclass: `Metrics`

```python
@dataclass
class Metrics:
    sharpe:               float
    sortino:              float
    calmar:               float
    max_drawdown_pct:     float
    max_dd_duration_days: int
    time_in_market_pct:   float
    cagr:                 float
    win_rate:             float = 0.0
    profit_factor:        float = 0.0
    expectancy:           float = 0.0
    avg_bars_held:        float = 0.0
    total_trades:         int   = 0
```

---

#### `compute_extended_trade_metrics`

```python
def compute_extended_trade_metrics(trades_df: pd.DataFrame) -> dict
```

**Parameters:** A DataFrame with at least a `"pnl"` column and optionally `"bars_held"`.

**Returns:** A dict with keys `win_rate`, `profit_factor`, `expectancy`, `avg_bars_held`, `total_trades`.

**Formulas:**

```
win_rate      = count(pnl > 0) / total_trades          (then × 100 for %)
gross_profit  = sum(pnl > 0)
gross_loss    = abs(sum(pnl < 0))
profit_factor = gross_profit / gross_loss               (inf if gross_loss == 0)
avg_win       = mean(pnl > 0)
avg_loss      = abs(mean(pnl < 0))
expectancy    = (win_rate × avg_win) - ((1 - win_rate) × avg_loss)
avg_bars_held = mean(bars_held)
```

---

#### `compute_metrics`

```python
def compute_metrics(
    equity_df: pd.DataFrame,
    days_in_market: int,
    trades_df: Optional[pd.DataFrame] = None
) -> Metrics
```

**Parameters:**
- `equity_df` — DataFrame with `"date"` and `"equity"` columns.
- `days_in_market` — int count of days with an open position.
- `trades_df` — optional trade log DataFrame.

**Returns:** A populated `Metrics` dataclass.

**All formulas:**

```
# Daily returns
ret = equity.pct_change().fillna(0)

# Sharpe (annualized, daily returns, no risk-free adjustment by default)
sharpe = (mean(ret) / std(ret, ddof=0)) × sqrt(252)

# Sortino (uses only negative return days in denominator)
neg    = ret[ret < 0]
ds     = std(neg, ddof=0)
sortino = (mean(ret) / ds) × sqrt(252)        (inf if ds == 0)

# CAGR
years  = (end_date - start_date).days / 365.0
cagr   = (end_equity / start_equity) ^ (1/years) - 1

# Max Drawdown
roll_max      = equity.cummax()
dd_series     = equity / roll_max - 1.0
max_dd_pct    = abs(dd_series.min())           (as percentage)

# Max Drawdown Duration (consecutive days below rolling max)
max_dur = longest run of dd_series < 0

# Calmar
calmar = cagr / max_dd_pct                     (inf if max_dd_pct == 0)

# Time in Market
time_in_market_pct = (days_in_market / len(equity_df)) × 100
```

All metrics are rounded:
- `sharpe`, `sortino`, `calmar`: 4 decimal places
- `max_drawdown_pct`, `cagr`, `time_in_market_pct`: 2 decimal places
- Trade metrics: 1–2 decimal places

---

#### `adjust_ohlc_with_adjclose`

```python
def adjust_ohlc_with_adjclose(df: pd.DataFrame) -> pd.DataFrame
```

Applies split and dividend adjustment to OHLC prices using the `Adj Close` column from yfinance:

```
factor = Adj Close / Close
Open, High, Low, Close *= factor
```

Drops the `Adj Close` column after adjustment. Returns `df` unchanged if `"Adj Close"` is not present.

---

#### `fetch_history`

```python
def fetch_history(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame
```

**Parameters:**
- `ticker` — ticker symbol.
- `start`, `end` — date range.

**Returns:** Adjusted OHLCV DataFrame with a `datetime64` index, sorted ascending. Returns an empty DataFrame if yfinance returns nothing.

**Behavior:** Calls `yf.download(..., auto_adjust=False)` to get raw splits/dividends data, then applies `adjust_ohlc_with_adjclose` manually. Selects only `["Open", "High", "Low", "Close", "Volume"]`.

---

#### `build_universe`

```python
def build_universe(signals_map: Dict[str, pd.DataFrame]) -> List[str]
```

**Returns:** Sorted list of ticker strings from the `signals_map` keys (all tickers in the signal CSV).

---

#### `run_backtest`

```python
def run_backtest(
    signals_csv: str,
    out_dir: str,
    initial_cash: float = 100_000.0,
    commission: float = 0.0005,
    slippage_pct: float = 0.0005,
    max_positions: int = 10,
    risk_free: float = 0.0,
    dd_stop: float = 0.20,
    min_align: int = 2,
    use_recalc: bool = True,
    verbose_mismatch: bool = True,
    min_price: float = 5.0,
    min_volume: int = 200_000,
    long_only: bool = True,
    trend_filter: bool = True,
    risk_pct: float = 0.015,
) -> Tuple[pd.DataFrame, pd.DataFrame, Metrics]
```

**Returns:** `(equity_df, trades_df, metrics)` where `equity_df` has columns `["date", "equity"]`, `trades_df` has all trade log fields, and `metrics` is a `Metrics` dataclass.

**Behavior:**
1. Creates `out_dir`.
2. Loads and normalizes signals with `load_signals(signals_csv)`.
3. Determines global date range from all signal DataFrames.
4. Sets `hist_start = start_dt - max(365, SMA_LONG+20) days` to ensure SMA200 warm-up.
5. For each ticker: downloads OHLCV, warns if fewer than `MIN_BARS_WARMUP (220)` warm-up bars, runs `ta_validate`, trims to `[start_dt:]`, merges recalculated signals back into `signals_map[tkr]` at matching dates.
6. Optionally logs signal mismatches between CSV-provided and recalculated values if `verbose_mismatch=True`.
7. Configures Backtrader `Cerebro`: sets cash, commission, percent slippage.
8. Adds one `PandasDataAdj` feed per ticker.
9. Selects `ImprovedLongOnlyStrategy` (if `long_only=True`) or `MultiTickerSignalStrategy`.
10. Runs `cerebro.run(maxcpus=1)`.
11. Trims equity curve to `[start_dt:]`, computes metrics.
12. Saves:
    - `<out_dir>/portfolio_equity_curve.csv`
    - `<out_dir>/trade_log.csv`
    - `<out_dir>/summary_metrics.json`

**Files read:** signals CSV, yfinance download (network).
**Files written:**
- `results_run/portfolio_equity_curve.csv`
- `results_run/trade_log.csv`
- `results_run/summary_metrics.json`

---

#### `load_json_config`

```python
def load_json_config(config_path: str) -> Dict[str, Any]
```

**Returns:** Parsed JSON dict from `config_path`, or `{}` if file does not exist or is malformed.

**Default config path:** `Module_2_Technical_Analysis/results_run/backtest_config.json`

---

#### `parse_args`

```python
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace
```

Defines all CLI arguments with defaults matching the strategy defaults. Boolean arguments accept `"1"`, `"true"`, `"yes"` (case-insensitive). Key arguments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--signals_csv` | str | None | Required path to TA CSV |
| `--out_dir` | str | `results_run_<timestamp>` | Output directory |
| `--initial_cash` | float | 100,000 | Starting capital |
| `--commission` | float | 0.0005 | Brokerage commission fraction |
| `--slippage_pct` | float | 0.0005 | Slippage fraction |
| `--max_positions` | int | 10 | Maximum concurrent positions |
| `--dd_stop` | float | 0.35 | Portfolio drawdown halt level |
| `--min_align` | int | 2 | Min signals to agree for entry/exit |
| `--use_recalc` | bool | True | Use recomputed indicators |
| `--min_price` | float | 5.0 | Skip below this price |
| `--min_volume` | int | 200,000 | Skip below this volume |
| `--long_only` | bool | True | Disable short selling |
| `--trend_filter` | bool | True | Require Close > SMA200 for entry |
| `--risk_pct` | float | 0.015 | Portfolio risk fraction per trade |

---

#### `overlay_args_with_json`

```python
def overlay_args_with_json(args: argparse.Namespace, json_cfg: Dict[str, Any]) -> argparse.Namespace
```

**Behavior:** For each key in `json_cfg` that matches an attribute of `args`, calls `setattr(args, k, v)`. JSON config values override CLI defaults; this allows a stable JSON config to act as persistent settings without repeated CLI flags.

---

#### `copy_config_to_outdir`

```python
def copy_config_to_outdir(config_source: str, out_dir: str) -> None
```

Copies the JSON config file to `<out_dir>/config_used.json` for reproducibility tracking. Silently skips if the source does not exist.

---

#### `main` (backtrader)

```python
def main(argv: Optional[List[str]] = None) -> None
```

**Execution sequence:**
1. `parse_args(argv)` — CLI defaults.
2. `load_json_config(DEFAULT_JSON_CONFIG)` — JSON override.
3. `overlay_args_with_json` — merge.
4. Validate `signals_csv` is set; exit with usage instructions if not.
5. `ensure_dir(out_dir)`.
6. `copy_config_to_outdir`.
7. Log all run parameters.
8. `run_backtest(...)`.
9. Print full performance summary table to stdout.

**Files written:** All files from `run_backtest` plus `config_used.json`.

---

## 11. `validate_env.py`

### Role and Phase

**Environment / pre-flight validation script.** Not part of the data pipeline. Run before any pipeline execution to verify that all required API keys are set, all critical Python packages are importable, all key pipeline script files exist, and all required output directories exist. Optionally tests live OpenAI API connectivity with `--test-api`.

### External Libraries

| Library | Import | Purpose |
|---------|--------|---------|
| `python-dotenv` | `from dotenv import load_dotenv` | `.env` file loading |
| `openai` | `from openai import OpenAI` | API connectivity test |
| `importlib.metadata` | stdlib | Checks `sentence-transformers` version without importing it (avoids torch segfault) |
| `argparse`, `os`, `sys`, `pathlib` | stdlib | CLI argument parsing, env access, exit codes |

> **Segfault mitigation:** `sentence-transformers` import is deliberately checked via `importlib.metadata.version("sentence-transformers")` rather than `__import__("sentence_transformers")` (line 110-115). This avoids loading `torch` at import time, which causes a macOS segfault on `torch==2.2.2` when `SentenceTransformer()` is instantiated.

### Functions

---

#### `load_env`

```python
def load_env() -> None
```

Calls `load_dotenv(BASE_DIR / ".env")` using python-dotenv. If python-dotenv is not installed, prints a warning and continues (OS environment variables will still be read).

---

#### `check`

```python
def check(label: str, passed: bool, detail: str = "") -> bool
```

**Parameters:**
- `label` — the check name to display.
- `passed` — True/False result.
- `detail` — optional description string.

**Returns:** `passed` (allows chaining in `if not check(...)`).

**Behavior:** Prints `"  ✅  {label}  — {detail}"` or `"  ❌  {label}  — {detail}"`.

---

#### `section`

```python
def section(title: str) -> None
```

Prints a formatted section header with a 55-character dashed border. Used to visually separate check categories.

---

#### `validate_api_keys`

```python
def validate_api_keys() -> list[str]
```

**Returns:** A list of required API key names that are missing or contain placeholder values.

**Keys checked:**

| Key | Required? | Purpose |
|-----|-----------|---------|
| `OPENAI_API_KEY` | Yes | GPT summarization, Chef GPT (Phases 5, 11) |
| `FINNHUB_API_KEY` | Yes | News scraping (Phase 2) |
| `SEC_API_KEY` | No | SEC Edgar filings |
| `QUANDL_API_KEY` | No | Macro data (Phase 6) |
| `QUIVERQUANT_API_KEY` | Yes | Political intelligence (Phase 6.5) |
| `FRED_API_KEY` | No | FRED macro data (Phase 13) |

A key is considered "set" if: non-empty, does not equal `"your_{key_lower}_here"`, and does not contain `"your_"`.

---

#### `validate_imports`

```python
def validate_imports() -> list[str]
```

**Returns:** A list of `"pip install <package>"` strings for required packages that fail to import.

**Packages checked:**

| Module | Package | Required? | Purpose |
|--------|---------|-----------|---------|
| `dotenv` | `python-dotenv` | Yes | API key management |
| `openai` | `openai` | Yes | GPT summarization |
| `streamlit` | `streamlit` | Yes | Dashboard |
| `pandas` | `pandas` | Yes | Data handling |
| `numpy` | `numpy` | Yes | Numerical operations |
| `yfinance` | `yfinance` | Yes | Market data |
| `feedparser` | `feedparser` | Yes | RSS news scraping |
| `requests` | `requests` | Yes | HTTP requests |
| `vaderSentiment` | `vaderSentiment` | No | Sentiment analysis |
| `sklearn` | `scikit-learn` | No | Clustering algorithms |
| `faiss` | `faiss-cpu` | No | Vector search |
| `backtrader` | `backtrader` | No | Backtesting engine |
| `fredapi` | `fredapi` | No | FRED macro data |
| `plotly` | `plotly` | No | Charts |
| `sentence-transformers` | (metadata only) | No | Article embeddings — checked via `importlib.metadata`, not `__import__` |

---

#### `validate_files`

```python
def validate_files() -> list[str]
```

**Returns:** A list of relative path strings for required files that are missing.

**Files checked:**

| File | Required? | Purpose |
|------|-----------|---------|
| `phase3_extraction.py` | Yes | Phase 3 — Data extraction |
| `phase4_clustering.py` | Yes | Phase 4 — Article clustering |
| `recession_signals.py` | Yes | Phase 13 — Recession signals |
| `historical_correlation.py` | Yes | Phase 7 — Historical correlation |
| `opportunity_score.py` | Yes | Phase 8.9 — Opportunity scoring |
| `chef_gpt.py` | Yes | Phase 11 — Chef GPT synthesis |
| `controller.py` | Yes | Phase 12 — Pipeline controller |
| `dashboard/app.py` | Yes | Streamlit dashboard |
| `agents/security_audit.py` | No | Security audit agent |
| `agents/data_quality.py` | No | Data quality agent |
| `agents/verification_runner.py` | No | Verification runner |
| `.env` | Yes | API keys config |
| `requirements.txt` | Yes | Package manifest |

---

#### `validate_directories`

```python
def validate_directories() -> None
```

**Behavior:** Checks (and creates if missing) three directories:
- `news_output/`
- `Module_2_Technical_Analysis/results_run/`
- `agents/`

All three are reported as passing regardless of whether they pre-existed.

---

#### `test_openai_api`

```python
def test_openai_api() -> bool
```

**Returns:** `True` if the OpenAI API responds successfully; `False` if the key is absent or any exception occurs.

**Behavior:** Sends a minimal chat completion request:
```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say OK"}],
    max_tokens=5,
)
```
Checks `bool(response.choices[0].message.content)`. Only invoked when `--test-api` is passed.

---

#### `main` (validate_env)

```python
def main() -> None
```

**Behavior:**
1. Parses `--test-api` flag.
2. Calls `load_env()`.
3. Runs all four validation sections in order: API keys, imports, files, directories.
4. If `--test-api`: calls `test_openai_api()`.
5. Exits with `sys.exit(0)` if all required checks passed, `sys.exit(1)` otherwise.
6. Prints actionable remediation instructions for each failure category.

---

## Appendix: Data Flow Summary

```
PDF Books
    ↓
economic_engine.py          → economic_knowledge_index.faiss
                               economic_knowledge_metadata.json
    ↓
clustered_summaries.json (Phase 4 clustering output — separate script)
    ↓
article_clustering.py (Phase 5 GPT summarization)
                            → clustered_articles_with_summaries.json
                               sector_summaries.json (partial)
    ↓
GPT_article_clustering_summary.py (Phase 4 sector overview)
                            → sector_summaries.json (full, 12-sentence overviews)
    ↓
Reasoning_Report.py (Phase 6 economic reasoning)
                            → economic_reasoning_summary.json
                               (bullish_sectors, bearish_sectors)
    ↓
ta_analysis.py (TA engine)
                            → ta_analysis_detailed.csv
                               raw_data/<ticker>.csv
    ↓
phase_3_signal.py (signal generation)
                            → signal_output_phase3.json
    ↓
prepare_qlib_data.py        → qlib_data/formatted/data.pkl
    ↓
pipeline_alpha.py (LightGBM)→ qlib_data/predictions.csv
    ↓
phase_4_backtrader.py (backtesting)
                            → results_run/portfolio_equity_curve.csv
                               results_run/trade_log.csv
                               results_run/summary_metrics.json
```
