# Part 5 — Backend Server Reference (FastAPI)

This document is an exhaustive technical reference for every file in `server/`. It covers every function, class, constant, route, middleware, and security mechanism exactly as written in the source code. File-and-line citations appear where precision matters.

---

## Table of Contents

1. [Dependency Map](#1-dependency-map)
2. [File: `requirements.txt`](#2-file-requirementstxt)
3. [File: `.env.example`](#3-file-envexample)
4. [File: `.gitignore`](#4-file-gitignore)
5. [File: `config.py`](#5-file-configpy)
6. [File: `db.py`](#6-file-dbpy)
7. [File: `auth.py`](#7-file-authpy)
8. [File: `data.py`](#8-file-datapy)
9. [File: `main.py`](#9-file-mainpy)
10. [Endpoints Quick-Reference Table](#10-endpoints-quick-reference-table)
11. [Security Architecture Summary](#11-security-architecture-summary)

---

## 1. Dependency Map

```
main.py
├── config.py          (settings, resolved paths, tier definitions)
├── db.py              (SQLite user store)
├── auth.py            (router: /api/auth/*, JWT, bcrypt, rate limiting)
│   ├── config.py
│   └── db.py
└── data.py            (router: /api/data/*, gated datasets)
    ├── config.py
    └── auth.py        (imports current_user dependency)
```

Import order matters: `db.init_db()` is called inside `main.py` at module load time, before any request is handled.

---

## 2. File: `requirements.txt`

**Responsibility:** Declares the exact pinned Python dependencies for the isolated server virtualenv. The comment at the top of the file explicitly warns that this virtualenv must be kept separate from the data-pipeline virtualenv (`tf_env`) because the version pins are different.

| Package | Pinned Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.0 | ASGI web framework; routes, middleware, dependency injection |
| `uvicorn[standard]` | 0.30.1 | ASGI server (includes `httptools`, `uvloop`, `websockets`) |
| `bcrypt` | 4.1.3 | Password hashing; slow by design to resist offline brute-force |
| `PyJWT` | 2.8.0 | Signs and verifies JWT session tokens with HS256 |
| `python-dotenv` | 1.0.1 | Loads `server/.env` into `os.environ` at startup |

**No ORM, no async DB driver, no Redis.** The design is intentionally minimal for a single-process closed beta: SQLite + in-memory rate-limit state is sufficient and avoids operational complexity.

---

## 3. File: `.env.example`

**Responsibility:** Template for `server/.env`, which is gitignored. Documents every environment variable the server reads. Operators copy this file to `server/.env` and fill in real values, or set the variables directly in the hosting platform dashboard (Render / Railway / Fly).

### Variables

| Variable | Default in example | Purpose |
|---|---|---|
| `TF_SECRET_KEY` | `change-me-to-a-long-random-string` | HMAC-SHA256 signing key for JWT session tokens. Must be replaced before production. |
| `TF_BETA_KEY` | `<redacted — configured via TF_BETA_KEY>` | Closed-beta invite key. Users must present this at signup. |
| `TF_PRODUCTION` | `0` | Set to `"1"` to enable Secure cookies, HSTS header, and HTTPS redirect. |
| `TF_ALLOWED_ORIGINS` | `http://localhost:8000` | Comma-separated CORS allow-list. In production: exact HTTPS domain. |
| `LEGISCAN_API_KEY` | _(empty)_ | Used by offline build scripts only; never sent to the browser. |
| `OPENSTATES_API_KEY` | _(empty)_ | Used by offline build scripts only; never sent to the browser. |
| `FINNHUB_API_KEY` | _(empty)_ | Used by offline build scripts only; never sent to the browser. |
| `OPENAI_API_KEY` | _(empty)_ | Used by offline build scripts only; never sent to the browser. |

The comment in the file notes a method for generating a strong signing key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 4. File: `.gitignore`

**Responsibility:** Prevents secrets and local artifacts from entering version control. The server `.gitignore` file is intentionally narrow — it only covers server-specific artifacts.

Entries:
- `.env` — the live secrets file
- `.venv/` — the server's isolated virtualenv
- `__pycache__/` — compiled bytecode
- `*.pyc` — compiled bytecode
- `users.db` — the SQLite database containing hashed passwords and user records

---

## 5. File: `config.py`

**Responsibility:** Central configuration for the entire backend. Loads all settings from the environment (via `python-dotenv`) and exposes them as module-level constants. All other modules import from here; nothing is hardcoded anywhere else.

### Module-Level Constants

#### Path Constants

Resolved at import time using `Path(__file__).resolve().parent` so the server runs correctly regardless of the working directory when `uvicorn` is started.

| Constant | Value / Resolution | Type |
|---|---|---|
| `SERVER_DIR` | Directory containing `config.py` itself (`.../ThinkFree-main/server`) | `Path` |
| `ROOT_DIR` | Parent of `SERVER_DIR` (`.../ThinkFree-main`) | `Path` |
| `WEBAPP_DIR` | `ROOT_DIR / "webapp"` — the static front-end shell | `Path` |
| `PRIVATE_DATA_DIR` | `ROOT_DIR / "private_data"` — built JSON datasets, never web-served | `Path` |
| `DB_PATH` | `SERVER_DIR / "users.db"` — the SQLite database file | `Path` |

#### Runtime Settings (from environment)

| Constant | Environment Variable | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | `TF_SECRET_KEY` | `"change-me-to-a-long-random-string"` | JWT signing key (HS256) |
| `BETA_KEY` | `TF_BETA_KEY` | `"<redacted — configured via TF_BETA_KEY>"` | Closed-beta invite key |
| `PRODUCTION` | `TF_PRODUCTION` | `False` (when env var != `"1"`) | Enables Secure cookies, HSTS, HTTPS redirect |
| `ALLOWED_ORIGINS` | `TF_ALLOWED_ORIGINS` | `["http://localhost:8000"]` | CORS allow-list (split on `,`, stripped) |
| `SESSION_TTL_SECONDS` | _(hardcoded)_ | `604800` (7 days) | JWT and cookie expiry |

#### Tier Definitions

`TIERS: dict[str, dict]` — maps tier slug to display name and refresh cadence. The `refresh_min` value is the minimum number of minutes between `/api/data/live` calls for users on that tier. The server enforces this value; it cannot be bypassed by the browser.

```python
TIERS = {
    "free":   {"name": "Free",         "refresh_min": 1440},  # once/day
    "hourly": {"name": "Pro - Hourly", "refresh_min": 60},
    "half":   {"name": "Pro - 30-min", "refresh_min": 30},
    "live":   {"name": "Pro - 15-min", "refresh_min": 15},
    "beta":   {"name": "Beta Access",  "refresh_min": 15},    # full access during beta
}
```

`DEFAULT_TIER: str` = `"beta"` — all new accounts created during the closed beta receive the `"beta"` tier, giving them 15-minute refresh access.

### Functions

---

### `_get`

```python
def _get(name: str, default: str = "") -> str
```

**Parameters:**
- `name: str` — environment variable name
- `default: str` — value to use if the variable is absent

**Returns:** `str` — the environment variable value, or `default`.

**What it does:** A thin wrapper around `os.environ.get`. Used internally by every config setting to read from the environment.

**Security relevance:** All sensitive values (`SECRET_KEY`, `BETA_KEY`) pass through this function. By routing all env reads through one function, the module makes it impossible to accidentally hardcode a value inline and forget to read from the environment.

---

### `is_placeholder_secret`

```python
def is_placeholder_secret() -> bool
```

**Parameters:** None.

**Returns:** `bool` — `True` if `SECRET_KEY` is either the empty string or the default placeholder `"change-me-to-a-long-random-string"`.

**What it does:** Checks whether the JWT signing key is still the insecure default. Called in `main.py` at startup; if it returns `True` while `PRODUCTION` is also `True`, the application raises `RuntimeError` and refuses to start.

**Security relevance:** Fail-loud guard against deploying with a guessable signing key. Without this check, a misconfigured production deploy would silently accept any token signed with the known placeholder.

---

## 6. File: `db.py`

**Responsibility:** A minimal SQLite-backed user store. Uses only Python's standard library `sqlite3` module (no ORM). The design explicitly notes that this module is the single swap point if the project grows to need Postgres: callers use the public functions, never the SQLite connection directly.

Every function opens a fresh short-lived connection and commits or reads within a single `with` block. This avoids shared-connection threading issues while remaining safe across FastAPI's thread pool.

### Database Schema

Table: `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `email` | `TEXT` | `PRIMARY KEY` | Lowercase email address; the account identifier |
| `name` | `TEXT` | `NOT NULL` | Display name |
| `pass_hash` | `TEXT` | `NOT NULL` | bcrypt hash of the password (never plaintext) |
| `tier` | `TEXT` | `NOT NULL` | Tier slug (`"free"`, `"beta"`, etc.) |
| `a11y` | `INTEGER` | `NOT NULL DEFAULT 0` | Accessibility mode flag; `0`=off, `1`=on |
| `profile` | `TEXT` | nullable | JSON-encoded behavioral quiz answers |
| `created` | `TEXT` | `NOT NULL` | ISO date string (`YYYY-MM-DD`) |
| `token_valid_after` | `INTEGER` | `NOT NULL DEFAULT 0` | Unix timestamp; tokens with `iat` before this are rejected |

The `token_valid_after` column was added after initial deployment. `init_db()` handles live migration using `PRAGMA table_info`.

### Functions

---

### `_connect`

```python
def _connect() -> sqlite3.Connection
```

**Parameters:** None.

**Returns:** `sqlite3.Connection` — a new connection to the database at `config.DB_PATH`, with `row_factory = sqlite3.Row` (so rows behave like dicts).

**What it does:** Opens a fresh SQLite connection on every call. `check_same_thread=False` is set because FastAPI runs handlers across multiple threads; opening per-call avoids sharing a single connection across threads. `row_factory = sqlite3.Row` allows columns to be accessed by name.

**Side effects:** Creates `users.db` on disk if it does not exist.

---

### `init_db`

```python
def init_db() -> None
```

**Parameters:** None.

**Returns:** `None`.

**What it does (step by step):**
1. Opens a connection via `_connect()`.
2. Executes `CREATE TABLE IF NOT EXISTS users (...)` with all columns.
3. Runs `PRAGMA table_info(users)` to get the set of existing column names.
4. If `token_valid_after` is not present (pre-migration database), issues `ALTER TABLE users ADD COLUMN token_valid_after INTEGER NOT NULL DEFAULT 0` to add it non-destructively.
5. Commits.

**Side effects:** Modifies the database schema if the migration column is missing.

**Called by:** `main.py` at module load time, before any request is handled (`db.init_db()` at line 36 of `main.py`).

---

### `get_user`

```python
def get_user(email: str) -> Optional[dict]
```

**Parameters:**
- `email: str` — the email address to look up (lowercased internally)

**Returns:** `dict | None` — the full account row as a Python dict (with `profile` JSON decoded and `a11y` converted to `bool`), or `None` if no matching row exists.

**What it does (step by step):**
1. Executes `SELECT * FROM users WHERE email = ?` with `email.lower()`.
2. If no row, returns `None`.
3. Converts the `sqlite3.Row` to a plain `dict`.
4. Casts `a11y` from integer to `bool`.
5. Parses `profile` from JSON string to dict/None.
6. Returns the augmented dict.

**Security relevance:** Always lowercases the lookup key, matching the insert behavior in `create_user`. Prevents account duplication from case differences. The returned dict contains `pass_hash`; callers in `auth.py` are responsible for stripping it before returning anything to the browser (see `_public_user`).

---

### `create_user`

```python
def create_user(email: str, name: str, pass_hash: str, tier: str, created: str) -> None
```

**Parameters:**
- `email: str` — lowercased email (primary key)
- `name: str` — display name (already stripped by caller)
- `pass_hash: str` — bcrypt-hashed password (plaintext never passed here)
- `tier: str` — tier slug
- `created: str` — ISO date string

**Returns:** `None`.

**What it does:** Executes a parameterized `INSERT INTO users` with `a11y=0` and `profile=NULL`. Commits on success.

**Side effects:** Raises `sqlite3.IntegrityError` if the email already exists (primary key violation). The caller (`auth.signup`) checks for an existing account before calling this, so this is a safety net.

**Security relevance:** Uses parameterized queries throughout — no string interpolation, no SQL injection vector. The `pass_hash` parameter is always a bcrypt digest; the plaintext password is never passed to this function.

---

### `update_profile`

```python
def update_profile(email: str, profile: Optional[dict]) -> None
```

**Parameters:**
- `email: str` — account to update
- `profile: Optional[dict]` — behavioral quiz answers, or `None` to clear

**Returns:** `None`.

**What it does:** Serializes `profile` to JSON (or stores `NULL`) and executes a parameterized `UPDATE users SET profile = ? WHERE email = ?`. Commits on success.

**Side effects:** Overwrites the existing profile.

---

### `update_a11y`

```python
def update_a11y(email: str, a11y: bool) -> None
```

**Parameters:**
- `email: str` — account to update
- `a11y: bool` — `True` to enable accessibility mode

**Returns:** `None`.

**What it does:** Converts `a11y` to `1` or `0` and executes a parameterized `UPDATE users SET a11y = ? WHERE email = ?`. Commits on success.

---

### `update_token_valid_after`

```python
def update_token_valid_after(email: str, ts: int) -> None
```

**Parameters:**
- `email: str` — account whose tokens should be invalidated
- `ts: int` — Unix timestamp (seconds); any token with `iat < ts` is rejected

**Returns:** `None`.

**What it does:** Executes a parameterized `UPDATE users SET token_valid_after = ? WHERE email = ?` and commits.

**Security relevance:** This is the JWT revocation mechanism. On logout, `auth.logout` calls this with `int(time.time())` as `ts`. From that point forward, any JWT that was issued before the logout — including a token the attacker may have captured — is rejected by `auth.current_user` even if the token has not yet expired. This closes the window between logout and natural token expiry.

---

## 7. File: `auth.py`

**Responsibility:** All authentication and session management for the closed beta. Implements signup (with invite-key gating), login, logout, and the `current_user` FastAPI dependency. Security properties enforced here: bcrypt password hashing, httpOnly/Secure/SameSite JWT cookie, constant-time invite-key comparison, in-memory brute-force rate limiting, and JWT revocation via `token_valid_after`.

All routes are mounted under the prefix `/api/auth`.

### Module-Level Constants

| Constant | Value | Purpose |
|---|---|---|
| `COOKIE_NAME` | `"tf_session"` | Name of the httpOnly session cookie |
| `_EMAIL_RE` | compiled regex | Validates email format (requires real-looking TLD, 2+ letters); case-insensitive |
| `_LOGIN_MAX_FAILS` | `5` | Max failed logins per (IP + email) before 429 |
| `_LOGIN_WINDOW` | `900` (15 min) | Rolling window for per-account login failures |
| `_LOGIN_IP_MAX_FAILS` | `20` | Max failed logins per IP across all accounts before 429 |
| `_LOGIN_IP_WINDOW` | `900` (15 min) | Rolling window for per-IP login failures |
| `_SIGNUP_MAX_FAILS` | `10` | Max failed signup attempts per IP before 429 |
| `_SIGNUP_WINDOW` | `3600` (1 hour) | Rolling window for per-IP signup failures |
| `_fails` | `dict[str, deque]` | In-memory store of failure timestamps, keyed by rate-limit key string |

### Brute-Force Rate Limiting

The limiter uses a **rolling window** strategy: each failure is recorded as a timestamp in a `collections.deque`. On each check, entries older than the window are dropped from the front. If the remaining count meets or exceeds the threshold, HTTP 429 is raised with a `Retry-After` header indicating seconds until the oldest failure ages out.

Three separate rate-limit dimensions are tracked:

1. **Per (IP + email)** for login — `"login:{ip}:{email}"` — stops targeted password guessing against one account.
2. **Per IP** for login — `"login_ip:{ip}"` — stops credential-stuffing sprays across many accounts from one source.
3. **Per IP** for signup — `"signup:{ip}"` — stops brute-forcing the closed-beta invite key via repeated signup attempts.

A successful login clears both the per-account and per-IP login keys for that IP, so a legitimate user is never penalized by their own past failures.

**Important operational note:** The limiter is in-memory and per-process. It resets on server restart. A multi-worker deployment would need Redis. This is documented in the source comments.

### Pydantic Models

---

#### `SignupBody`

```python
class SignupBody(BaseModel):
    beta_key: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    email: str
    password: str = Field(min_length=8, max_length=200)
    consent: bool = False
```

Fields:
- `beta_key` — the closed-beta invite key; must be non-empty (Pydantic rejects empty string)
- `name` — display name; 1–80 characters
- `email` — email address string; format is validated server-side by `_EMAIL_RE` after Pydantic accepts it
- `password` — minimum 8 characters, maximum 200 characters (prevents bcrypt input length attacks)
- `consent` — age-requirement attestation (18+, or 13+ with parental permission); defaults to `False`; must be `True` to proceed

---

#### `LoginBody`

```python
class LoginBody(BaseModel):
    email: str
    password: str
```

No length constraints enforced by Pydantic at this level; the handler normalizes email and delegates all further validation to `verify_password`.

---

#### `ProfileBody`

```python
class ProfileBody(BaseModel):
    age: str | None = None
    experience: str | None = None
    goal: str | None = None
    timeline: str | None = None
    emotional: str | None = None
```

All fields optional. The age field is a string (to match the front-end's form value) and is cast to `int` in the handler for age-floor validation.

### Private Functions

---

### `_client_ip`

```python
def _client_ip(request: Request) -> str
```

**Parameters:**
- `request: Request` — the FastAPI/Starlette request object

**Returns:** `str` — the best-effort client IP address.

**What it does:** Reads the `X-Forwarded-For` header; if present, returns the first (leftmost) IP in the comma-separated list, which is the original client as set by the hosting proxy (Render/Railway/Cloudflare). Falls back to `request.client.host` (the raw socket peer), then to `"unknown"` if the client is absent.

**Security relevance:** Used as part of rate-limit keys. Taking only the first XFF hop prevents a client from injecting a fake IP into the header to bypass a ban — the proxy always prepends the real client IP before any attacker-controlled values.

---

### `_check_locked`

```python
def _check_locked(key: str, max_fails: int, window: int) -> None
```

**Parameters:**
- `key: str` — rate-limit bucket key (e.g. `"login:1.2.3.4:user@example.com"`)
- `max_fails: int` — threshold before 429 is raised
- `window: int` — rolling window in seconds

**Returns:** `None` (raises on lockout).

**What it does (step by step):**
1. Gets or creates a `deque` for `key` in `_fails`.
2. Pops entries from the front of the deque that are older than `window` seconds.
3. If `len(dq) >= max_fails`: computes `retry = int(window - (now - dq[0])) + 1` (seconds until oldest failure ages out), raises `HTTPException(429)` with `Retry-After: {retry}` header.

**Security relevance:** Called before any password or invite-key comparison, so the attacker is blocked before consuming any bcrypt compute cycles.

---

### `_record_fail`

```python
def _record_fail(key: str) -> None
```

**Parameters:**
- `key: str` — rate-limit bucket key

**Returns:** `None`.

**What it does:** Appends `time.time()` to the deque for `key`. Called after a failed login or signup attempt.

---

### `_clear_fails`

```python
def _clear_fails(*keys: str) -> None
```

**Parameters:**
- `*keys: str` — one or more rate-limit bucket keys to clear

**Returns:** `None`.

**What it does:** Removes all failure history for each given key from `_fails`. Called on successful login to reset both the per-account and per-IP counters for that user/IP combination, so a legitimate user is not penalized.

---

### `hash_password`

```python
def hash_password(plain: str) -> str
```

**Parameters:**
- `plain: str` — the plaintext password

**Returns:** `str` — the bcrypt hash (includes salt; each call produces a unique hash).

**What it does:** Encodes `plain` to UTF-8, calls `bcrypt.hashpw` with a fresh `bcrypt.gensalt()`, and decodes the result to a UTF-8 string for storage.

**Security relevance:** bcrypt is intentionally slow (cost factor controlled by `gensalt()`). Each call generates a new random salt, so identical passwords produce different hashes. The plaintext is never stored or logged.

---

### `verify_password`

```python
def verify_password(plain: str, hashed: str) -> bool
```

**Parameters:**
- `plain: str` — plaintext password from the login attempt
- `hashed: str` — bcrypt hash stored in the database

**Returns:** `bool` — `True` if the password matches.

**What it does:** Encodes both strings to UTF-8 and calls `bcrypt.checkpw`. Catches `ValueError` and `TypeError` (malformed hash) and returns `False` instead of raising.

**Security relevance:** `bcrypt.checkpw` is constant-time relative to the hash computation, preventing timing-based password extraction. The try/except prevents malformed hash values in the database from causing unhandled exceptions that could leak information.

---

### `_make_token`

```python
def _make_token(email: str, tier: str) -> str
```

**Parameters:**
- `email: str` — the account email (becomes the JWT `sub` claim)
- `tier: str` — the account tier slug (stored in the JWT as `tier` claim)

**Returns:** `str` — a signed JWT string.

**What it does:** Builds a payload dict with claims `sub`, `tier`, `iat` (issued-at, UTC), and `exp` (expiry, UTC now + `config.SESSION_TTL_SECONDS`). Encodes with `jwt.encode(..., config.SECRET_KEY, algorithm="HS256")`.

**Security relevance:** The `iat` claim is used by `current_user` to implement JWT revocation by comparing against `token_valid_after`. The `tier` claim is embedded in the token so the server does not need a DB lookup to know the tier on data requests — but `current_user` re-reads from the DB to confirm the account still exists, so a deleted account is always rejected.

---

### `_set_session_cookie`

```python
def _set_session_cookie(response: Response, token: str) -> None
```

**Parameters:**
- `response: Response` — the outgoing FastAPI response
- `token: str` — the JWT string to store in the cookie

**Returns:** `None`.

**What it does:** Calls `response.set_cookie` with:
- `key="tf_session"`
- `value=token`
- `max_age=config.SESSION_TTL_SECONDS` (604800; 7 days)
- `httponly=True` — cookie is invisible to JavaScript
- `secure=config.PRODUCTION` — only sent over HTTPS in production; `False` locally so `http://localhost` works
- `samesite="lax"` — sent on top-level navigations but not on cross-site POST requests (CSRF defense)
- `path="/"` — cookie is sent on all paths

**Security relevance:** The three cookie flags (`httponly`, `secure`, `samesite`) together prevent the three main session theft vectors: XSS (cannot read the cookie), network eavesdropping (HTTPS-only in production), and cross-site request forgery (SameSite=Lax blocks cross-origin POST).

---

### `_public_user`

```python
def _public_user(user: dict) -> dict
```

**Parameters:**
- `user: dict` — full account dict as returned by `db.get_user` (includes `pass_hash`)

**Returns:** `dict` — safe subset of the account for sending to the browser.

**What it does:** Constructs and returns a new dict with only: `email`, `name`, `tier`, `tier_name` (looked up from `config.TIERS`), `a11y`, and `profile`. The `pass_hash`, `created`, and `token_valid_after` fields are deliberately excluded.

**Security relevance:** Central stripping point. Every endpoint that returns user data calls this function, ensuring the bcrypt hash is never accidentally leaked to the browser.

---

### `current_user`

```python
def current_user(tf_session: str | None = Cookie(default=None)) -> dict
```

**Parameters:**
- `tf_session: str | None` — the value of the `tf_session` cookie, injected by FastAPI's dependency injection from the request's cookie jar

**Returns:** `dict` — the full account row (including `pass_hash`) for use by the calling handler. Handlers that return data to the browser must pass the result through `_public_user`.

**What it does (step by step):**
1. If `tf_session` is `None` (cookie absent): raises `HTTPException(401, "Not authenticated")`.
2. Decodes and verifies the JWT using `config.SECRET_KEY` and `HS256`. On any `jwt.PyJWTError` (invalid signature, expired, malformed): raises `HTTPException(401, "Invalid or expired session")`.
3. Looks up the account via `db.get_user(payload["sub"])`. If not found: raises `HTTPException(401, "Account not found")`.
4. Compares `payload["iat"]` (issued-at) against `user["token_valid_after"]`. If `iat < token_valid_after`: raises `HTTPException(401, "Session revoked")`.
5. Returns the full user dict.

**Security relevance:** This function is the single enforcement point for authentication. It is declared as a FastAPI `Depends(current_user)` dependency on every protected endpoint. It enforces: cookie presence, JWT signature validity, JWT expiry, account existence, and JWT revocation. An attacker who steals a valid JWT is blocked the moment the legitimate user logs out (because logout bumps `token_valid_after`).

### Auth Endpoints

---

### `POST /api/auth/signup`

```python
@router.post("/signup")
def signup(body: SignupBody, request: Request, response: Response)
```

**Auth required:** No (public).

**What it does (step by step):**
1. Constructs the signup rate-limit key `"signup:{client_ip}"` and calls `_check_locked` (10 fails / 1 hour per IP). Raises 429 if locked.
2. Compares `body.beta_key.strip()` against `config.BETA_KEY` using `hmac.compare_digest` (constant-time). If mismatch: calls `_record_fail`, raises 403.
3. If `body.consent` is `False`: raises 400.
4. Normalizes `email = body.email.strip().lower()`. If it does not match `_EMAIL_RE`: raises 400.
5. Calls `db.get_user(email)`. If an account exists: raises 409.
6. Calls `db.create_user(email, name, hash_password(body.password), config.DEFAULT_TIER, today)`.
7. Calls `_make_token` and `_set_session_cookie` to issue a session immediately.
8. Returns `{"user": _public_user(...)}`.

**Returns:** `{"user": {...}}` — the safe public user dict.

**Security relevance:** `hmac.compare_digest` prevents timing attacks on the invite key. Signup rate limit prevents brute-forcing the invite key. Consent check is server-side (cannot be skipped from browser). Generic conflict message on duplicate email does not reveal which emails exist.

---

### `POST /api/auth/login`

```python
@router.post("/login")
def login(body: LoginBody, request: Request, response: Response)
```

**Auth required:** No (public).

**What it does (step by step):**
1. Normalizes `email = body.email.strip().lower()`.
2. Computes `ip = _client_ip(request)`.
3. Constructs rate-limit keys `k_user = "login:{ip}:{email}"` and `k_ip = "login_ip:{ip}"`.
4. Calls `_check_locked(k_user, 5, 900)` — per-account limit. Raises 429 if locked.
5. Calls `_check_locked(k_ip, 20, 900)` — per-IP limit. Raises 429 if locked.
6. Calls `db.get_user(email)`. If not found, or if `verify_password` returns `False`: records failure on both keys, raises 401 with a generic `"Incorrect email or password"` message (same message for both cases to avoid user enumeration).
7. On success: calls `_clear_fails(k_user, k_ip)`.
8. Calls `_make_token` and `_set_session_cookie`.
9. Returns `{"user": _public_user(user)}`.

**Returns:** `{"user": {...}}` — the safe public user dict.

**Security relevance:** Two-level rate limiting (per-account and per-IP). Unified error message prevents account enumeration. Failure counters are cleared on success so legitimate users never get locked out. bcrypt comparison is constant-time.

---

### `POST /api/auth/logout`

```python
@router.post("/logout")
def logout(response: Response, tf_session: str | None = Cookie(default=None))
```

**Auth required:** No (intentionally — a logged-out user must be able to call this; invalid cookies are handled gracefully).

**What it does (step by step):**
1. If `tf_session` is present:
   a. Decodes the JWT (without raising — `jwt.PyJWTError` is silently passed).
   b. If `sub` (email) is valid and the account exists: calls `db.update_token_valid_after(email, int(time.time()))` to bump the validity epoch, immediately invalidating all outstanding tokens for that account.
2. Calls `response.delete_cookie(COOKIE_NAME, path="/")` to clear the session cookie in the browser.
3. Returns `{"ok": True}`.

**Returns:** `{"ok": True}`.

**Security relevance:** Two-layer logout: cookie deletion (browser) and JWT revocation (server-side `token_valid_after`). The second layer ensures a stolen token is invalidated on logout, not just at expiry. The try/except silently handles invalid or already-expired cookies so logout always succeeds from the browser's perspective.

---

### `GET /api/auth/me`

```python
@router.get("/me")
def me(user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**What it does:** Returns the currently authenticated account.

**Returns:** `{"user": _public_user(user)}`.

**Usage:** Called by the front-end on page load to check whether a session cookie is still valid. If the user is not logged in, `current_user` raises 401 and the front-end redirects to login.

---

### `POST /api/auth/profile`

```python
@router.post("/profile")
def save_profile(body: ProfileBody, user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**What it does (step by step):**
1. Casts `body.age` to `int` (catches `TypeError`/`ValueError`, defaults to `0`).
2. If `age < 13`: raises 400 `"You must be at least 13 years old to use ThinkFree"`.
3. If `age > 120`: raises 400 `"Enter a valid age"`.
4. Calls `db.update_profile(user["email"], body.model_dump())`.
5. Re-fetches the updated account and returns `{"user": _public_user(...)}`.

**Returns:** `{"user": {...}}` — updated public user dict.

**Security relevance:** Age floor is enforced server-side (COPPA compliance baseline). Cannot be bypassed by sending a manipulated request from the browser.

---

### `POST /api/auth/a11y`

```python
@router.post("/a11y")
def save_a11y(on: bool, user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**Parameters (query/body):**
- `on: bool` — enable (`True`) or disable (`False`) accessibility mode

**What it does:** Calls `db.update_a11y(user["email"], on)`.

**Returns:** `{"ok": True}`.

---

## 8. File: `data.py`

**Responsibility:** Gated data endpoints. The large datasets that previously shipped as publicly-accessible `webapp/js/*_data.js` files have been moved to `private_data/` (never web-served). This module serves them only to authenticated users. Anonymous requests receive 401. Per-tier refresh cadence and a market-hours gate are enforced server-side.

All routes are mounted under the prefix `/api/data`.

### Dataset Organization

Datasets are organized in `private_data/manifest.json` (read by `_manifest()`) into three named lists:

| Manifest key | Used by endpoint | Description |
|---|---|---|
| `core` | `GET /api/data/bundle` | Datasets the dashboard needs immediately after login |
| `lazy` | `GET /api/data/state` | Large state-legislature datasets, loaded on demand |
| `live` | `GET /api/data/live` | Price and news data, refreshed per tier cadence |

### Module-Level State

| Constant / Variable | Type | Purpose |
|---|---|---|
| `_last_live` | `dict[str, float]` | In-memory map of `email -> unix timestamp` of last successful `/live` pull; enforces tier cadence |

Like the auth rate-limiter, `_last_live` is in-memory and per-process. It resets on restart and is noted in the source as a Redis candidate for multi-worker deployments.

### Private Functions

---

### `_manifest`

```python
def _manifest() -> dict
```

**Parameters:** None.

**Returns:** `dict` — the parsed contents of `private_data/manifest.json`.

**What it does:** Constructs the path `config.PRIVATE_DATA_DIR / "manifest.json"`. If the file does not exist, raises `HTTPException(503, "Data not built yet. Run scripts/extract_data_to_json.py")`. Otherwise reads and JSON-parses the file.

**Side effects:** File I/O on every call (not cached). The manifest is small so this is not a bottleneck.

---

### `_load`

```python
@lru_cache(maxsize=64)
def _load(global_name: str) -> str
```

**Parameters:**
- `global_name: str` — the dataset name (matches a JSON file in `private_data/` without extension)

**Returns:** `str` — the raw JSON text of the dataset.

**Decorator:** `@lru_cache(maxsize=64)` — the dataset text is cached in memory after the first disk read. Since the data files are large and static (rebuilt by offline scripts, not by the server), caching eliminates repeated disk I/O for the most common datasets.

**What it does:** Constructs the path `config.PRIVATE_DATA_DIR / f"{global_name}.json"`. If the file does not exist, raises `HTTPException(404, f"Unknown dataset: {global_name}")`. Otherwise reads and returns the raw text (not parsed).

**Design choice:** Returns raw JSON string, not a parsed object, to avoid a parse + re-serialize round trip when assembling the bundle response.

---

### `_bundle_json`

```python
def _bundle_json(names: list[str]) -> str
```

**Parameters:**
- `names: list[str]` — list of dataset names to bundle

**Returns:** `str` — a single JSON object string with each dataset name as a key mapped to its dataset.

**What it does:** For each name, calls `_load(name)` to get the raw JSON text, then constructs `"name":rawJSON` pairs and joins them into `{pair1,pair2,...}`. This produces a valid JSON object without ever deserializing and re-serializing the large dataset payloads.

---

### `_market_open`

```python
def _market_open(now: dt.datetime | None = None) -> bool
```

**Parameters:**
- `now: dt.datetime | None` — if provided, uses this datetime instead of the real current time (for testing)

**Returns:** `bool` — `True` if US equity markets are currently open.

**What it does:**
1. Imports `zoneinfo.ZoneInfo` and creates an `America/New_York` timezone-aware datetime (current time if `now` is not provided).
2. If today is Saturday or Sunday (`weekday() >= 5`): returns `False`.
3. Computes `minutes = hour * 60 + minute`. Market hours are 09:30–16:00 ET, which is `570 <= minutes < 960`.
4. Returns `True` if within those bounds.

**Error handling:** If `zoneinfo` is unavailable (missing system timezone data), the `except Exception` clause returns `True` (does not block refreshes) to fail open rather than erroneously blocking legitimate requests.

**Used by:** The `/live` endpoint to gate lower-tier users during off-hours.

### Data Endpoints

---

### `GET /api/data/bundle`

```python
@router.get("/bundle")
def bundle(user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**What it does:**
1. Calls `_manifest()` to get the dataset lists.
2. Calls `_bundle_json(m["core"])` to assemble all core datasets into a single JSON object string.
3. Returns a `Response` with `media_type="application/json"` and the raw JSON string as the body.

**Returns:** JSON object containing all core datasets needed to render the app shell.

**Security:** Requires a valid session cookie. Returns 401 if unauthenticated, 503 if the data has not been built yet.

---

### `GET /api/data/state`

```python
@router.get("/state")
def state(user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**What it does:**
1. Calls `_manifest()`.
2. Calls `_bundle_json(m["lazy"])` to assemble the state-legislature datasets.
3. Returns a `Response` with `media_type="application/json"`.

**Returns:** JSON object containing LegiScan + Open States data.

**Design:** These datasets are large and loaded lazily — the front-end calls this endpoint only when the user navigates to the State Legislature view, rather than on initial load.

---

### `GET /api/data/live`

```python
@router.get("/live")
def live(user: dict = Depends(current_user))
```

**Auth required:** Yes (`current_user` dependency).

**What it does (step by step):**
1. Looks up the user's tier in `config.TIERS` (falls back to `DEFAULT_TIER` if tier slug is unknown).
2. Gets `refresh_min = tier["refresh_min"]`.
3. **Market-hours gate:** If `refresh_min > 30` (i.e., tier is `"hourly"` or `"free"`) AND `_market_open()` is `False`: returns `{"paused": True, "reason": "market_closed"}` immediately without consuming a refresh slot.
4. **Cadence enforcement:** Computes `wait = refresh_min * 60 - (now - _last_live[user["email"]])`. If `wait > 0`: raises `HTTPException(429, f"Refresh available in {int(wait)}s")` with `Retry-After: {wait}` header.
5. Records `_last_live[user["email"]] = now`.
6. Calls `_manifest()` and `_bundle_json(m["live"])`.
7. Returns a `Response` with `media_type="application/json"`.

**Returns:** JSON object with current prices and news data, or `{"paused": True, "reason": "market_closed"}`.

**Rate-limit behavior by tier:**

| Tier | `refresh_min` | Market-hours gate applies? |
|---|---|---|
| `free` | 1440 (24 hrs) | Yes (> 30 min) |
| `hourly` | 60 | Yes (> 30 min) |
| `half` | 30 | No (== 30 min) |
| `live` | 15 | No (< 30 min) |
| `beta` | 15 | No (< 30 min) |

**Security:** Both the cadence and the market-hours gate are enforced server-side. The browser cannot bypass them by modifying JavaScript or sending extra requests — the server tracks `_last_live` per user email.

---

## 9. File: `main.py`

**Responsibility:** The application entry point. Creates the FastAPI app instance, wires up routers and middleware, mounts static file directories, and defines two simple top-level routes (`/healthz` and `/`). Also enforces the startup guard (refuse to run in production with a placeholder secret).

### Startup Guard

```python
# main.py:31-32
if config.PRODUCTION and config.is_placeholder_secret():
    raise RuntimeError("TF_SECRET_KEY is unset/placeholder. ...")
```

Called at module load time (before the ASGI server accepts any connections). If `TF_PRODUCTION=1` is set but `TF_SECRET_KEY` is still the default placeholder, the process exits with `RuntimeError`. This prevents a misconfigured production deploy from silently running with a guessable signing key.

### FastAPI Instance

```python
app = FastAPI(title="ThinkFree Finance", docs_url=None, redoc_url=None, openapi_url=None)
```

`docs_url=None`, `redoc_url=None`, `openapi_url=None` — all auto-generated API documentation endpoints are disabled. The interactive Swagger UI and OpenAPI schema are not accessible in any environment.

### Initialization Sequence

```python
db.init_db()          # Create/migrate the SQLite users table
app.include_router(auth.router)   # Mount /api/auth/*
app.include_router(data.router)   # Mount /api/data/*
```

These three lines run at import time, before the ASGI server starts accepting requests.

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
```

**Configuration details:**
- `allow_origins` — from `config.ALLOWED_ORIGINS` (env-configured, not `"*"`)
- `allow_credentials=True` — required because the session travels in a cookie; this means the wildcard `"*"` origin is forbidden by the CORS spec and would cause an error
- `allow_methods` — only `GET`, `POST`, and `OPTIONS` (no `PUT`, `DELETE`, `PATCH`)
- `allow_headers` — only `Content-Type`

The source comment notes: in the recommended single-server setup, the front-end and API share one origin, so the browser never makes a cross-origin request and this middleware is effectively inert. It is present for deployments where the front-end is hosted on a different domain.

### Blocked Path Constants

```python
_BLOCKED_SUFFIXES = ("_data.js", "news_intel.js", "member_bills.js")
```

A tuple of filename suffixes that must never be served directly. Even if copies of these files still exist under `webapp/js/` (during the migration from the old public-data architecture), the middleware returns 404 before the static file handler can serve them.

### Middleware

---

### `security_and_blocklist`

```python
@app.middleware("http")
async def security_and_blocklist(request: Request, call_next)
```

**Decorator:** `@app.middleware("http")` — applied to every HTTP request and response.

**Parameters:**
- `request: Request` — the incoming ASGI request
- `call_next` — callable; passes the request to the next handler in the stack

**Returns:** A `Response` object.

**What it does (step by step):**

**Step 0 — Production HTTPS redirect** (applied before path checks):
- If `config.PRODUCTION` is `True` AND the path is not `"/healthz"` (health check is exempted to avoid redirecting the load balancer probe):
  - Reads the `X-Forwarded-Proto` header (set by the TLS-terminating proxy). Takes the first value (before any comma), strips whitespace. Defaults to `"https"` when the header is absent (so a direct HTTPS hit is never redirected).
  - If the scheme is `"http"`: returns `RedirectResponse` to the same URL with `scheme="https"` and HTTP **308** (Permanent Redirect, preserving the request method).

**Step 1 — Blocked path enforcement:**
- If the path starts with `"/js/"` AND ends with any of `_BLOCKED_SUFFIXES`: returns `JSONResponse({"detail": "Not found"}, status_code=404)`.
- This blocks direct browser access to `*_data.js`, `news_intel.js`, and `member_bills.js` regardless of where the files sit on disk.

**Step 2 — Pass to next handler:**
- Calls `await call_next(request)` to execute the actual route handler or static file handler.

**Step 3 — Security headers (applied to all responses):**

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents browsers from MIME-sniffing responses away from the declared content type |
| `X-Frame-Options` | `DENY` | Prevents the app from being embedded in any iframe (clickjacking defense) |
| `Referrer-Policy` | `no-referrer` | Suppresses the `Referer` header on all outgoing requests, preventing URL leakage |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disables access to sensitive browser APIs |
| `Content-Security-Policy` | See below | Restricts resource loading to trusted sources |

**CSP value:**
```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self'
```
- Scripts: only from the same origin (no CDN, no inline scripts)
- Styles: same origin plus `'unsafe-inline'` (because the UI uses `style=""` attributes)
- Images: same origin, `data:` URIs, and any `https:` URL
- `frame-ancestors 'none'`: reinforces X-Frame-Options at the CSP level
- `base-uri 'self'`: prevents base-tag injection attacks

**Step 4 — HSTS (production only):**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```
Applied only when `config.PRODUCTION` is `True`. Instructs browsers to only contact the server over HTTPS for the next 365 days, including all subdomains.

### Static Mounts

```python
app.mount("/css", StaticFiles(directory=config.WEBAPP_DIR / "css"), name="css")
app.mount("/js",  StaticFiles(directory=config.WEBAPP_DIR / "js"),  name="js")
```

Serves `webapp/css/*` at `/css/*` and `webapp/js/*` at `/js/*`. The `_BLOCKED_SUFFIXES` check in the middleware intercepts requests for blocked filenames before they reach these handlers.

### Top-Level Routes

---

### `GET /healthz`

```python
@app.get("/healthz")
def healthz()
```

**Auth required:** No.

**What it does:** Returns `{"ok": True}`.

**Returns:** JSON `{"ok": True}`.

**Purpose:** Simple liveness probe for the hosting platform's load balancer or health-check system. Deliberately exempted from the HTTPS redirect (step 0 of the middleware) so the host's HTTP probe is never redirected.

---

### `GET /`

```python
@app.get("/")
def index()
```

**Auth required:** No (the HTML shell itself is public; data is gated behind `/api/data/*`).

**What it does:** Returns `FileResponse(config.WEBAPP_DIR / "index.html")`.

**Returns:** The `webapp/index.html` app shell.

**Design:** The shell HTML contains no data and no secrets. It loads JS and CSS, checks for a session cookie via `GET /api/auth/me`, and redirects to login if unauthenticated. All actual data is fetched from the authenticated `/api/data/*` endpoints after login.

---

## 10. Endpoints Quick-Reference Table

| Method | Path | Handler | Auth Required | Returns |
|---|---|---|---|---|
| `GET` | `/healthz` | `main.healthz` | No | `{"ok": True}` |
| `GET` | `/` | `main.index` | No | `webapp/index.html` (FileResponse) |
| `POST` | `/api/auth/signup` | `auth.signup` | No | `{"user": {...}}` + sets session cookie |
| `POST` | `/api/auth/login` | `auth.login` | No | `{"user": {...}}` + sets session cookie |
| `POST` | `/api/auth/logout` | `auth.logout` | No (graceful) | `{"ok": True}` + clears cookie, revokes JWT |
| `GET` | `/api/auth/me` | `auth.me` | Yes | `{"user": {...}}` |
| `POST` | `/api/auth/profile` | `auth.save_profile` | Yes | `{"user": {...}}` (updated) |
| `POST` | `/api/auth/a11y` | `auth.save_a11y` | Yes | `{"ok": True}` |
| `GET` | `/api/data/bundle` | `data.bundle` | Yes | JSON bundle of core datasets |
| `GET` | `/api/data/state` | `data.state` | Yes | JSON bundle of state-legislature datasets |
| `GET` | `/api/data/live` | `data.live` | Yes | JSON bundle of live data, or `{"paused": True, "reason": "market_closed"}` |
| `GET` | `/css/*` | StaticFiles | No | CSS files from `webapp/css/` |
| `GET` | `/js/*_data.js` | Middleware blocklist | — | 404 (blocked) |
| `GET` | `/js/news_intel.js` | Middleware blocklist | — | 404 (blocked) |
| `GET` | `/js/member_bills.js` | Middleware blocklist | — | 404 (blocked) |
| `GET` | `/js/*` (other) | StaticFiles | No | JS files from `webapp/js/` |

**Notes:**
- `docs_url`, `redoc_url`, and `openapi_url` are all set to `None` — no auto-generated documentation is accessible.
- All CORS is scoped to `config.ALLOWED_ORIGINS` (never `"*"`).
- All endpoints except `/healthz` are subject to the security headers middleware.

---

## 11. Security Architecture Summary

This section synthesizes the security mechanisms across all files into a single reference.

### Authentication Flow

```
Browser                         Server
  │                               │
  │  POST /api/auth/login         │
  │  {email, password}  ────────► │  1. Check brute-force limits
  │                               │  2. db.get_user(email)
  │                               │  3. bcrypt.checkpw(password, hash)
  │                               │  4. jwt.encode(sub, tier, iat, exp)
  │  ◄──── Set-Cookie: tf_session │  5. response.set_cookie(httpOnly, Secure, SameSite=Lax)
  │                               │
  │  GET /api/data/bundle         │
  │  Cookie: tf_session ────────► │  1. jwt.decode(cookie, SECRET_KEY)
  │                               │  2. db.get_user(sub) → account exists?
  │                               │  3. payload.iat >= user.token_valid_after?
  │                               │  4. tier → check cadence / market hours
  │  ◄──── JSON datasets          │  5. _bundle_json(core datasets)
```

### Security Controls Index

| Control | Location | Mechanism |
|---|---|---|
| Password hashing | `auth.py:hash_password` | bcrypt with random salt; `bcrypt.gensalt()` per call |
| Password verification | `auth.py:verify_password` | `bcrypt.checkpw` (constant-time); exception-safe |
| Session token | `auth.py:_make_token` | JWT signed HS256 with `TF_SECRET_KEY`; 7-day expiry |
| Cookie security | `auth.py:_set_session_cookie` | `httpOnly=True`, `Secure=PRODUCTION`, `SameSite=lax` |
| JWT revocation | `db.py:update_token_valid_after` + `auth.py:current_user` | `token_valid_after` epoch; bumped on logout |
| Invite-key comparison | `auth.py:signup` | `hmac.compare_digest` (constant-time; prevents timing attacks) |
| Login brute-force | `auth.py:_check_locked` | Rolling-window deque; per (IP+account) and per-IP |
| Signup brute-force | `auth.py:_check_locked` | Rolling-window deque; per IP |
| User enumeration | `auth.py:login` | Single generic error for wrong email OR wrong password |
| Age floor | `auth.py:save_profile` | Server-side: `age < 13` → 400 |
| Consent | `auth.py:signup` | Server-side: `consent == False` → 400 |
| Password stripping | `auth.py:_public_user` | Removes `pass_hash` before any data leaves the server |
| Startup secret guard | `main.py:31-32` | Refuses to start in production with placeholder key |
| Data file blocklist | `main.py:security_and_blocklist` | 404 for `*_data.js`, `news_intel.js`, `member_bills.js` |
| HTTPS redirect | `main.py:security_and_blocklist` | 308 redirect for `X-Forwarded-Proto: http` in production |
| Security headers | `main.py:security_and_blocklist` | X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP, HSTS |
| CORS | `main.py` | Explicit allow-list; never `"*"`; credentials allowed |
| OpenAPI docs | `main.py` | All disabled (`docs_url=None`, etc.) |
| SQL injection | `db.py` (all functions) | Parameterized queries throughout; no string interpolation |
| Per-tier cadence | `data.py:live` | In-memory `_last_live` enforced server-side |
| Market-hours gate | `data.py:_market_open` | DST-aware America/New_York check; blocks lower tiers after hours |
| Secrets in env | `config.py:_get` | All sensitive values read from environment variables only |
| Database gitignored | `server/.gitignore` | `users.db` never committed |
| `.env` gitignored | `server/.gitignore` | `.env` never committed |
