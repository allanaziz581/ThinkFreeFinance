# Part 8 — Python Verification Agent Layer

> **Source tree:** `agents/` (relative to repo root `ThinkFree-main/`)
> **Files covered:** `__init__.py`, `data_quality.py`, `security_audit.py`, `strategy_audit.py`, `verification_runner.py`

---

## Summary Table

| Agent | Module | Triggers After | Blocks On | Output Written |
|---|---|---|---|---|
| **DataQualityAgent** | `agents/data_quality.py` | Phase 2 (scraping) and Phase 3 (extraction) | Any `BLOCKER`-severity finding | `pipeline_audit.json` (via runner) |
| **SecurityAuditAgent** | `agents/security_audit.py` | Every pipeline execution | Any `CRITICAL` or `HIGH` finding | `pipeline_audit.json` (also writes directly) |
| **StrategyAuditAgent** | `agents/strategy_audit.py` | Phase 9 (backtesting) | Any `BLOCKER`-severity finding | `pipeline_audit.json` (via runner) |
| **VerificationRunner** | `agents/verification_runner.py` | Invoked by `controller.py` or directly | Any agent returning FAIL or ERROR | `pipeline_audit.json` (combined) |

---

## Package Root — `agents/__init__.py`

**File:** `agents/__init__.py` (line 1–2)

The package init is a single-line comment:

```python
# ThinkFree Finance — Verification Agent Layer
```

No imports, no `__all__`, no public API defined at the package level. All agents are imported directly by `verification_runner.py` using their module paths.

---

## DataQualityAgent — `agents/data_quality.py`

### Overview

**Pipeline checkpoint:** After Phase 2 (raw scraping) and Phase 3 (NLP extraction). Also validates Phase 4 (clustering), Phase 6 (economic reasoning), and Phase 13 (recession signals).

**What it checks:**

| Phase | Check Category | Severity Possible |
|---|---|---|
| Phase 2 | Missing title, empty title, missing URL, no content body, stale/unparseable timestamps | BLOCKER, WARN |
| Phase 3 | Null sentiment, missing compound score, zero data richness, no extracted entities, sort order | BLOCKER, WARN, INFO |
| Phase 4 | Empty clustering output, too few clusters, missing GICS sector, missing impact score | BLOCKER, WARN, INFO |
| Phase 6 | Missing economic reasoning file, missing required keys, thin summary | INFO, WARN |
| Phase 13 | Missing recession output, missing risk score, score out of 0–10 range | INFO, WARN |

**Pass/fail verdict logic:** FAIL if any finding has `severity == "BLOCKER"`. No blockers → PASS. Warnings do not block.

**Global threshold constant:**

```python
PASS_THRESHOLD = 0.80  # agents/data_quality.py:22
```

This constant is defined but its value (80%) is referenced conceptually in per-field checks — the actual blocking thresholds are implemented inline per field (e.g., `> 0.2` for missing title, `> 0.3` for missing URL, `> 0.5` for null sentiment).

**Files read:**

| File Path | Purpose |
|---|---|
| `news_output/articles_*.json` (most recent by sort) | Phase 2 raw articles |
| `news_output/enriched_news_sentiment.json` | Phase 3 enriched/extracted articles |
| `news_output/clustered_summaries.json` | Phase 4 clustered output |
| `news_output/economic_reasoning_summary.json` | Phase 6 economic reasoning |
| `recession_signals_output.json` (repo root) | Phase 13 recession signals |

**Files written:** None directly. Results are returned as a `dict` and written by `verification_runner.py` into `pipeline_audit.json`.

---

### `class QualityFinding`

**File:** `agents/data_quality.py`, lines 25–40

```python
class QualityFinding:
    def __init__(self, severity: str, phase: str, check: str, message: str, count: int = 1)
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `severity` | `str` | One of `"BLOCKER"`, `"WARN"`, `"INFO"` |
| `phase` | `str` | Pipeline phase label, e.g. `"phase2"`, `"phase3"`, `"phase6"` |
| `check` | `str` | Short machine-readable check ID, e.g. `"missing_title"`, `"null_sentiment"` |
| `message` | `str` | Human-readable description of the finding |
| `count` | `int` | Number of affected records (default `1`; `0` for structural/aggregate findings) |

**Instance attributes:** `self.severity`, `self.phase`, `self.check`, `self.message`, `self.count`

#### `QualityFinding.to_dict()`

```python
def to_dict(self) -> dict
```

Returns a flat dictionary with keys `severity`, `phase`, `check`, `message`, `count`. Used when serializing findings into the `pipeline_audit.json` output.

---

### `check_phase2_output(articles)`

**File:** `agents/data_quality.py`, lines 47–132

```python
def check_phase2_output(articles: list[dict]) -> list[QualityFinding]
```

**Purpose:** Validates the raw scraped article list produced by `phase2_data_scraping.py`.

**Parameters:** `articles` — list of raw article dicts.

**Returns:** List of `QualityFinding` objects.

**Step-by-step behavior:**

1. **Empty guard** (line 52–56): If `articles` is empty, immediately returns a single `BLOCKER` finding with check `"empty_output"`. No further checks run.

2. **Per-article field checks** (lines 63–73): Iterates all articles and counts:
   - `missing_title`: `art.get("title")` is falsy.
   - `empty_title`: title exists but `len(title) < 10`.
   - `missing_url`: neither `art.get("url")` nor `art.get("link")` is truthy.
   - `no_summary`: none of `summary`, `content`, or `description` fields present.

3. **Missing title threshold** (lines 77–82):
   - If `missing_title / total > 0.2` → `BLOCKER`
   - Otherwise → `WARN`

4. **Empty title** (lines 84–88): Any `empty_title > 0` → `WARN` (`"thin_title"`).

5. **Missing URL threshold** (lines 90–95):
   - If `missing_url / total > 0.3` → `BLOCKER`
   - Otherwise → `WARN`

6. **No content** (lines 97–101): Any `no_summary > 0` → `WARN` (`"no_content"`).

7. **Freshness check** (lines 103–131): Iterates articles, tries to parse `published`, `publishedAt`, or `datetime` field as ISO 8601 (with `Z` → `+00:00` substitution). Counts articles published within the last 48 hours.
   - If `fresh_count == 0` and articles exist → `WARN` (`"stale_data"`)
   - If `fresh_count < total * 0.5` → `WARN` (`"mostly_stale"`)

---

### `check_phase3_output(articles)`

**File:** `agents/data_quality.py`, lines 139–214

```python
def check_phase3_output(articles: list[dict]) -> list[QualityFinding]
```

**Purpose:** Validates enriched articles from `phase3_extraction.py`, which adds sentiment, entity extraction, and data richness scores.

**Parameters:** `articles` — list of enriched article dicts.

**Returns:** List of `QualityFinding` objects.

**Step-by-step behavior:**

1. **Empty guard** (lines 143–148): Empty list → single `BLOCKER` (`"empty_output"`), return immediately.

2. **Per-article checks** (lines 153–172): Iterates all articles counting:
   - `null_sentiment`: `art.get("sentiment")` is `None`, or it is a dict but `compound` key is absent or `None`.
   - `missing_compound`: `sentiment` is not a dict or lacks `"compound"`.
   - `zero_richness`: `art.get("data_richness_score")` is `None` or `0`.
   - `missing_entities`: `art.get("entities", {})` is empty or all entity lists are empty.

3. **Null sentiment threshold** (lines 174–179):
   - If `null_sentiment / total > 0.5` → `BLOCKER`
   - Otherwise → `WARN`

4. **Missing compound** (lines 181–184): Any → `WARN` (`"missing_compound"`).

5. **Low richness threshold** (lines 186–191):
   - If `zero_richness > total * 0.5` → `WARN` (`"low_richness"`).

6. **Low entity extraction threshold** (lines 193–199):
   - If `missing_entities > total * 0.7` → `INFO` (`"low_entity_extraction"`). Severity intentionally `INFO` because spaCy may not be installed.

7. **Sort order check** (lines 201–212): If `len(articles) >= 3`, samples the first 10 articles, extracts `abs(compound)` for each, and checks whether the list is already sorted descending. If not → `INFO` (`"not_sorted"`).

---

### `check_phase4_output(data)`

**File:** `agents/data_quality.py`, lines 221–268

```python
def check_phase4_output(data: dict) -> list[QualityFinding]
```

**Purpose:** Validates the clustered output dict from `phase4_clustering.py`.

**Parameters:** `data` — dict mapping cluster IDs to lists of article dicts.

**Returns:** List of `QualityFinding` objects.

**Step-by-step behavior:**

1. **Empty guard** (lines 226–231): Empty dict → `BLOCKER` (`"empty_output"`), return immediately.

2. **Cluster count check** (lines 233–238):
   - `total_clusters = len(data)`. If `< 2` → `WARN` (`"too_few_clusters"`). Expected 5+ clusters.
   - `total_articles = sum(len(v) for v in data.values() if isinstance(v, list))`.

3. **Per-article checks within clusters** (lines 240–250): Iterates each cluster's article list counting:
   - `no_sector`: `art.get("gics_sector")` is falsy.
   - `no_impact`: `art.get("impact_score") is None`.

4. **Missing sector threshold** (lines 252–256):
   - If `no_sector > total_articles * 0.3` → `WARN` (`"missing_sector"`).

5. **Missing impact threshold** (lines 258–262):
   - If `no_impact > total_articles * 0.3` → `WARN` (`"missing_impact"`).

6. **OK summary** (lines 263–267): Always appends an `INFO` (`"ok"`) finding with cluster and article counts.

---

### `check_economic_reasoning(data)`

**File:** `agents/data_quality.py`, lines 275–301

```python
def check_economic_reasoning(data: dict) -> list[QualityFinding]
```

**Purpose:** Validates Phase 6 economic reasoning output from `GPT_Economy/Reasoning_Report.py`.

**Parameters:** `data` — dict loaded from `economic_reasoning_summary.json`.

**Step-by-step behavior:**

1. **Not-generated guard** (lines 279–283): Empty dict → `INFO` (`"not_generated"`), return immediately. Soft failure — Phase 6 is optional.

2. **Required keys check** (lines 285–292): Checks for `"summary"`, `"bullish_sectors"`, `"bearish_sectors"`. Missing any → `WARN` with key-specific check name.

3. **Thin summary check** (lines 294–299): If `summary` is a string with `len < 50` → `WARN` (`"thin_summary"`).

---

### `check_recession_output(data)`

**File:** `agents/data_quality.py`, lines 308–331

```python
def check_recession_output(data: dict) -> list[QualityFinding]
```

**Purpose:** Validates Phase 13 recession signals output.

**Parameters:** `data` — dict loaded from `recession_signals_output.json`.

**Step-by-step behavior:**

1. **Not-generated guard** (lines 312–316): Empty dict → `INFO` (`"not_generated"`), return immediately.

2. **Score presence check** (lines 318–321): `data.get("recession_risk", {}).get("score")`. If `None` → `WARN` (`"missing_score"`).

3. **Score range check** (lines 323–328): If score exists but not in `[0, 10]` → `WARN` (`"score_out_of_range"`).

---

### `load_json_safe(path)`

**File:** `agents/data_quality.py`, lines 338–343

```python
def load_json_safe(path: Path) -> Any
```

**Purpose:** Safely loads a JSON file. Returns `None` on `FileNotFoundError` or `json.JSONDecodeError` without raising. Used by `run_data_quality_check` for every file it reads.

---

### `run_data_quality_check(verbose)`

**File:** `agents/data_quality.py`, lines 346–445

```python
def run_data_quality_check(verbose: bool = True) -> dict
```

**Purpose:** Main entry point for the DataQualityAgent. Loads all pipeline output files and runs all check functions.

**Parameters:** `verbose` — if `True`, prints progress and verdict to stdout.

**Returns:** A `dict` with the following structure:

```json
{
  "audit_timestamp": "<ISO 8601>Z",
  "verdict": "PASS" | "FAIL",
  "summary": {
    "blockers": <int>,
    "warnings": <int>,
    "info": <int>
  },
  "findings": [ <QualityFinding.to_dict()>, ... ],
  "message": "<human-readable verdict string>"
}
```

**Step-by-step execution:**

1. Glob `news_output/articles_*.json`, sort descending (most recent first), load the newest file. Handles both `list` format (standard) and Finnhub nested dict format (flattens `company_news` arrays). Calls `check_phase2_output`.

2. Load `news_output/enriched_news_sentiment.json`. If a list, calls `check_phase3_output`. Otherwise appends `INFO` (`"not_found"`).

3. Load `news_output/clustered_summaries.json`. If a dict, calls `check_phase4_output`. Otherwise appends `INFO` (`"not_found"`).

4. Load `news_output/economic_reasoning_summary.json`. Calls `check_economic_reasoning(econ or {})`.

5. Load `recession_signals_output.json`. Calls `check_recession_output(recession or {})`.

6. Partitions all findings by severity. **Verdict is `FAIL` if `len(blockers) > 0`, else `PASS`.**

7. Prints summary to stdout if `verbose=True` (max 5 blocking/warning findings shown).

**Does not write any file directly.** Returns the result dict.

---

## SecurityAuditAgent — `agents/security_audit.py`

### Overview

**Pipeline checkpoint:** Runs on every pipeline execution (no phase dependency).

**What it checks:**

| Check | Function | Severity |
|---|---|---|
| Hardcoded secrets and dangerous code patterns in all `.py` files | `scan_python_files_for_secrets` | CRITICAL, HIGH, MEDIUM |
| API keys / secret patterns in JSON output files | `scan_json_outputs_for_secrets` | CRITICAL, HIGH |
| `.env` file existence and `.gitignore` coverage | `check_env_file` | HIGH, CRITICAL |
| Bandit static analysis (subprocess) | `run_bandit` | CRITICAL/HIGH/MEDIUM (from bandit) |
| CVE scan via safety (subprocess) | `run_safety_check` | HIGH |
| Pipeline output structure validation | `validate_pipeline_output_structure` | INFO, MEDIUM, HIGH |

**Pass/fail verdict logic:** FAIL if any finding has `severity == "CRITICAL"` OR `severity == "HIGH"`. Medium, Low, and Info do not block.

```python
passed = len(critical) == 0 and len(high) == 0  # agents/security_audit.py:365
```

**CI gate behavior:** When run as `__main__`, exits with `sys.exit(0 if _result.get("passed") else 1)` (line 403), allowing CI pipelines and pre-commit hooks to block on failure.

> **Note:** There is a subtle bug at line 403: `_result.get("passed")` should be `_result.get("verdict") == "PASS"` since the result dict contains key `"verdict"`, not `"passed"`. As written, `get("passed")` always returns `None` (falsy), so `__main__` always exits with code 1. `verification_runner.py` correctly reads `result.get("verdict")` and is unaffected.

**Files read:**

- All `*.py` files recursively under repo root (excluding `venv/`, `venv_qlib/`, `__pycache__/`, `.git/`, `site-packages/`)
- First 20 `*.json` files under `news_output/` and `GPT_Economy/`
- `.env` (for existence, gitignore coverage, and rotated-key detection)
- `.gitignore`
- `user_profile.json` (structure validation)
- `news_output/economic_reasoning_summary.json` (structure validation)

**Files written:**

- `pipeline_audit.json` (repo root) — written directly by `run_security_audit` at line 384–385, even when called standalone (unlike other agents which only write via the runner).

---

### Secret Detection Patterns

**File:** `agents/security_audit.py`, lines 34–42

```python
SECRET_PATTERNS = [
    (re.compile(r'sk-proj-[A-Za-z0-9_-]{40,}'), "OpenAI API key"),
    (re.compile(r'sk-[A-Za-z0-9]{48}'), "OpenAI API key (legacy)"),
    (re.compile(r'"api_key"\s*:\s*"[A-Za-z0-9_-]{20,}"'), "Hardcoded API key in JSON"),
    (re.compile(r'password\s*=\s*["\'][^"\']{8,}["\']', re.I), "Hardcoded password"),
    (re.compile(r'secret\s*=\s*["\'][^"\']{8,}["\']', re.I), "Hardcoded secret"),
    (re.compile(r'Bearer [A-Za-z0-9_-]{20,}'), "Hardcoded Bearer token"),
    (re.compile(r'[A-Za-z0-9]{40}'), None),  # Generic long token — flagged only in assignment context
]
```

The first 4 patterns from `SECRET_PATTERNS` are used in `scan_json_outputs_for_secrets` (line 165: `SECRET_PATTERNS[:4]`). All labeled patterns are checked; the generic 40-char token pattern (index 6, `label=None`) is present in the list but the JSON scanner skips it via `if label and ...`.

**Dangerous Code Patterns:**

**File:** `agents/security_audit.py`, lines 44–51

```python
DANGEROUS_PATTERNS = [
    (re.compile(r'\beval\s*\('), "Use of eval() — potential code injection"),
    (re.compile(r'\bexec\s*\('), "Use of exec() — potential code injection"),
    (re.compile(r'subprocess.*shell\s*=\s*True'), "subprocess with shell=True — command injection risk"),
    (re.compile(r'pickle\.loads\b'), "pickle.loads — unsafe deserialization"),
    (re.compile(r'yaml\.load\s*\([^)]*\)(?!.*Loader)'), "yaml.load without Loader — unsafe deserialization"),
    (re.compile(r'os\.system\s*\('), "os.system() — prefer subprocess"),
]
```

All six dangerous patterns are checked on every line of every `.py` file. Any match → `HIGH` severity finding with category `"dangerous_code"`.

**Dynamic secret fragments from `.env`:**

**File:** `agents/security_audit.py`, lines 53–69

```python
def _secret_fragments():
    frags = ["sk-proj-", "sk-ant-", "ghp_", "github_pat_"]
    try:
        for line in (Path(__file__).resolve().parent.parent / ".env").read_text(...).splitlines():
            if "=" in line and not line.strip().startswith("#"):
                v = line.split("=", 1)[1].strip()
                if len(v) >= 16:
                    frags.append(v[:14])   # first 14 chars of each real key value
    except Exception:
        pass
    return frags

KNOWN_BAD_STRINGS = _secret_fragments()
```

`KNOWN_BAD_STRINGS` is built at import time. It starts with four generic provider prefixes:
- `"sk-proj-"` (OpenAI project keys)
- `"sk-ant-"` (Anthropic API keys)
- `"ghp_"` (GitHub Personal Access Tokens)
- `"github_pat_"` (GitHub fine-grained PATs)

Then reads the live `.env` file and appends the first 14 characters of every value that is 16+ characters long. This means real API key material from `.env` is scanned for directly, without ever storing the full key in the committed source file.

---

### `class Finding`

**File:** `agents/security_audit.py`, lines 75–91

```python
class Finding:
    def __init__(self, severity: str, category: str, file: str, line: int, message: str)
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `severity` | `str` | One of `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"INFO"` |
| `category` | `str` | Machine-readable category: `"exposed_secret"`, `"dangerous_code"`, `"env_assignment"`, `"secret_in_output"`, `"missing_env"`, `"env_not_gitignored"`, `"rotated_key_in_env"`, `"bandit_<test_id>"`, `"cve"`, `"missing_output"`, `"malformed_output"`, `"invalid_json"`, `"tool_missing"`, `"tool_error"` |
| `file` | `str` | Relative file path (relative to repo root) |
| `line` | `int` | Line number (`0` for file-level findings) |
| `message` | `str` | Human-readable description |

#### `Finding.to_dict()`

```python
def to_dict(self) -> dict
```

Returns `{"severity", "category", "file", "line", "message"}`. Used for JSON serialization.

---

### `scan_python_files_for_secrets(root)`

**File:** `agents/security_audit.py`, lines 93–138

```python
def scan_python_files_for_secrets(root: Path) -> list[Finding]
```

**Purpose:** Scans all `.py` files in the project for hardcoded secrets and dangerous code patterns.

**Parameters:** `root` — the repo root `Path`.

**Step-by-step behavior:**

1. `root.rglob("*.py")` — finds all Python files recursively.
2. Skips files where any path component is in `{"venv", "venv_qlib", "__pycache__", ".git", "site-packages"}`.
3. Reads each file with `errors="replace"` (handles binary content gracefully).
4. Iterates line by line:
   - **Known bad strings:** For each string in `KNOWN_BAD_STRINGS`, checks `if bad_str in line`. Match → `CRITICAL` finding, category `"exposed_secret"`, message shows first 8 chars followed by `...`.
   - **Dangerous patterns:** For each of 6 patterns in `DANGEROUS_PATTERNS`, checks `pattern.search(line)`. Match → `HIGH` finding, category `"dangerous_code"`.
   - **Direct env assignment:** Checks `re.search(r'os\.environ\["(OPENAI|API|SECRET|KEY|TOKEN|PASSWORD)', line, re.I)`. If matched and line does not contain `"os.getenv"` or `"load_dotenv"` → `MEDIUM` finding, category `"env_assignment"`.

---

### `scan_json_outputs_for_secrets(root)`

**File:** `agents/security_audit.py`, lines 141–174

```python
def scan_json_outputs_for_secrets(root: Path) -> list[Finding]
```

**Purpose:** Checks pipeline output JSON files for accidentally embedded API keys.

**Step-by-step behavior:**

1. Scans `news_output/` and `GPT_Economy/` directories (if they exist) for all `*.json` files.
2. Samples the **first 20 files only** (line 150: `output_files[:20]`).
3. For each file, reads full text content:
   - Checks each `KNOWN_BAD_STRINGS` fragment. Match → `CRITICAL` finding, breaks (one finding per file).
   - Checks `SECRET_PATTERNS[:4]` (the four most specific patterns). Labeled match → `HIGH` finding, breaks.

---

### `check_env_file(root)`

**File:** `agents/security_audit.py`, lines 177–211

```python
def check_env_file(root: Path) -> list[Finding]
```

**Purpose:** Verifies that the `.env` file exists, is gitignored, and does not still contain previously-rotated keys.

**Step-by-step behavior:**

1. If `root / ".env"` does not exist → `HIGH` finding (`"missing_env"`), return immediately.
2. Reads `.gitignore`. If `".env"` not a substring of its content → `HIGH` finding (`"env_not_gitignored"`).
3. Reads `.env` content. For each string in `KNOWN_BAD_STRINGS`, checks if present → `CRITICAL` finding (`"rotated_key_in_env"`), prompting immediate key rotation.

---

### `run_bandit(root)`

**File:** `agents/security_audit.py`, lines 214–244

```python
def run_bandit(root: Path) -> list[Finding]
```

**Purpose:** Runs the `bandit` static analysis tool as a subprocess and parses its JSON output.

**Subprocess call:**

```
python -m bandit -r <root> --exclude <root>/venv,<root>/venv_qlib -f json -q
```

**Step-by-step behavior:**

1. Runs bandit with 60-second timeout.
2. If stdout is non-empty, parses as JSON. Processes up to the first 10 `"results"` entries.
3. Each bandit result maps to a `Finding` with:
   - `severity`: `issue.get("issue_severity", "MEDIUM").upper()`
   - `category`: `"bandit_" + issue.get("test_id", "unknown").lower()`
   - `file`: bandit's `filename` with root prefix stripped
   - `line`: bandit's `line_number`
   - `message`: `"[<test_id>] <issue_text>"`
4. On `FileNotFoundError` (bandit not installed) → `INFO` finding (`"tool_missing"`).
5. On any other exception → `INFO` finding (`"tool_error"`).

---

### `run_safety_check()`

**File:** `agents/security_audit.py`, lines 247–276

```python
def run_safety_check() -> list[Finding]
```

**Purpose:** Runs `safety check` to identify dependencies with known CVEs.

**Subprocess call:**

```
python -m safety check --json
```

**Step-by-step behavior:**

1. Runs safety with 30-second timeout.
2. Parses stdout as JSON. Handles both list format (legacy safety) and dict with `"vulnerabilities"` key.
3. Processes up to 5 vulnerabilities. Each maps to a `Finding` with:
   - `severity`: `"HIGH"`
   - `category`: `"cve"`
   - `file`: `"requirements.txt"`
   - `message`: `"Vulnerable package: <name>. <advisory[:100]>"`
4. On `FileNotFoundError` → `INFO` (`"tool_missing"`).
5. On exception → `INFO` (`"tool_error"`).

---

### `validate_pipeline_output_structure(root)`

**File:** `agents/security_audit.py`, lines 279–322

```python
def validate_pipeline_output_structure(root: Path) -> list[Finding]
```

**Purpose:** Checks that key pipeline output files exist and contain their required top-level keys.

**Checks defined** (lines 283–294):

| File | Required Keys | Label |
|---|---|---|
| `user_profile.json` | `["age", "risk_tolerance", "risk_score"]` | `"User Profile"` |
| `news_output/economic_reasoning_summary.json` | `["summary", "bullish_sectors", "bearish_sectors"]` | `"Economic Reasoning"` |

**Step-by-step behavior per check:**

1. If file does not exist → `INFO` finding (`"missing_output"`). Continue to next check.
2. Load and parse JSON. If `json.JSONDecodeError` → `HIGH` finding (`"invalid_json"`).
3. For each required key missing from the parsed dict → `MEDIUM` finding (`"malformed_output"`).

---

### `run_security_audit(verbose)`

**File:** `agents/security_audit.py`, lines 329–397

```python
def run_security_audit(verbose: bool = True) -> dict
```

**Purpose:** Main entry point for SecurityAuditAgent. Runs all six check functions and writes `pipeline_audit.json`.

**Execution order:**

1. `scan_python_files_for_secrets(BASE_DIR)`
2. `scan_json_outputs_for_secrets(BASE_DIR)`
3. `check_env_file(BASE_DIR)`
4. `run_bandit(BASE_DIR)`
5. `run_safety_check()`
6. `validate_pipeline_output_structure(BASE_DIR)`

**Verdict logic** (line 365):

```python
passed = len(critical) == 0 and len(high) == 0
```

**Return dict structure:**

```json
{
  "audit_timestamp": "<ISO 8601>Z",
  "verdict": "PASS" | "FAIL",
  "summary": {
    "critical": <int>,
    "high": <int>,
    "medium": <int>,
    "info": <int>,
    "total": <int>
  },
  "findings": [ <Finding.to_dict()>, ... ],
  "message": "<human-readable verdict>"
}
```

**Writes directly** to `pipeline_audit.json` (line 384–385). This is the only agent that writes to disk independently of the runner.

**Verbose output** (when `verbose=True`): Prints progress, verdict label, and the first 5 critical/high findings with `file:line — message` format.

---

## StrategyAuditAgent — `agents/strategy_audit.py`

### Overview

**Pipeline checkpoint:** After Phase 9 (backtesting). Reads output from `Module_2_Technical_Analysis/results_run/`.

**What it checks:**

| Check ID | Metric | Threshold | Severity |
|---|---|---|---|
| `negative_sharpe` | Sharpe ratio | `< 0` | BLOCKER |
| `low_sharpe` | Sharpe ratio | `< 0.5` | WARN |
| `sharpe_ok` | Sharpe ratio | `>= 0.5` | INFO |
| `excessive_drawdown` | Max Drawdown % | `> 35` | BLOCKER |
| `high_drawdown` | Max Drawdown % | `> 20` | WARN |
| `negative_cagr` | CAGR % | `< 0` | BLOCKER |
| `suspicious_cagr` | CAGR % | `> 100` | WARN |
| `no_trades` | Trade count | `== 0` | BLOCKER |
| `too_few_trades` | Trade count | `< 5` | WARN |
| `overtrading` | Trade count | `> 500` | WARN |
| `low_market_exposure` | Time in Market % | `< 5` (and trades > 0) | WARN |
| `possible_lookahead` | CAGR > 50 AND trades < 20 | Heuristic combined | WARN |

**Pass/fail verdict logic:** FAIL if any finding has `severity == "BLOCKER"`. Warnings do not block.

**Files read:**

| File Path | Purpose |
|---|---|
| `Module_2_Technical_Analysis/results_run/summary_metrics.json` | Numeric strategy performance metrics |
| `Module_2_Technical_Analysis/results_run/trade_log.csv` | Trade log (line count used to determine trade count) |

**Files written:** None directly. Results returned as dict for the runner to include in `pipeline_audit.json`.

---

### `class StrategyFinding`

**File:** `agents/strategy_audit.py`, lines 32–47

```python
class StrategyFinding:
    def __init__(self, severity: str, check: str, message: str, value: Any = None, plain_english: str = "")
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `severity` | `str` | `"BLOCKER"`, `"WARN"`, or `"INFO"` |
| `check` | `str` | Machine-readable check ID (e.g., `"negative_sharpe"`, `"excessive_drawdown"`) |
| `message` | `str` | Technical description for developers |
| `value` | `Any` | The raw metric value that triggered the finding (e.g., `-0.43` for Sharpe) |
| `plain_english` | `str` | Plain-language explanation for the dashboard, written for non-technical users |

#### `StrategyFinding.to_dict()`

```python
def to_dict(self) -> dict
```

Returns `{"severity", "check", "message", "value", "plain_english"}`.

---

### `load_json(path)`

**File:** `agents/strategy_audit.py`, lines 50–55

```python
def load_json(path: Path) -> dict
```

Returns empty dict `{}` on `FileNotFoundError` or `json.JSONDecodeError`. Safe loader; does not raise.

---

### `count_trades(trade_log_path)`

**File:** `agents/strategy_audit.py`, lines 58–64

```python
def count_trades(trade_log_path: Path) -> int
```

Opens the CSV trade log and counts `len(lines) - 1` (subtracts the header row). Returns `-1` if the file is not found (indicating Phase 9 has not been run).

---

### `run_strategy_audit(verbose)`

**File:** `agents/strategy_audit.py`, lines 67–202

```python
def run_strategy_audit(verbose: bool = True) -> dict
```

**Purpose:** Main entry point for StrategyAuditAgent.

**Step-by-step behavior:**

1. Loads `summary_metrics.json` via `load_json`. If empty → single `INFO` finding (`"missing_backtest"`) and returns immediately via `_build_result`.

2. Extracts metric values with safe float conversion and `None` handling:
   ```python
   sharpe         = float(metrics.get("Sharpe", 0) or 0)
   sortino        = float(metrics.get("Sortino", 0) or 0) if metrics.get("Sortino") not in (None, float("inf")) else None
   max_drawdown   = float(metrics.get("Max Drawdown %", 0) or 0)
   cagr           = float(metrics.get("CAGR %", 0) or 0)
   time_in_market = float(metrics.get("Time in Market %", 0) or 0)
   trade_count    = count_trades(TRADE_LOG_PATH)
   ```

3. **Check 1 — Sharpe Ratio** (lines 95–115):
   - `< 0` → BLOCKER `"negative_sharpe"` with plain-English: "A negative Sharpe means the strategy is losing more money than it would if you just held cash."
   - `< 0.5` → WARN `"low_sharpe"`, target is Sharpe > 1.0.
   - `>= 0.5` → INFO `"sharpe_ok"`.

4. **Check 2 — Max Drawdown** (lines 117–133):
   - `> 35` → BLOCKER `"excessive_drawdown"` with plain-English explaining retail investor behavior.
   - `> 20` → WARN `"high_drawdown"` recommending trailing stops.

5. **Check 3 — CAGR** (lines 135–153):
   - `< 0` → BLOCKER `"negative_cagr"` explaining signals predicting wrong direction or excessive costs.
   - `> 100` → WARN `"suspicious_cagr"` flagging lookahead bias as the probable cause.

6. **Check 4 — Trade Count** (lines 155–179):
   - `== 0` → BLOCKER `"no_trades"` with specific remediation: "Lower min_align from 3 to 2, or check that signal columns are mapped correctly."
   - `< 5` → WARN `"too_few_trades"` (statistically meaningless sample).
   - `> 500` → WARN `"overtrading"` (commission/slippage risk).

7. **Check 5 — Time in Market** (lines 181–189):
   - `< 5%` AND `trade_count != 0` → WARN `"low_market_exposure"` suggesting signal alignment requirements are too strict.

8. **Check 6 — Lookahead Bias Heuristic** (lines 191–201):
   - `cagr > 50 AND trade_count < 20` → WARN `"possible_lookahead"` explaining that entry fills should be on the next bar (t+1), not the signal bar (t).

9. Calls `_build_result(findings, verbose)` to package and return.

---

### `_build_result(findings, verbose)`

**File:** `agents/strategy_audit.py`, lines 205–247

```python
def _build_result(findings: list[StrategyFinding], verbose: bool) -> dict
```

**Purpose:** Packages findings into the return dict, generates plain-English summary, and prints verbose output.

**Verdict logic:** FAIL if any BLOCKER finding present.

**Plain-English summary generation:**

- If blockers: `"Strategy audit found {n} critical issue(s) that must be fixed: {first 2 blocker messages joined by '; '}"`
- If warnings only: `"Strategy passed basic checks but has {n} warning(s) to review."`
- If clean: `"Strategy audit passed. No critical issues detected."`

**Return dict structure:**

```json
{
  "audit_timestamp": "<ISO 8601>Z",
  "verdict": "PASS" | "FAIL",
  "summary": {
    "blockers": <int>,
    "warnings": <int>,
    "info": <int>
  },
  "plain_english_summary": "<string>",
  "findings": [ <StrategyFinding.to_dict()>, ... ],
  "recommendations": [ "<string>", ... ]
}
```

**Verbose output:** Prints verdict label, first 5 blocker+warning findings, and first 3 recommendations.

---

### `_build_recommendations(findings)`

**File:** `agents/strategy_audit.py`, lines 250–273

```python
def _build_recommendations(findings: list[StrategyFinding]) -> list[str]
```

**Purpose:** Generates a prioritized, actionable recommendation list based on which check IDs fired.

**Rule table:**

| Triggered Checks | Recommendations Added |
|---|---|
| `"no_trades"` or `"too_few_trades"` | 1) Reduce `min_align` from 3 to 2. 2) Verify `COLUMN_ALIASES` maps `'macd_signal'` to `'macd_signal_flag'`. |
| `"negative_cagr"` or `"negative_sharpe"` | 1) Switch to LONG-ONLY strategy. 2) Add ATR trailing stops (2x ATR below peak). 3) Add trend filter: only enter long when `Close > SMA200`. |
| `"excessive_drawdown"` or `"high_drawdown"` | 1) Per-trade risk sizing: risk 1–2% equity per trade. 2) Reduce max drawdown stop from 35% to 15%. |
| `"possible_lookahead"` | Verify entry fills on next bar (t+1, not t). Reference `cerebro.resampledata`. |
| None of the above | `"Continue monitoring strategy performance as market conditions change."` |

---

## VerificationRunner — `agents/verification_runner.py`

### Overview

`verification_runner.py` is the orchestration entry point that invokes all three agents, collects their results, computes an overall verdict, and writes the unified `pipeline_audit.json`. It is designed to be called by `controller.py` (Phase 12) at defined pipeline checkpoints, or run directly from the command line.

**CLI interface:**

```
python agents/verification_runner.py [--phase {security,data,strategy,all}] [--quiet]
```

Default: `--phase all`.

**Exit codes:**

- `0` — overall verdict is `PASS`
- `1` — overall verdict is `FAIL`, `ERROR`, or `UNKNOWN`

**Files written:**

- `pipeline_audit.json` (repo root) — combined output from all agents.

---

### Constants and Imports

**File:** `agents/verification_runner.py`, lines 23–30

```python
BASE_DIR = Path(__file__).parent.parent
AUDIT_OUTPUT = BASE_DIR / "pipeline_audit.json"
sys.path.insert(0, str(BASE_DIR))

from agents.security_audit import run_security_audit
from agents.data_quality import run_data_quality_check
from agents.strategy_audit import run_strategy_audit
```

The runner inserts `BASE_DIR` into `sys.path` so agent imports resolve regardless of working directory.

---

### `run_all_agents(verbose)`

**File:** `agents/verification_runner.py`, lines 33–121

```python
def run_all_agents(verbose: bool = True) -> dict
```

**Purpose:** Runs all three agents in sequence, catches exceptions, and produces a combined audit result.

**Execution order and crash isolation:**

Each agent is wrapped in a `try/except Exception`:

```
[1/3] SecurityAuditAgent  → results["security"]
[2/3] DataQualityAgent    → results["data_quality"]
[3/3] StrategyAuditAgent  → results["strategy_audit"]
```

If an agent raises an uncaught exception, a synthetic error result is inserted:

```json
{
  "verdict": "ERROR",
  "message": "<AgentName> crashed: <exception>",
  "findings": []
}
```

**Overall verdict logic** (lines 91–94):

```python
all_verdicts = [r.get("verdict", "UNKNOWN") for r in results.values()]
any_fail = any(v in ("FAIL", "ERROR") for v in all_verdicts)
overall = "FAIL" if any_fail else "PASS"
```

`ERROR` and `FAIL` both count as pipeline failures. `UNKNOWN` is not in the fail-set, so an unrecognized verdict defaults to PASS (edge case for future agents).

**Combined output written to `pipeline_audit.json`:**

```json
{
  "pipeline_audit_timestamp": "<ISO 8601>Z",
  "overall_verdict": "PASS" | "FAIL",
  "agents_run": ["security", "data_quality", "strategy_audit"],
  "agent_verdicts": {
    "security": "PASS" | "FAIL" | "ERROR",
    "data_quality": "PASS" | "FAIL" | "ERROR",
    "strategy_audit": "PASS" | "FAIL" | "ERROR"
  },
  "agent_results": {
    "security": { <full SecurityAuditAgent result> },
    "data_quality": { <full DataQualityAgent result> },
    "strategy_audit": { <full StrategyAuditAgent result> }
  },
  "message": "<human-readable overall verdict>"
}
```

**Verbose output:** Prints banner, per-agent verdict with icons, and path to the audit file.

---

### `run_single_agent(agent_name, verbose)`

**File:** `agents/verification_runner.py`, lines 124–134

```python
def run_single_agent(agent_name: str, verbose: bool = True) -> dict
```

**Purpose:** Dispatches to a single agent by name string. Accepted names: `"security"`, `"data"`, `"strategy"`.

On unrecognized name: prints error and `sys.exit(1)`.

> **Note:** When a single agent is run via `run_single_agent`, results are **not** written to `pipeline_audit.json` by the runner (only SecurityAuditAgent writes directly). DataQualityAgent and StrategyAuditAgent results are only returned in-memory.

---

### `main()`

**File:** `agents/verification_runner.py`, lines 137–157

```python
def main()
```

**Purpose:** CLI entry point. Parses `--phase` and `--quiet` arguments.

**Argument parsing:**

| Argument | Choices | Default | Effect |
|---|---|---|---|
| `--phase` | `security`, `data`, `strategy`, `all` | `all` | Which agent(s) to run |
| `--quiet` | flag | off | Suppresses verbose output |

**Exit behavior** (lines 155–157):

```python
verdict = result.get("overall_verdict", result.get("verdict", "UNKNOWN"))
sys.exit(0 if verdict == "PASS" else 1)
```

Reads `"overall_verdict"` for the combined run, falls back to `"verdict"` for single-agent runs. Exits `1` on anything except `"PASS"`.

---

## Cross-Agent Architecture Notes

### Data Flow

```
Pipeline phases
    │
    ▼
controller.py (Phase 12)
    │
    ├─ calls verification_runner.py
    │       │
    │       ├─ [1] SecurityAuditAgent ──── reads .py files, .env, .gitignore, JSON outputs
    │       │       └─ writes pipeline_audit.json (directly)
    │       │
    │       ├─ [2] DataQualityAgent ────── reads news_output/*.json, recession_signals_output.json
    │       │       └─ returns dict only
    │       │
    │       └─ [3] StrategyAuditAgent ──── reads Module_2_Technical_Analysis/results_run/
    │               └─ returns dict only
    │
    └─ writes pipeline_audit.json (combined, overwrites SecurityAuditAgent's direct write)
```

### Severity Vocabulary by Agent

| Agent | Severity Levels | Block Level |
|---|---|---|
| DataQualityAgent | BLOCKER, WARN, INFO | BLOCKER |
| SecurityAuditAgent | CRITICAL, HIGH, MEDIUM, LOW, INFO | CRITICAL or HIGH |
| StrategyAuditAgent | BLOCKER, WARN, INFO | BLOCKER |

### `pipeline_audit.json` Schema (Combined)

The file at repo root is overwritten on every full runner invocation. The schema nests the full result dict from each agent under `"agent_results"`:

```
pipeline_audit.json
├── pipeline_audit_timestamp     (ISO 8601 UTC string)
├── overall_verdict              ("PASS" | "FAIL")
├── agents_run                   (list of agent keys)
├── agent_verdicts               (flat key → verdict summary)
├── agent_results
│   ├── security                 (full SecurityAuditAgent result)
│   ├── data_quality             (full DataQualityAgent result)
│   └── strategy_audit           (full StrategyAuditAgent result)
└── message                      (human-readable overall verdict)
```

### Pipeline Error Reporting

The CLAUDE.md architecture document specifies a `pipeline_errors.json` file for failed-verdict logging, but the current implementation consolidates all findings directly into `pipeline_audit.json`. No separate `pipeline_errors.json` is written by any agent in the current codebase.

### Planned Agents Not Yet Implemented

Per CLAUDE.md, the following agents are planned but have no corresponding files in `agents/`:

| Planned Agent | Planned Trigger | Status |
|---|---|---|
| `FinancialFactAgent` | After Phase 5 (GPT summarization) | Not implemented |
| `EconomicReasoningAgent` | After Phase 6 (reasoning engine) | Not implemented |
| `RecessionSignalAgent` | After Phase 13 (recession engine) | Not implemented |

These would live in `agents/verification/` per the roadmap, though the three current agents live directly in `agents/`.
