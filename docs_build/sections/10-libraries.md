# Part 10 — Library & Dependency Inventory

This part lists every third-party library the platform depends on, what it is
used for, and any version pin and the reason for it. Two dependency sets exist:
the **pipeline** set (`requirements.txt`, installed into the legacy `tf_env`) and
the **backend** set (`server/requirements.txt`, installed into a clean
`server/.venv`). The two are deliberately kept separate so the lean web backend
does not drag in the heavy ML/quant stack.

## 10.1 Backend dependencies (`server/requirements.txt`)

Installed into a clean virtualenv (never reuse `tf_env`).

| Library | Pin | Purpose |
|---------|-----|---------|
| fastapi | 0.111.0 | The web framework: routing, dependency injection, request validation |
| uvicorn[standard] | 0.30.1 | ASGI server that runs the FastAPI app |
| bcrypt | 4.1.3 | Password hashing (slow by design; resists brute force) |
| PyJWT | 2.8.0 | Signed session tokens stored in the httpOnly cookie |
| python-dotenv | 1.0.1 | Loads secrets from `server/.env` (never committed) |

The backend otherwise relies on the Python **standard library** only: `sqlite3`
(user store), `hmac` (constant-time beta-key compare), `hashlib`, `datetime`,
`json`, `re`, `os`, `pathlib`, `zoneinfo` (market-hours), and `secrets`.

## 10.2 Pipeline dependencies (`requirements.txt`)

Grouped by role. Several pins are mandatory for macOS / Python 3.10 compatibility
(see 10.4).

### AI / LLM & embeddings
| Library | Pin | Purpose |
|---------|-----|---------|
| openai | >=1.0.0 | GPT calls for summarization, reasoning, and the Chef GPT briefing |
| langchain | 1.3.9 | LLM orchestration framework |
| langchain-community | >=0.3 | Community integrations (vector stores, loaders) |
| langchain-openai | >=0.2 | OpenAI provider for LangChain |
| tiktoken | (unpinned) | Token counting for prompt budgeting |
| sentence-transformers | 2.7.0 | Sentence embeddings for clustering / semantic search |
| transformers | 4.41.2 | Underlying model library for embeddings |
| torch | 2.2.2 | Tensor backend for transformers |
| faiss-cpu | (unpinned) | Vector index for the economic-reasoning knowledge base |

### Quant / technical analysis / backtesting
| Library | Pin | Purpose |
|---------|-----|---------|
| backtrader | (unpinned) | Backtesting engine (Phase 9) |
| QuantLib | (unpinned) | Quantitative finance math (Phase 8 metrics) |
| ta | (unpinned) | Technical-analysis indicators |
| scikit-learn | (unpinned) | Clustering (KMeans/Agglomerative), ML utilities |
| scipy | (unpinned) | Scientific computing used by the quant/stat code |
| numpy | <2 | Numerical arrays (pinned, see 10.4) |
| pandas | >=2.0.0 | Dataframes throughout the pipeline |

### Market & economic data
| Library | Pin | Purpose |
|---------|-----|---------|
| yfinance | (unpinned) | Yahoo Finance market data |
| fredapi | (unpinned) | FRED macroeconomic series (yield curve, etc.) |
| requests | (unpinned) | HTTP client for external APIs |
| feedparser | (unpinned) | RSS news ingestion |
| beautifulsoup4 | (unpinned) | HTML parsing/scraping |

### NLP / sentiment
| Library | Pin | Purpose |
|---------|-----|---------|
| vaderSentiment | (unpinned) | Lexicon sentiment scoring |
| (nltk) | (imported) | NLP utilities used in extraction |

### Delivery / visualization (legacy prototype)
| Library | Pin | Purpose |
|---------|-----|---------|
| streamlit | >=1.32.0 | The legacy `dashboard/app.py` prototype UI |
| plotly | >=5.0.0 | Charts in the Streamlit prototype |

### Validation, security & utilities
| Library | Pin | Purpose |
|---------|-----|---------|
| pydantic | >=2.0.0 | Schema validation for inter-module data contracts |
| validators | (unpinned) | Input sanitization for URLs, emails, tickers |
| ratelimit | (unpinned) | Decorator-based rate limiting on external API calls |
| python-dotenv | >=1.0.0 | Loads pipeline secrets from `.env` |
| tqdm | (unpinned) | Progress bars for long builds |

### Other third-party libraries seen in imports
| Library | Where | Purpose |
|---------|-------|---------|
| qlib | `Module_2_Technical_Analysis/` | Quant research data layer for TA/backtesting |
| fitz (PyMuPDF) | book/PDF ingestion | Reading economics PDFs into the knowledge base |
| ijson | bulk SEC ingestion | Streaming JSON parse of large filings |
| dulwich | `push_to_github.py` | Pure-Python git operations |

## 10.3 Standard-library usage (notable)

Across the pipeline the stdlib does much of the heavy lifting:
`json` (58 files), `pathlib` (50), `os` (28), `urllib` (25), `datetime` (24),
`typing` (19), `re` (18), `time` (14), plus `sys`, `collections`, `math`,
`argparse`, `concurrent.futures`, `threading`, `subprocess`, `gzip`, `zipfile`,
`csv`, `io`, `difflib`, `functools`, `itertools`, `dataclasses`, `logging`,
`ssl`, `hashlib`, `hmac`, `sqlite3`. `from __future__ import annotations` appears
in 51 files (forward-reference typing).

## 10.4 Version-pin rationale

The blueprint records hard pins for macOS / Python 3.10 stability:

- **numpy < 2** — required for compatibility with the torch 2.2.x ABI.
- **sentence-transformers == 2.7.0**, **transformers == 4.41.2**,
  **torch == 2.2.2** — this exact triple is the known-good combination on macOS
  Python 3.10. A documented constraint: `SentenceTransformer()` can **segfault**
  on macOS with torch 2.2.2 if the model is loaded at runtime; the economic
  engine therefore avoids loading the model live and instead keyword-scans FAISS
  metadata. Engineers reproducing the environment must honor these pins.

## 10.5 Frontend dependencies

**None.** The `webapp/` front end has **zero external or CDN dependencies**. It is
pure vanilla JavaScript, HTML, and CSS, all served locally. `index.html` loads
only three local scripts up front (`boot.js`, `auth_seed.js`, `auth.js`); every
other module is injected locally by `boot.js` after authentication. The logout
animation and all icons are hand-authored inline SVG — no icon library, no
framework (no React/Vue/jQuery), and no analytics or third-party trackers.

This is a deliberate security and performance choice: there is no supply-chain
surface in the browser bundle, nothing phones home, and the only code the browser
runs is code in this repository.

## 10.6 Security tooling (referenced by CI and the audit agent)

The CI security workflow and the static audit agent use: **bandit** (static
analysis), **safety** / **pip-audit** (dependency CVE scans), and
**detect-secrets** (pre-commit secret blocking). These are invoked as scanners
(see Parts 8 and 11) rather than imported as libraries.
