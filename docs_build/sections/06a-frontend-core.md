# Part 6A — Frontend Reference: Core (boot.js, auth.js, app.js)

This document is a complete, function-by-function reference for the three JavaScript files that form the entire operational spine of the ThinkFree Finance static webapp. Every function is documented with its signature, parameter types, return value, step-by-step behavior, side effects, and design rationale. Line citations use the format `file:line`.

---

## Table of Contents

1. [Script Load Order and HTML Structure](#1-script-load-order-and-html-structure)
2. [boot.js — Bootstrap and Dual-Mode Orchestrator](#2-bootjs--bootstrap-and-dual-mode-orchestrator)
3. [auth.js — Beta Gate, Session, and Tier Model](#3-authjs--beta-gate-session-and-tier-model)
4. [app.js — Main Controller, Router, and View Renderer](#4-appjs--main-controller-router-and-view-renderer)
5. [Window Globals Cross-Reference](#5-window-globals-cross-reference)

---

## 1. Script Load Order and HTML Structure

### 1.1 The HTML Shell (`index.html`)

`index.html` (`webapp/index.html`) is a single-page shell. Its `<body>` starts with `class="tf-locked"` applied statically — this hides all app content before any JavaScript runs (`index.html:9`). It contains:

- **`#tf-splash`** (`index.html:10–14`): A static, CSS-animated loading logo rendered by the browser immediately, before any JS. Removed by `killSplash()` in `auth.js`.
- **`.app`** (sidebar + `.main`): The full application chrome — sidebar nav, user chip, dark-mode toggle, top bar with greeting and search input, the viewport with eleven `<section class="page">` elements (one per route), and the shared modal overlay.
- **`#modal` / `#modalBox` / `#modalContent`** (`index.html:112–117`): The shared detail overlay used for politician profiles, bill details, stock details, trades views, event details, and the accessibility statement.
- **`#ticker`** (`index.html:75`): An empty `<div>` where `initTicker()` in `app.js` injects the scrolling market ticker.
- **`#tf-updated-slot`** (`index.html:68`): A `<div>` in the sidebar footer where `auth.js`'s `stampEl()` injects the live-data status line.

### 1.2 Script Load Order

Three `<script defer>` tags at the bottom of `<body>` (`index.html:125–129`):

```
1. js/boot.js        — IIFE; runs immediately at eval time; sets window.TFBoot
2. js/auth_seed.js   — local-only / gitignored dev helper; absent on server (404, harmless)
3. js/auth.js        — IIFE; runs immediately; sets window.Auth; calls boot() on DOMContentLoaded
```

Because all three use `defer`, they evaluate in document order after the DOM is parsed but before `DOMContentLoaded` fires. The data scripts (`js/*_data.js`) and all logic scripts (`js/scores.js`, `js/app.js`, etc.) are **not** present as static `<script>` tags; they are injected dynamically by `boot.js`'s `ensureAppLoaded()` only after authentication, which is why the old list of `<script>` tags was removed from `index.html` (see the comment at `index.html:119–124`).

### 1.3 Evaluation-Time Data Capture

Every logic script captures its data globals into a module-level `const` at script-eval time. For example, `app.js` line 15:

```js
const D = window.TF_DATA || {};
```

This is the central design constraint that drives boot.js's entire architecture: if `app.js` evaluates before `window.TF_DATA` exists, `D` is permanently `{}` for the lifetime of the page. Boot.js guarantees that all `window.*_DATA` globals are populated **before** any logic script is injected.

---

## 2. boot.js — Bootstrap and Dual-Mode Orchestrator

**File:** `webapp/js/boot.js`  
**Structure:** A single IIFE (`"use strict"; (function(){ ... })()`), with `window.TFBoot` as its only export.  
**Purpose:** Detect whether the app is running under the FastAPI backend ("server" mode) or as a plain static file ("static" mode), then orchestrate loading all data globals and logic scripts in the correct order, after authentication.

### 2.1 Module-Level Constants

#### `DATA_SCRIPTS` (boot.js:34–39)

```js
const DATA_SCRIPTS = [
  "js/data.js", "js/influence_data.js", "js/relationships_data.js", "js/nonprofit_data.js",
  "js/fec_data.js", "js/sec_data.js", "js/secbulk_data.js", "js/usaspending_data.js",
  "js/states_data.js", "js/sp500_data.js", "js/quant_data.js", "js/member_bills.js",
  "js/prices_data.js", "js/news_intel.js",
];
```

An ordered list of data script paths. Each file, when evaluated, assigns a `window.*_DATA` global (e.g., `window.TF_DATA`, `window.PRICES_DATA`, `window.NEWS_INTEL`). In **static mode** these are injected as `<script>` tags (in this exact order) so that each global exists before the next file executes. In **server mode** these files are 404-blocked by `server/main.py`; the same globals are populated from `/api/data/bundle` and `/api/data/live` API responses instead.

**Not in this list:** `js/legiscan_data.js` and `js/openstates_data.js`. Those are ~4.5 MB combined and are lazy-loaded by `app.js`'s `ensureStateData()` only on the first visit to the State Rankings page.

#### `LOGIC_SCRIPTS` (boot.js:45–49)

```js
const LOGIC_SCRIPTS = [
  "js/scores.js", "js/genimpact.js", "js/app.js", "js/influenceweb.js",
  "js/usmap_paths.js", "js/congress.js", "js/glossary.js", "js/scoreinfo.js",
  "js/predictions.js",
];
```

Scripts that read the window globals populated by `DATA_SCRIPTS`. Loaded in both modes, always after data globals exist, in this order to preserve the relative eval ordering from the old `index.html`. `js/usmap_paths.js` contains static SVG path geometry (not sensitive, not blocked by the server), so it loads normally in both modes.

---

### 2.2 Functions

#### `injectScript(src)` (boot.js:52–59)

**Signature:** `function injectScript(src: string): Promise<string>`  
**Returns:** A `Promise` that resolves with `src` when the script loads, or rejects with an `Error` if it fails.

**Behavior:**
1. Creates a new `<script>` element.
2. Sets `s.src = src`.
3. Attaches `onload` → `resolve(src)` and `onerror` → `reject(new Error(...))`.
4. Appends the element to `document.body`.

**Design note:** Appending to `body` (not `head`) ensures the script loads after the existing DOM. There is no `async` or `defer` attribute on the injected tag, so the browser loads and evaluates each script as it is appended. The sequential guarantee is enforced by `loadInOrder`, not by the tag attributes.

---

#### `loadInOrder(list)` (boot.js:63–65)

**Signature:** `async function loadInOrder(list: string[]): Promise<void>`  
**Returns:** `Promise<void>` — resolves when every script in the list has been injected and evaluated, in order.

**Behavior:**
- Iterates `list` sequentially with `for...await`. Each `await injectScript(list[i])` pauses the loop until the current script's `onload` fires before the next script tag is created.

**Design note:** This is the mechanism that makes the data-before-logic guarantee work. A `Promise.all` would inject all tags in parallel and break the eval order.

---

#### `api(path, opts)` (boot.js:70–81)

**Signature:** `async function api(path: string, opts?: {method?: string, body?: any}): Promise<{ok: boolean, status: number, data: any}>`  
**Returns:** An object `{ok, status, data}`. Never rejects (only network failures would propagate, but the surrounding callers wrap in try/catch).

**Parameters:**
- `path`: A same-origin URL path, e.g., `"/api/healthz"` or `"/api/data/bundle"`.
- `opts.method`: HTTP method; defaults to `"GET"`.
- `opts.body`: If present, serialized to JSON; `Content-Type: application/json` is added.

**Behavior:**
1. Builds a `fetch` init object with `credentials: "same-origin"` so the browser sends the session cookie on every request.
2. If `opts.body` is defined, stringifies it and adds the JSON Content-Type header.
3. Calls `fetch(path, init)`.
4. Attempts `res.json()` in a try/catch; sets `data = null` on parse failure (e.g., a 204 No Content or an HTML error page).
5. Returns `{ok: res.ok, status: res.status, data}`.

**Design note:** Callers branch on `res.status` (401/403/409/429) directly without try/catch noise. Returning `{ok, status, data}` instead of throwing keeps all error logic in the caller as readable `if` branches.

**Exported as:** `window.TFBoot.api` — consumed by `auth.js` for all `/api/auth/*` calls and by `app.js`'s `ensureStateData()`.

---

#### `detectMode()` (boot.js:86–93)

**Signature:** `async function detectMode(): Promise<"server" | "static">`  
**Returns:** `"server"` if `/api/healthz` responds with HTTP 200 OK; `"static"` otherwise.

**Behavior:**
1. `fetch("/api/healthz", { credentials: "same-origin" })`.
2. If the fetch succeeds and `res.ok` is true → `"server"`.
3. If the response is not OK (404, 500, etc.) → `"static"`.
4. If `fetch` itself throws (network error, `file://` origin blocked, CORS) → catches and returns `"static"`.

**Design note:** Three cases all collapse to "static": (a) `file://` protocol (fetch throws a TypeError), (b) a dumb static host that 404s the healthz path, (c) any network failure. Only the FastAPI backend, which explicitly handles `GET /api/healthz` with a 200, triggers server mode.

---

#### `populateData(mode)` (boot.js:112–122)

**Signature:** `async function populateData(mode: "server" | "static"): Promise<void>`

**Behavior — server mode:**
1. Calls `api("/api/data/bundle")`. If `ok` and `data` exist, `Object.assign(window, bundle.data)` — the server returns a JSON object whose keys are exactly the `window.*_DATA` names the logic scripts expect (e.g., `{TF_DATA: {...}, FEC_DATA: {...}, ...}`).
2. Calls `api("/api/data/live")`. If `ok` and `data` and `!data.paused`, `Object.assign(window, live.data)` — adds or overwrites `window.PRICES_DATA` and `window.NEWS_INTEL` with the freshest live data.
3. If `live.data.paused` is true (server-side market-hours pause), the live globals are not set for this initial load (the old data is stale, but the UI shows a "markets closed" stamp via `stamp()` in `auth.js`).

**Behavior — static mode:**
1. Calls `loadInOrder(DATA_SCRIPTS)` — injects each `js/*_data.js` as a `<script>` tag in order. Each script assigns its global (`window.TF_DATA = {...}`, etc.) as a side effect of evaluation.

---

#### `ensureAppLoaded()` (boot.js:127–137)

**Signature:** `function ensureAppLoaded(): Promise<void>`  
**Returns:** A `Promise<void>` that resolves when (a) the data globals are set, (b) all logic scripts have evaluated, and (c) `window.TF.init` is confirmed to exist.

**Behavior:**
1. **Idempotency check:** If `appLoadedPromise` is already set (a previous call was made), returns the same promise. Subsequent calls await the same single chain — no double-loading.
2. Awaits `ready` (the mode detection promise) to get the confirmed mode string.
3. Awaits `populateData(mode)`.
4. Awaits `loadInOrder(LOGIC_SCRIPTS)` — injects `scores.js`, `genimpact.js`, `app.js`, etc.
5. Guards: if `window.TF && window.TF.init` is falsy after all scripts load, throws `Error("ThinkFree app failed to initialize")`. This surfaces as the "Could not load your dashboard" error in `auth.js:unlock`.

**Side effects:**
- Appends 9+ `<script>` elements to `document.body`.
- Sets all `window.TF_DATA`, `window.PRICES_DATA`, etc. globals.
- `app.js` assigns `window.TF.init` synchronously at its eval time, making `window.TF` available immediately after `loadInOrder(LOGIC_SCRIPTS)` resolves.

**Called by:** `auth.js:unlock()` — awaited before calling `window.TF.init()`.

---

### 2.3 `window.TFBoot` Public API

Assigned at `boot.js:139–147`:

```js
window.TFBoot = {
  ready,              // Promise<"server"|"static"> — resolves once mode is known
  mode,               // "server"|"static"|null — set synchronously after ready resolves
  ensureAppLoaded,    // () => Promise<void> — idempotent boot + script loader
  api,                // (path, opts?) => Promise<{ok, status, data}>
  DATA_SCRIPTS,       // string[] — the ordered data script list (exposed for debugging)
  LOGIC_SCRIPTS,      // string[] — the ordered logic script list (exposed for debugging)
};
```

**`ready`** is the pending promise from `detectMode().then(...)`. The `.then` callback sets `TFBoot.mode` before resolving the promise, so any awaiter of `ready` can immediately read `TFBoot.mode` synchronously.

**Static mode warning:** The `.then` callback also calls `console.warn` (`boot.js:102`) with a reminder that the localStorage gate is a dev fallback, not real security.

---

## 3. auth.js — Beta Gate, Session, and Tier Model

**File:** `webapp/js/auth.js`  
**Structure:** A single IIFE (`"use strict"; (function(){ ... })()`), with `window.Auth` as its only export.  
**Purpose:** Manage the entire pre-authentication flow: login, beta key verification, account signup, behavioral-quiz profile creation, accessibility onboarding, session management, live-data refresh scheduling, and logout. The gate overlay is rendered and controlled entirely from within this IIFE; no auth HTML exists in `index.html`.

### 3.1 Module-Level Constants and Variables

#### `BETA_HASH` (auth.js:28)

```js
const BETA_HASH = "5sw0ilypx6";
```

The `cyrb53` hash of the plaintext beta invite key (`"<redacted — configured via TF_BETA_KEY>"`). In **static mode**, `cyrb53(enteredKey) === BETA_HASH` is the pre-check before the signup form is shown. In **server mode**, this constant is present but unused for the actual gate check — the plaintext key is never in the bundle; instead, the entered key is sent to `/api/auth/signup` where the server validates it in constant time.

#### `TIERS` (auth.js:44–50)

```js
const TIERS = {
  free:   { id: "free",   name: "Free",         refreshMin: 1440, price: "$0",     blurb: "Daily news briefing" },
  hourly: { id: "hourly", name: "Pro · Hourly", refreshMin: 60,   price: "$9/mo",  blurb: "Refreshes every hour" },
  half:   { id: "half",   name: "Pro · 30-min", refreshMin: 30,   price: "$19/mo", blurb: "Refreshes every 30 minutes" },
  live:   { id: "live",   name: "Pro · 15-min", refreshMin: 15,   price: "$39/mo", blurb: "Refreshes every 15 minutes - fastest feed" },
  beta:   { id: "beta",   name: "Beta Access",  refreshMin: 15,   price: "Free (beta)", blurb: "Full 15-minute access during beta" },
};
```

Each tier controls how frequently the live-data interval fires (`refreshMin` × 60 × 1000 ms). `beta` tier grants 15-minute cadence for free during the closed beta period. Prices are placeholder values, noted in source as needing to be set before launch.

**Exported as:** `window.Auth.TIERS`.

#### `LS` — localStorage Helper (auth.js:55–60)

```js
const LS = {
  get accounts() { try { return JSON.parse(localStorage.getItem("tf_accounts") || "{}"); } catch (e) { return {}; } },
  set accounts(v) { localStorage.setItem("tf_accounts", JSON.stringify(v)); },
  get session() { return localStorage.getItem("tf_session") || ""; },
  set session(v) { v ? localStorage.setItem("tf_session", v) : localStorage.removeItem("tf_session"); },
};
```

A thin abstraction over `localStorage`. The accounts object is a dictionary keyed by email address; each value holds `{ name, pass (cyrb53 hash), tier, a11y, profile, created }`. The session is a single email string pointing to the active account. Setting `session` to a falsy value removes the key entirely (used on logout).

**Design note:** `LS` is only read and written in **static mode**. In server mode, the session lives in an httpOnly cookie managed by the FastAPI backend; `LS` is never touched.

#### `E` — HTML Escaper (auth.js:63)

```js
const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
```

A minimal HTML-escaper used everywhere user-supplied text is interpolated into `innerHTML`. Guards against XSS in the auth gate views.

#### `validId` (auth.js:66)

```js
const validId = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) || /^[a-z0-9_.-]{3,}$/i.test(s);
```

Accepts either a valid email address or a simple alphanumeric username (3+ characters). Used on the login form to allow logging in by email or a username alias (e.g., `"admin"`).

#### `validEmail` (auth.js:71)

```js
const validEmail = (s) => /^[^\s@]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/i.test(s);
```

A stricter check used on the signup form. Requires a TLD of 2+ letters. Rejects obviously malformed emails like `"a@b"` or `"a@b.1"`. A real-looking email that passes this check is still subject to the async `emailDomainReal()` domain-existence check.

#### `SERVER()` (auth.js:103)

```js
const SERVER = () => !!(window.TFBoot && window.TFBoot.mode === "server");
```

A zero-argument function (not a stored value) that reads `window.TFBoot.mode` at call time. Every auth/data branch that differs between modes calls `SERVER()` to decide which path to take. Using a function rather than a constant means it correctly reflects the mode even if called before `TFBoot.ready` has settled (in which case `mode` is still `null`, and `SERVER()` returns `false`, correctly defaulting to static behavior).

#### `betaKeyEntered` (auth.js:108)

```js
let betaKeyEntered = "";
```

Carries the invite key entered in the `"beta"` view forward to the signup POST. In server mode the local cyrb53 check is skipped; the raw key string is sent to `/api/auth/signup` where the server validates it. If the server returns 403, the UI re-renders the `"beta"` view and shows the error message.

#### `currentUser` / `refreshTimer` / `unlocked` (auth.js:139)

```js
let currentUser = null, refreshTimer = null, unlocked = false;
```

- **`currentUser`**: The active account object. In static mode it is `accountFor()`'s return value (email + LS entry). In server mode it is the enriched server response from `adoptServerUser()`. Set to `null` on logout.
- **`refreshTimer`**: The `setInterval` handle for the live-data refresh loop. Stored so it can be `clearInterval`'d when the tier changes or the user logs out.
- **`unlocked`**: Boolean; `true` after successful login. The `guard()` tamper-protection checks this — once true it stops re-locking. Set to `false` on logout.

#### Immediate Lock (auth.js:144)

```js
if (document.body) document.body.classList.add("tf-locked");
```

Applied at IIFE eval time (before `DOMContentLoaded`). If `document.body` is already available (e.g., the script is in a deferred position), the class is applied immediately, hiding the app before any content renders. This is belt-and-suspenders alongside the `class="tf-locked"` already on `<body>` in the HTML.

---

### 3.2 Functions

#### `cyrb53(str, seed)` (auth.js:33–39)

**Signature:** `function cyrb53(str: string, seed?: number): string`  
**Returns:** A base-36 string hash of `str`.

**Behavior:**
- Implements the cyrb53 non-cryptographic hash algorithm. Uses two 32-bit integers, applies the MurmurHash3-style mixing of `Math.imul`, and combines them into a 53-bit integer.
- The `seed` parameter (default `0`) allows salting; it is always called without a seed in this codebase.
- Returns `(4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)` — a compact base-36 string.

**Usage:**
- `cyrb53(betaKey) === BETA_HASH` — beta key verification in static mode (`bind()`, data-act `"verify"`).
- `cyrb53(pass)` — password hashing for static-mode account storage. Passwords are stored and compared as their cyrb53 hash, never in plaintext.

**Design note:** cyrb53 is explicitly not suitable for real authentication (no salt per account, not cryptographically resistant to preimage attacks). The code comment says "Good enough for a soft gate; not suitable for real auth." Real authentication uses the FastAPI backend with bcrypt.

---

#### `emailDomainReal(email)` (auth.js:79–97)

**Signature:** `async function emailDomainReal(email: string): Promise<boolean>`  
**Returns:** `true` if the email's domain appears to exist and be able to receive mail; `false` if the domain is definitively nonexistent.

**Behavior:**
1. Extracts the domain from the email (`email.split("@")[1]`). If absent or has no `.`, returns `false`.
2. Defines a helper `ask(type)` that fetches `https://dns.google/resolve?name={domain}&type={type}` (Google DNS-over-HTTPS), returning parsed JSON or `null` on failure.
3. Calls `ask("MX")`:
   - If the DNS response is `null` (network unreachable), returns `true` — **fail open** to avoid locking out real users on flaky networks.
   - If `mx.Status === 3` (NXDOMAIN — domain does not exist in DNS), returns `false`.
   - If `mx.Answer` is non-empty, returns `true` (domain has a real mail server).
4. If MX lookup returns no answer records, falls back to an `ask("A")` lookup:
   - If `null` → `true` (fail open).
   - If `a.Answer` is non-empty → `true` (domain resolves at all, even without explicit MX).
   - Otherwise → `false`.
5. Any uncaught exception → `true` (fail open).

**Side effects:** Disables and re-enables the signup button during the async DNS lookup (`bind()`, data-act `"signup"`) to prevent double-submission.

**Design note:** The fail-open policy means a real user with a legitimate but temporarily unreachable domain is never locked out. The cost is that some nonsense domains with DNS outages might pass, but those users still require a real password and beta key, so the gate is still effective.

---

#### `adoptServerUser(u)` (auth.js:114–119)

**Signature:** `function adoptServerUser(u: object): object`  
**Returns:** The same user object, mutated with an enriched `profile` if the raw answers are present.

**Behavior:**
1. Checks if `u && u.profile && u.profile.experience`. If so, calls `computeProfile(u.profile)` and overwrites `u.profile` with the enriched result.
2. If `computeProfile` throws (e.g., malformed answers), silently keeps the raw profile.
3. Returns `u`.

**Purpose:** The server persists only the five raw profile answers (`{age, experience, goal, timeline, emotional}`). The UI expects the enriched shape produced by `computeProfile`: `{age, experience, goal, timeline, emotional, risk_tolerance, risk_score, profile_id}`. This function bridges the gap so that server-mode and static-mode sessions look identical to `app.js` — which reads `p.risk_tolerance` and `p.goal` when tailoring news.

**Called by:** All server-mode authentication responses: `boot()` (`/api/auth/me`), `login` handler (`/api/auth/login`), `signup` handler (`/api/auth/signup`), `quiz-submit` handler (`/api/auth/profile`).

---

#### `computeProfile(a)` (auth.js:125–137)

**Signature:** `function computeProfile(a: {age: string|number, experience: string, goal: string, timeline: string, emotional: string}): object`  
**Returns:** An enriched profile object: `{age, experience, goal, timeline, emotional, risk_tolerance, risk_score, profile_id}`.

**Behavior — point accumulation:**

| Condition | Points |
|---|---|
| `age < 30` | +2 |
| `30 ≤ age < 50` | +1 |
| `experience === "advanced"` | +2 |
| `experience === "intermediate"` | +1 |
| `goal === "growth"` | +2 |
| `goal === "income"` | +1 |
| `emotional === "buy more"` | +2 |
| `emotional === "hold"` | +1 |

**Risk classification:**
- `pts ≥ 7` → `"high"`
- `pts ≥ 4` → `"moderate"`
- `pts < 4` → `"low"`

**Profile ID construction:**
- `ageGroup`: `"A1_<25"` | `"A2_25-34"` | `"A3_35-50"` | `"A4_50+"`.
- `riskGroup`: `"R1_Cons"` | `"R2_Mod"` | `"R3_High"`.
- `profile_id = ageGroup + "_" + riskGroup` (e.g., `"A2_25-34_R2_Mod"`).

**Design note:** This is a client-side port of `phase1_user_personalization.py` so that the web front-end and the Python pipeline share identical scoring logic. The `profile_id` is a compact string suitable as a cache/personalization key.

**Exported as:** `window.Auth.computeProfile`.

---

#### `accountFor()` (auth.js:148–151)

**Signature:** `function accountFor(): object | null`  
**Returns:** The current session's account object with `email` merged in, or `null` if no session exists.

**Behavior:**
1. Reads `LS.accounts[LS.session]` — the stored account for the current session email.
2. If found, returns `{ email: LS.session, ...a }`.
3. If `LS.session` is empty or no matching account exists, returns `null`.

**Used by:** `enter()`, `boot()` (static path), and the `a11y-on/off` and `quiz-submit` handlers after LS mutations.

---

#### `killSplash()` (auth.js:158)

**Signature:** `function killSplash(): void`

**Behavior:** Finds `#tf-splash` by ID and removes it from the DOM. No-op if already removed. Called by `showGate()` and `unlock()`.

**Design note:** The splash screen is a pure HTML/CSS animation that the browser renders immediately during the initial parse, giving the user visual feedback before any JavaScript runs. It must be explicitly removed once auth/app takes over.

---

#### `showGate(view)` (auth.js:162–167)

**Signature:** `function showGate(view?: string): void`

**Behavior:**
1. Calls `killSplash()`.
2. If `gate` (the module-level overlay element) does not yet exist, creates a `<div class="auth-gate">` and appends it to `document.body`.
3. Sets `gate.style.display = "flex"` to make it visible.
4. Calls `render(view || "login", {})` to populate the gate with the requested view's HTML.

**Called by:** `boot()` when no valid session is found, and `logout()` after the goodbye animation finishes (to show the login view again without reloading the page).

---

#### `hideGate()` (auth.js:169)

**Signature:** `function hideGate(): void`

**Behavior:** Sets `gate.style.display = "none"` if gate exists. Not currently called in the main flow (the gate is removed from the DOM entirely on unlock); retained as a utility.

---

#### `shell(inner)` (auth.js:173–179)

**Signature:** `function shell(inner: string): string`  
**Returns:** An HTML string wrapping `inner` in the branded auth card frame.

**Behavior:** Returns the outer card structure including the "TF" logo mark, the "ThinkFree Finance" brand name, the `inner` HTML, and the legal disclaimer footer. Keeps individual view templates lean by centralizing the frame.

---

#### `render(view, ctx)` (auth.js:183–226)

**Signature:** `function render(view: "login"|"beta"|"signup"|"quiz"|"a11y", ctx: object): void`

**Behavior:** Builds the inner HTML for the requested view, wraps it in `shell()`, and assigns to `gate.innerHTML`. The five views are:

- **`"login"`**: Email + password inputs, a Log In button (`data-act="login"`), and a link to the beta key entry view (`data-act="to-beta"`). Uses `autocomplete="username"` and `autocomplete="current-password"` for browser autofill support.
- **`"beta"`**: A single text input for the invite key, a Verify button (`data-act="verify"`), and a back link (`data-act="to-login"`).
- **`"signup"`**: Name, email, and password inputs; an age/consent checkbox (`#au-consent`); a Create Account button (`data-act="signup"`); a note that beta accounts get the 15-minute tier free.
- **`"quiz"`**: Five form controls — a number input for age, and four `<select>` elements for experience, goal, timeline, and emotional response. Pre-fills from `currentUser.profile` if the user is revisiting from Settings. A Continue button (`data-act="quiz-submit"`).
- **`"a11y"`**: A plain question with two buttons — `data-act="a11y-on"` and `data-act="a11y-off"`. No inputs.

**Design note:** All event wiring is done via the single delegated listener in `bind()` using `data-act` attributes, not inline `onclick` handlers. This keeps `render()` free of event registration.

---

#### `err(msg)` (auth.js:229)

**Signature:** `function err(msg: string): void`

**Behavior:** Finds `#auth-err` inside the gate. If `msg` is truthy, sets `textContent` and `style.display = "block"`. If empty, hides the element. Safe to call even if `#auth-err` doesn't exist in the current view.

---

#### `val(id)` (auth.js:232)

**Signature:** `const val = (id: string) => string`

**Returns:** The `.value` of the element with the given ID, or `""` if not found.

---

#### `enter(email)` (auth.js:237–240)

**Signature:** `function enter(email: string): void`

**Behavior:**
1. In **static mode**: Persists `email` to `LS.session` and sets `currentUser = accountFor()`.
2. In **server mode**: No localStorage write; `currentUser` was already set from the API response before `enter()` was called.
3. Calls `unlock(true)` (animated unlock).

**Called by:** The `"login"` data-act handler after credentials are verified.

---

#### `applyA11y(on)` (auth.js:244)

**Signature:** `function applyA11y(on: boolean): void`

**Behavior:** Calls `document.body.classList.toggle("a11y-mode", !!on)`. The CSS file uses `.a11y-mode` to activate larger text, higher contrast, stronger focus outlines, and `prefers-reduced-motion`-style animation removal.

---

#### `unlock(animated)` (auth.js:254–287)

**Signature:** `async function unlock(animated: boolean): Promise<void>`

**Behavior:**
1. Sets `unlocked = true` — stops `guard()` from re-locking.
2. Calls `killSplash()`.
3. If `animated && gate`: Replaces the gate's innerHTML with a "Welcome / Unlocking your dashboard" card. This gives the user visual feedback during the potentially multi-second data fetch.
4. Awaits `window.TFBoot.ensureAppLoaded()`. On failure, shows the "Could not load your dashboard" error and returns early.
5. Calls `applyA11y(currentUser && currentUser.a11y)` — honors the user's stored accessibility preference immediately.
6. Calls `window.TF.init()` if it exists — triggers the first full app render. Guarded with `if (window.TF && window.TF.init)` because `init()` is idempotent (`_inited` flag prevents double-initialization).
7. Calls `window.TF.onRefresh()` — updates the greeting and re-renders the active page for this specific account's data.
8. Calls `applyUser()` — writes the user's name, plan, and avatar initial into the sidebar.
9. Calls `startRefresh()` — starts the tier-appropriate live-data interval.
10. **Animated path:** Wraps the gate-removal in a `setTimeout(700ms)` to let the welcome card settle, then removes `"tf-locked"` from `<body>` (revealing the rendered app behind the gate), adds class `"unlocking"` to the gate (a CSS slide-up animation), and removes the gate element when `animationend` fires (or after 1000ms as a timeout fallback).
11. **Non-animated path:** Removes `"tf-locked"` immediately and drops the gate synchronously.

**Design note:** The 700ms welcome card delay is intentional — it gives `ensureAppLoaded()` time to fetch data and inject scripts before the app is revealed. Without it, the page could flash an empty state. The `animationend` + 1000ms fallback pattern prevents a memory leak if the animation event never fires (e.g., `prefers-reduced-motion` OS setting skips animations).

---

#### `bind()` (auth.js:292–383)

**Signature:** `function bind(): void`

**Behavior:** Attaches a single delegated `click` listener on `document`. The listener:
1. Finds `e.target.closest("[data-act]")`. If not found, or if `gate` is absent or hidden, returns early.
2. Reads `t.dataset.act` and dispatches to the appropriate handler.

**Handlers (by `data-act` value):**

- **`"to-beta"`**: Calls `render("beta")`.
- **`"to-login"`**: Calls `render("login")`.
- **`"verify"`**:
  - Static mode: Checks `cyrb53(key) === BETA_HASH`. On match → `render("signup")`; on mismatch → `err(...)`.
  - Server mode: Stores key in `betaKeyEntered` and calls `render("signup")` unconditionally (server validates the key at signup time).
- **`"signup"`**:
  1. Reads name, email (lowercased), password, and consent checkbox.
  2. Validates: name non-empty, `validEmail(email)`, consent checked.
  3. Disables the button, awaits `emailDomainReal(email)`, re-enables.
  4. If domain fails → `err(...)`.
  5. **Server mode**: Requires password ≥ 8 chars; POSTs to `/api/auth/signup` with `{beta_key, name, email, password, consent: true}`; on 403 re-renders `"beta"` with the error; on other error shows the detail message; on success sets `currentUser = adoptServerUser(res.data.user)` and renders `"quiz"`.
  6. **Static mode**: Requires password ≥ 6 chars; checks for duplicate email in `LS.accounts`; creates the account with `cyrb53(pass)` as the stored password; sets `LS.session` and `currentUser`; renders `"quiz"`.
- **`"quiz-submit"`**:
  1. Reads the five quiz field values.
  2. Hard floor: if `ageNum < 13` → `err(...)`. Max: if `ageNum > 120` → `err(...)`.
  3. **Server mode**: POSTs to `/api/auth/profile`; sets `currentUser = adoptServerUser(res.data.user)` on success; renders `"a11y"`.
  4. **Static mode**: Calls `computeProfile(answers)`; writes enriched profile to `LS.accounts[LS.session].profile`; refreshes `currentUser`; renders `"a11y"`.
- **`"a11y-on"` / `"a11y-off"`**:
  1. Determines desired state (`on = a === "a11y-on"`).
  2. **Server mode**: POSTs to `/api/auth/a11y?on={on}` (fire-and-forget with await for ordering); sets `currentUser.a11y = on`; calls `applyA11y(on)`.
  3. **Static mode**: Mutates `LS.accounts`; refreshes `currentUser`; calls `applyA11y(on)`.
  4. Both modes: calls `unlock(true)` — initiates the full animated unlock sequence.
- **`"login"`**:
  1. Reads email (lowercased) and password.
  2. **Server mode**: POSTs to `/api/auth/login`; on failure → `err(...)`; on success → `currentUser = adoptServerUser(res.data.user)` and `enter(email)`.
  3. **Static mode**: Reads `LS.accounts[email]`; checks `acc.pass === cyrb53(pass)`; on match → `enter(email)`; on mismatch → `err(...)`.

**Called at IIFE scope (auth.js:505).** Set up before DOMContentLoaded, so the listener is active for the lifetime of the page.

---

#### `applyUser()` (auth.js:387–393)

**Signature:** `function applyUser(): void`

**Behavior:** Reads `currentUser`. If null, no-op. Otherwise:
- `#userName.textContent = u.name || u.email`
- `#userPlan.textContent = TIERS[u.tier].name || TIERS.beta.name`
- `#userAvatar.textContent = (u.name || u.email)[0].toUpperCase()`

**Called by:** `unlock()`.

---

#### `startRefresh()` (auth.js:398–404)

**Signature:** `function startRefresh(): void`

**Behavior:**
1. Clears any existing `refreshTimer` with `clearInterval`.
2. Looks up the tier from `TIERS[(currentUser && currentUser.tier) || "beta"]`, falling back to `TIERS.beta`.
3. Computes `ms = tier.refreshMin * 60 * 1000`.
4. Sets `refreshTimer = setInterval(() => refreshLiveData(tier), ms)`.
5. Calls `stamp(tier)` immediately to render the current status into the sidebar.

**Design note:** Clearing before setting means tier upgrades take effect immediately — no doubled intervals.

---

#### `stampEl()` (auth.js:408–415)

**Signature:** `function stampEl(): HTMLElement | null`

**Behavior:** Tries to find `#tf-updated` by ID. If not found, tries `#tf-updated-slot` then `.sidebar-foot` as the parent; creates a `<div id="tf-updated" class="tf-updated" role="status">` and appends it. Returns the element, or `null` if no parent slot is found.

**Design note:** Lazily creating the element means the stamp works even if it's called before the sidebar is in the DOM (though in practice it's called after `unlock()` which runs after `window.TF.init()` which renders the sidebar).

---

#### `stamp(tier)` (auth.js:419–425)

**Signature:** `function stamp(tier: object): void`

**Behavior:**
1. Gets or creates the stamp element via `stampEl()`. Returns if null.
2. If `pausedForClose(tier)` → sets innerHTML to: `<span class="tf-dot closed"></span>Markets closed · updates resume 9:30 AM ET`.
3. Otherwise: computes whether we're in "extended hours" (`!marketOpen()`), formats the tier name and cadence, and sets innerHTML to: `<span class="tf-dot"></span>Live · {tier.name} · every {N min or day}{extended}`.

---

#### `marketOpen()` (auth.js:430–438)

**Signature:** `function marketOpen(): boolean`  
**Returns:** `true` during US equity core market hours; `false` otherwise.

**Behavior:**
1. Constructs the current Eastern time using `new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }))`. This approach is DST-correct without any timezone library.
2. Returns `false` on weekends (day `0` = Sunday, `6` = Saturday).
3. Computes `mins = hours * 60 + minutes`. Returns `true` if `mins >= 570 && mins < 960` (9:30 AM to 4:00 PM ET).
4. On any `toLocaleString` failure (rare; some environments don't support the IANA database) → returns `true` (fail open: don't block refresh).

**Design note:** Market holidays are not modeled. The refresh simply skips during a holiday and resumes the next session when `marketOpen()` returns `true` again.

---

#### `pausedForClose(tier)` (auth.js:443)

**Signature:** `function pausedForClose(tier: object): boolean`  
**Returns:** `true` if the market is closed AND the tier has a `refreshMin > 30` (i.e., is the daily or hourly tier).

**Logic:** `return !marketOpen() && (tier.refreshMin || 0) > 30`.

**Rationale:** The 15-minute and 30-minute tiers (`refreshMin ≤ 30`) are paid for coverage that includes extended hours. The daily and hourly tiers do not have that entitlement, so they pause when the core market is closed to save API budget.

---

#### `refreshLiveData(tier)` (auth.js:448–478)

**Signature:** `async function refreshLiveData(tier: object): Promise<void>`

**Behavior — server mode** (auth.js:452–464):
1. Calls `api("/api/data/live")`.
2. If `res.status === 429` (rate-limited — too soon for this tier's cadence): calls `stamp(tier)` and returns without updating data.
3. If `ok && data && !data.paused`: `Object.assign(window, res.data)` (refreshes `PRICES_DATA`, `NEWS_INTEL`); calls `window.TF.onRefresh()`; updates `#tf-updated` with "Updated HH:MM · {tier.name}".
4. If `paused` (market closed server-side): calls `stamp(tier)` only.
5. Network error: silently swallowed — keeps current data.

**Behavior — static mode** (auth.js:466–477):
1. Checks `pausedForClose(tier)`. If paused: calls `stamp(tier)` and returns.
2. For each of `["js/prices_data.js", "js/news_intel.js"]`:
   - Fetches the file with `?t={Date.now()}` cache-bust.
   - Parses the JSON out of the file text by slicing from the `window.NAME =` marker, stripping the trailing `;`, and calling `JSON.parse`. This avoids injecting a new `<script>` tag (which would evaluate the whole file again and might conflict with the existing global).
   - Assigns `window[key] = JSON.parse(json)`.
3. Calls `window.TF.onRefresh()`.
4. Updates the `#tf-updated` timestamp line.

**Design note:** The raw-text parsing approach (slice + JSON.parse) in static mode is deliberate: injecting a second `<script>` tag for the same file would re-run the global assignment but the old constant captures in logic scripts would not update. By directly mutating `window.PRICES_DATA`, all code that reads `window.PRICES_DATA` at refresh time (rather than at eval time) gets the fresh data.

---

#### `guard()` (auth.js:484–502)

**Signature:** `function guard(): void`

**Behavior:**
1. Creates an inner `reassert` function:
   - If `unlocked` is true → returns immediately (the app is legitimately unlocked).
   - Disconnects the `MutationObserver` before touching the DOM. **Critical:** Without this disconnect, the observer's own DOM write (`appendChild(gate)`, `classList.add`) would fire the callback again as a microtask, creating an infinite loop that starved the page event loop and froze the tab.
   - Re-adds `"tf-locked"` to `<body>` if it was removed.
   - Re-appends `gate` to `<body>` if it was removed.
   - Sets `gate.style.display = "flex"` if it was hidden.
   - Re-observes `document.body` for `childList` changes after the DOM writes are done.
2. Tries to create a `MutationObserver(reassert)` observing `document.body` with `{ childList: true }`. This fires when someone removes the gate via devtools `Remove element`.
3. Regardless of observer support, sets `setInterval(reassert, 700)` — a 700ms periodic fallback that catches style/class edits (e.g., removing `"tf-locked"` via devtools `Edit attribute`) that the `childList` observer doesn't see.

**Called at IIFE scope (auth.js:506)** — active from page load.

**Design note:** The observer/interval combination makes it impractical to bypass the gate via devtools. However, the code comments explicitly acknowledge this is a soft gate: "It is NOT real security." The comment in `boot.js` reiterates the same — real data protection happens server-side, where the data files are 404-blocked.

---

#### `boot()` (auth.js:512–526)

**Signature:** `async function boot(): Promise<void>`

**Behavior:**
1. Adds `"tf-locked"` to `document.body` (in case JS was slow to run and the class was temporarily absent).
2. Awaits `window.TFBoot.ready` to get the confirmed `mode` string. Falls back to `"static"` if `TFBoot` is absent.
3. **Server mode**:
   - Calls `api("/api/auth/me")` to check for an existing session cookie.
   - If the response is `ok` and has a `user`: `currentUser = adoptServerUser(res.data.user)`; calls `unlock(false)` (silent, no animation — returning user).
   - Otherwise: calls `showGate("login")`.
4. **Static mode**:
   - If `LS.session && LS.accounts[LS.session]`: `currentUser = accountFor()`; calls `unlock(false)`.
   - Otherwise: calls `showGate("login")`.

**Entry point:** Called via:
```js
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
```
This handles both the common case (script `defer`'d, DOM already parsed) and edge cases where the script might evaluate after `DOMContentLoaded`.

---

#### `logout()` (auth.js:532–555)

**Signature:** `function logout(): void`

**Behavior:**
1. **Server mode**: Fires `api("/api/auth/logout", { method: "POST" })` as fire-and-forget (no await, inside try/catch) — clears the httpOnly session cookie server-side. The UI proceeds regardless.
2. **Both modes**: `LS.session = ""`; `currentUser = null`; `unlocked = false`.
3. Clears `refreshTimer`.
4. Adds `"tf-locked"` to `<body>` — hides the app.
5. Removes any existing gate element.
6. Creates a new `<div class="auth-gate goodnight" role="status">` and appends it to `<body>`. Its content is a goodbye card with:
   - A smiling face SVG (`gn-face`).
   - A waving hand SVG (`gn-wave`). Both are inline SVGs with neon-style CSS stroke animations.
   - "Goodbye, friend" and "See you next session" text.
7. After 1800ms, removes the goodbye element and calls `showGate("login")` — back to the login view.

**Design note:** `location.reload()` was deliberately avoided. A full reload would re-parse ~6 MB of data scripts (the `DATA_SCRIPTS` list) and re-run all the logic scripts, which was observed to trigger Chrome's "Page Unresponsive" dialog. The no-reload path re-uses the already-loaded app; the next login simply calls `window.TF.onRefresh()` to re-render with the new account's data.

**Event wiring** (auth.js:559): A separate `click` listener on `document` checks `e.target.closest("#logoutBtn")` and calls `logout()`. Bound on `document` so it survives sidebar re-renders.

---

#### `window.Auth` Public API (auth.js:562–593)

Assigned at the end of the IIFE:

| Property | Type | Description |
|---|---|---|
| `TIERS` | object | The tier definitions (see §3.1). |
| `user()` | `() => object\|null` | Returns `currentUser`. |
| `tier()` | `() => object` | Returns `TIERS[currentUser.tier] \|\| TIERS.free`. |
| `a11y()` | `() => boolean` | Returns `!!(currentUser && currentUser.a11y)`. |
| `profile()` | `() => object\|null` | Returns `currentUser.profile` or `null`. |
| `computeProfile` | function | The scoring function (exported for use in Settings and other modules). |
| `setProfile(answers)` | function | Updates the investor profile (Settings editor). |
| `setA11y(on)` | function | Updates accessibility preference (Settings toggle). |
| `logout` | function | The logout function. |

##### `window.Auth.setProfile(answers)` (auth.js:569–580)

**Behavior:**
1. Calls `computeProfile(answers)` to get the enriched profile.
2. **Server mode**: POSTs raw answers to `/api/auth/profile` (fire-and-forget); sets `currentUser.profile = prof`.
3. **Static mode**: Writes enriched profile to `LS.accounts` and `currentUser.profile`.
4. Returns the enriched profile object.

**Called by** `app.js` when the user clicks "Save profile" in the Settings page.

##### `window.Auth.setA11y(on)` (auth.js:581–591)

**Behavior:**
1. **Server mode**: POSTs to `/api/auth/a11y?on={on}` (fire-and-forget); updates `currentUser.a11y`.
2. **Static mode**: Writes to `LS.accounts` and `currentUser.a11y`.
3. Both modes: calls `applyA11y(on)`.

**Called by** `app.js`'s delegated `#a11yToggle` click/keydown handler.

---

## 4. app.js — Main Controller, Router, and View Renderer

**File:** `webapp/js/app.js`  
**Structure:** Non-IIFE module-level code; all identifiers are in the global scope of the script file (not `window.*` — they are function-scoped to the module by virtue of being top-level `const/let/function` in `"use strict"` but not explicitly attached to `window`). Exports only `window.TF.init` and `window.TF.onRefresh`, plus `window.tfShowLegState`.  
**Injected by:** `boot.js:loadInOrder(LOGIC_SCRIPTS)` — evaluated after all data globals exist.

### 4.1 Evaluation-Time Data Capture

#### `const D = window.TF_DATA || {}` (app.js:15)

The primary data object. Captured at script-eval time. Contains: `politicians`, `recent_trades`, `bills`, `correlation`, `sectors`, `tickers_opp`, `news`, `everyday`, `means`, `portfolio`, `recession`, `parallels`, `events`, `market_ticker`, `disclaimer`, `generated_at`, `user`.

All `render*()` functions read from `D`. Because `D` is a `const` reference to the object, if `window.TF_DATA` is mutated in place, `D` reflects the mutation. But `auth.js:refreshLiveData()` uses `Object.assign(window, data)` which replaces `window.TF_DATA` (a new reference), so `D` in `app.js` would not update for `TF_DATA`. Only `window.PRICES_DATA` and `window.NEWS_INTEL` are refreshed at runtime; `D` is treated as static.

#### `const STATES` (app.js:78)

```js
const STATES = (window.STATES_DATA || {}).byState || {};
```

State economic data keyed by abbreviation (e.g., `STATES["CA"]`). Captured at eval time from `window.STATES_DATA` (set by `js/states_data.js`).

#### `let LEGIS / OSTATES` (app.js:80–81)

```js
let LEGIS = (window.LEGISCAN_DATA || {}).byState || {};
let OSTATES = (window.OPENSTATES_DATA || {}).byState || {};
```

State legislative data. Declared with `let` (not `const`) because `ensureStateData()` can update them after lazy-loading the `legiscan_data.js` / `openstates_data.js` scripts.

#### `const NEWS_INTEL` (app.js:105)

```js
const NEWS_INTEL = window.NEWS_INTEL || { bySector: {}, byTicker: {} };
```

Chef GPT news intelligence index. Captured at eval time. `auth.js:refreshLiveData()` updates `window.NEWS_INTEL` with fresh data, but because `NEWS_INTEL` is a `const` reference to the object-at-eval-time, it **does not auto-update**. `tfNewsSummary()` reads directly from `NEWS_INTEL` (the eval-time snapshot). This is a known trade-off: the summary data is re-fetched on the next page render triggered by `window.TF.onRefresh()`, which calls `go(currentPage)`, which re-renders the active view's HTML including fresh `tfNewsSummary()` output — so the content updates, just not the constant reference itself.

#### `const SECBULK / USASTOCK / IWCOS / FEC` (app.js:359–167)

Read-only at eval time:
- `SECBULK`: SEC bulk financial data keyed by ticker (from `window.SECBULK_DATA.byTicker`).
- `USASTOCK`: USASpending government contracts keyed by ticker (from `window.USA_DATA.byTicker`).
- `IWCOS`: InfluenceWeb company names and metadata (from `window.IW_DATA.companies`).
- `FEC`: OpenFEC campaign finance data keyed by politician name (from `window.FEC_DATA.byName`).

---

### 4.2 DOM and Formatting Utilities

#### `$` (app.js:18)

```js
const $ = (sel, root = document) => root.querySelector(sel);
```

A brief alias for `querySelector`. Used throughout as `$("#greet")`, `$(".sidebar-foot")`, etc.

#### `esc(s)` (app.js:19)

```js
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ ... }[c]));
```

HTML escaper, identical in behavior to `auth.js`'s `E`. Used for all user-visible string interpolation in `app.js`'s templates. Handles `null`/`undefined` gracefully via `?? ""`.

#### `initials(name)` (app.js:20)

```js
const initials = (name) => String(name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
```

Returns up to 2 uppercase initials from a display name. Used for avatar placeholders.

#### `colorFor(v)` (app.js:21)

```js
const colorFor = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
```

Maps a signed numeric value to a CSS class string: `"up"` (green), `"down"` (red), or `""` (neutral). Used in financial data cells.

#### `pct(v)` (app.js:22)

```js
const pct = (v) => `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
```

Formats a number as a percentage string with sign and 2 decimal places (e.g., `"+3.45%"` or `"-1.20%"`).

#### Color Constants `C` (app.js:75)

```js
const C = { green: "#00C46A", red: "#EF4444", blue: "#38BDF8", amber: "#F59E0B", purple: "#A855F7" };
```

Shared color tokens used in `gauge()`, `sparkline()`, and `chamberBar()`.

#### `money0(n)` (app.js:121)

```js
const money0 = (n) => n == null ? "n/a" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
```

Formats a number as a dollar amount with no decimal places (e.g., `"$85,000"`). Returns `"n/a"` for null/undefined.

---

### 4.3 Visual Component Functions

#### `photoEl(name, bioguide, cls)` (app.js:26–32)

**Signature:** `function photoEl(name: string, bioguide: string|null, cls?: string): string`  
**Returns:** An `<img>` HTML string pointing to `assets/politicians/{bioguide}.jpg`, with an `onerror` handler that replaces the image with an initials placeholder `<div>`. If `bioguide` is absent, returns the placeholder immediately.

**Design note:** The `onerror` attribute's inner HTML uses escaped single quotes (`\\'`) because it is embedded in a double-quoted HTML attribute string. This avoids the XSS-via-onerror pattern since `esc(initials(name))` sanitizes the injected content.

---

#### `gauge(value, max, color, label)` (app.js:35–47)

**Signature:** `function gauge(value: number, max: number, color: string, label: string): string`  
**Returns:** An HTML string with a 116×116 SVG radial gauge and a centered label.

**Behavior:**
- Circle radius `r = 50`. Circumference `c = 2π × 50 ≈ 314.16`.
- `frac = clamp(value/max, 0, 1)`. `strokeDashoffset = c * (1 - frac)` — so `0` fills the full circle, `c` is empty.
- Background circle: `rgba(148,163,184,0.14)` — a subtle track.
- Foreground arc: `stroke={color}`, `stroke-linecap="round"` for rounded endpoints.

---

#### `sparkline(seed, color, dir)` (app.js:51–73)

**Signature:** `function sparkline(seed: number, color: string, dir?: "up"|"down"): string`  
**Returns:** An HTML string with an SVG sparkline chart (viewBox 240×38).

**Behavior:**
- Generates 24 pseudo-random data points using a linear congruential generator (LCG): `s = (s * 9301 + 49297) % 233280`. The LCG is seeded by `seed`, making charts deterministic — the same seed always produces the same shape.
- `dir = "up"` biases the random step: `v += (rnd - 0.45) * 10` (upward drift); `dir = "down"` uses `0.55` (downward drift).
- Renders a `<path>` for the line and a gradient-filled `<path>` for the area underneath.
- The gradient ID is `"g" + Math.abs(seed % 99999)` — unique-enough per sparkline to avoid SVG gradient ID collisions.

**Design note:** Deterministic pseudo-random sparklines are used for KPI cards and portfolio summaries where actual time-series data is not available. They convey visual "direction" without pretending to be real price data.

---

### 4.4 Data Enrichment and Intelligence Functions

#### `ensureStateData(cb)` (app.js:83–103)

**Signature:** `function ensureStateData(cb?: () => void): void`

**Behavior:**
1. If `window.LEGISCAN_DATA` already exists (pre-loaded or cached from a prior call): updates the module-level `LEGIS` and `OSTATES` references and calls `cb()` synchronously.
2. If `_stateDataLoading` is true (a load is already in progress): returns immediately to avoid double-loading.
3. Sets `_stateDataLoading = true`.
4. Defines `apply()`: updates `LEGIS`/`OSTATES` references and calls `cb()`.
5. **Server mode**: Calls `window.TFBoot.api("/api/data/state")`. On resolution (success or error), calls `Object.assign(window, res.data)` if ok, then `apply()`.
6. **Static mode**: Injects `js/legiscan_data.js` and `js/openstates_data.js` as `<script>` tags in parallel (not via `loadInOrder` — they are independent). Uses a countdown counter (`left = 2`) — `apply()` is called when both scripts fire `onload` or `onerror`.

**Called by:** `go("states")` in the router, and re-called if the user revisits the States page after `LEGISCAN_DATA` is populated.

**Design note:** This function avoids loading ~4.5 MB of state legislative data on initial page load. The data is only fetched once per session. The server mode fetches it as a gated authenticated bundle (`/api/data/state`) rather than exposing the raw files.

---

#### `tfNewsSummary(kind, key)` (app.js:107–119)

**Signature:** `function tfNewsSummary(kind: "ticker"|"sector", key: string): string`  
**Returns:** An HTML string with the "ThinkFree Summary" styled card, or `""` if no summary exists.

**Behavior — ticker:**
- Looks up `NEWS_INTEL.byTicker[key]`. If absent, returns `""`.
- Renders: badge, `v.summary` body, optional `v.what_it_means` section, and the "Chef GPT, not financial advice" footer.

**Behavior — sector:**
- Looks up `NEWS_INTEL.bySector[key]`, with fallback via `NI_SECTOR_ALIAS` (e.g., `"Technology"` → `"Information Technology"`).
- Renders: badge, sector label, `sec.summary` body, and the footer.

---

#### `accountabilityBlock(p)` (app.js:124–164)

**Signature:** `function accountabilityBlock(p: politician): string`  
**Returns:** An HTML section with the "Constituent Accountability" block, or `""` if no state data exists for `p.state`.

**Behavior:**
1. Maps `p.state` (full name, e.g., `"California"`) to a 2-letter abbreviation via `STATE_ABBR`.
2. Reads `STATES[ab]` for the state's economic data.
3. Computes `alignment`: `50 + (prosperity - 50) * 0.6 - max(0, repGain) * 0.8 - (pressure - 50) * 0.4`, clamped to 0–100.
   - High constituent prosperity + high pressure improvement + low representative trading gains → high alignment.
   - High trading gains while constituents struggle → low alignment.
4. Renders: an alignment score pill, meter bars for Prosperity / Affordability / Cost Pressure, economic stats summary line, and a Representative Outcomes section (trading return, P&L, PAC funding if FEC data exists).

**Framing note:** The `<div class="sample-note">` footer reads: "Alignment is not a corruption score. It contrasts how the district is doing economically with the representative's disclosed financial outcomes." This is the legally required non-accusatory framing mandated by `CLAUDE.md`.

---

#### `polScore3(p)` (app.js:174–181)

**Signature:** `function polScore3(p: politician): {influence: number, publicImpact: number, transparency: number}`

**Computes three scores for a politician:**
- **Influence**: `min(100, 30 + trades*0.3 + pac%*0.6 + |ret|*0.5)` — measures market access and funding leverage.
- **Public Impact**: `max(10, 70 - pac%*0.5 + individual%*0.2)` — measures grassroots vs PAC funding mix.
- **Transparency**: `max(5, 100 - pac%*1.4 - trades*0.15)` — inversely weighted by PAC dependence and trade frequency.

All three are integers between 0 and 100. The `polBadge()` function wraps them in interactive badge elements that trigger `ScoreInfo` explainers on click.

---

#### `fecBlock(name)` (app.js:183–200)

**Signature:** `function fecBlock(name: string): string`  
**Returns:** An HTML section with FEC campaign finance data for the politician, or `""` if no FEC data exists.

**Renders:** Total raised, from individuals, from PACs, cash on hand, top employer-contributor table, and a source link to the FEC profile.

---

#### `stockName(tk)` (app.js:362)

```js
function stockName(tk) { return (IWCOS[tk] && IWCOS[tk].name) || (SECBULK[tk] && SECBULK[tk].name) || tk; }
```

Returns the company name for a ticker. Prefers InfluenceWeb data (more curated), falls back to SEC bulk data, falls back to the ticker symbol itself.

---

#### `tickerCompanyName(tk)` (app.js:368)

```js
function tickerCompanyName(tk) { return (((window.PRICES_DATA || {}).byTicker || {})[tk] || {}).name || stockName(tk) || tk; }
```

Like `stockName()` but also checks `window.PRICES_DATA` (which is refreshed by the live-data timer), so it reflects the freshest company name.

---

#### `newsRelevant(a, tk)` (app.js:369–377)

**Signature:** `function newsRelevant(a: article, tk: string): boolean`  
**Returns:** `true` if the article is genuinely about the company represented by `tk`.

**Problem it solves:** Tickers like `"ON"`, `"IT"`, `"ALL"`, `"NOW"`, `"T"`, `"D"` are common English words. A naive `includes(ticker)` check would match irrelevant articles (e.g., any article containing the word "on" would match `ON` Semiconductor). `COMMON_TK` is a `Set` of such ambiguous tickers; `GENERIC_CO` is a `Set` of generic company-name words excluded from the company-name match.

**Logic (three tests, first match wins):**
1. **Company name match**: Tokenizes the company name (split on whitespace, length ≥ 4, not a generic word). If any token appears in the article blob, returns `true`.
2. **Explicit ticker mention**: Checks for `$TK` or `(TK)` in the blob. Returns `true`.
3. **Distinctive ticker token**: If `tk` is not in `COMMON_TK` and has ≥ 3 characters, checks for `\bTK\b` as a standalone word. Returns `true` if found.

---

#### `newsForTicker(tk)` (app.js:378)

```js
function newsForTicker(tk) { return (D.news || []).filter((n) => n.symbol === tk && newsRelevant(n, tk)); }
```

Filters all news to items whose `symbol` field matches `tk` AND passes the `newsRelevant()` check.

---

#### `preferredSectors()` (app.js:381–387)

**Signature:** `function preferredSectors(): string[]`  
**Returns:** An array of lowercase sector name strings matching the user's investment profile.

**Logic:**
- Growth/high-risk profile → technology, IT, communication services, consumer discretionary.
- Income/low-risk profile → utilities, consumer staples, real estate, financials, health care.
- Otherwise → a balanced default set.

**Called by:** `tailorNews()` and `renderNews()` (for the "tailored to your profile" label).

---

#### `tailorNews(list)` (app.js:388–396)

**Signature:** `function tailorNews(list: article[]): article[]`  
**Returns:** A re-ordered copy of `list` where preferred-sector articles sort first, preserving relative order within each group.

**Behavior:** Uses a stable sort — items get a priority of `0` (preferred) or `1` (other), and ties preserve the original index ordering. If `preferredSectors()` returns an empty set, the list is returned as-is.

---

#### `tidySummary(s)` (app.js:399–407)

**Signature:** `function tidySummary(s: string): string`  
**Returns:** A cleaned summary string that ends on a complete sentence boundary.

**Behavior:**
1. If `s` does not end in `"..."` or `"…"`, returns `s` unchanged.
2. Strips the trailing ellipsis.
3. Finds the last sentence-ending punctuation character (`.`, `!`, or `?`) with `re.exec` in a loop (to get the last match, not the first).
4. If a boundary is found at index ≥ 40 chars in, slices there.
5. Fallback (boundary too early or absent): strips the last dangling word and appends `"."`.

**Purpose:** News article previews from Finnhub and other sources are often truncated mid-sentence with `"..."`. Showing a mid-sentence cut looks broken; this function makes the preview end cleanly.

---

#### `detectThemes(items, max)` (app.js:421–424)

**Signature:** `function detectThemes(items: article[], max?: number): string[]`  
**Returns:** Up to `max` (default 3) plain-English theme strings matched against the combined headline+summary text of all articles.

**Behavior:** Tests each `NEWS_THEMES` regex against the concatenated article blob. Returns the friendly string label for each matching theme.

**`NEWS_THEMES`** (app.js:410–420): 9 regex patterns covering earnings, product launches, M&A, dividends, leadership changes, analyst ratings, litigation/regulation, daily stock moves, and partnerships.

---

#### `joinList(arr)` (app.js:425–429)

**Signature:** `function joinList(arr: string[]): string`  
**Returns:** A comma-and-"and" English list (e.g., `"earnings, dividends and leadership changes"`).

---

#### `genImpact(sectors)` (app.js:451–457)

**Signature:** `function genImpact(sectors: string[]): {gen: string, score: number}[]`  
**Returns:** Array of 5 generational impact scores.

**Behavior:** Looks up each sector in `GEN_SECTOR_W`. The weight for each generation is averaged across all input sectors. Multiplied by 70 and rounded. If no sectors match, uses `GEN_SECTOR_W.default`.

---

#### `genImpactBlock(sectors, title)` (app.js:459–475)

**Signature:** `function genImpactBlock(sectors: string[], title?: string): string`  
**Returns:** HTML for the generation impact panel.

**Behavior:**
- If `window.GenImpact` (the richer `genimpact.js` module) is available, delegates to `window.GenImpact.forSectors()` and `window.GenImpact.panel()`.
- Otherwise, falls back to the local `genImpact()` computation and renders bar rows inline.

---

#### `sourceName(url)` (app.js:477–485)

```js
function sourceName(url): string
```

Extracts the publisher name from a URL. Strips `www.` and the TLD; maps known hostnames to friendly names (e.g., `"finnhub"` → `"Finnhub"`).

#### `sourceLink(url, source)` / `newsHeadline(a)` / `readMore()` (app.js:487–495)

- `sourceLink(url, source)`: Returns an `<a>` tag linking to the original article with the publisher name.
- `newsHeadline(a)`: Returns `esc(a.headline)` — deliberately kept in-app (no link-out) so readers consume the ThinkFree Summary rather than leaving the app.
- `readMore()`: Returns `""` — placeholder; no "read more" link is emitted.

#### `credBadge(n)` (app.js:497–502)

Maps `n.credibility_tier` to a CSS class and renders a badge: `"Trusted"` → `.up`, `"Reliable"` → `.info`, `"Mixed"` → `.warn`, anything else → `.down`.

#### `newsSentiment(n)` (app.js:503–509)

Returns `[text, pillClass]` tuple: `"positive"` → `["Positive", "up"]`, `"negative"` → `["Negative", "down"]`, otherwise `["Neutral", "info"]`.

---

### 4.5 Modal Functions

#### `openModal(html)` (app.js:207–216)

**Signature:** `function openModal(html: string): void`

**Behavior:**
1. Sets `#modalContent.innerHTML = html`.
2. Adds class `"open"` to `#modal` (the overlay). CSS transitions the overlay to full opacity/visibility.
3. Resets scroll: `overlay.scrollTop = 0` and `#modalBox.scrollTop = 0`. Repeated inside `requestAnimationFrame()` to handle browser scroll restoration that might override the synchronous reset.

---

#### `closeModal()` (app.js:217–219)

**Signature:** `function closeModal(): void`

**Behavior:** Removes class `"open"` from `#modal`. The CSS transition hides the overlay.

**Called by:** The `#modalClose` button click, clicking the `#modal` overlay directly (not the `#modalBox` content area), and `Escape` keydown.

---

### 4.6 Detail View Functions

#### `politicianProfile(name)` (app.js:222–319)

**Signature:** `function politicianProfile(name: string): void`

**Behavior:**
1. Looks up the politician from `D.politicians` by name.
2. Computes `polScore3(p)` for the three accountability scores.
3. Builds the full HTML including:
   - `photoEl()` headshot.
   - Portfolio stats (net worth, portfolio value, 6-month return, P&L).
   - Three accountability score badges via `polBadge()`.
   - Summary text.
   - `fecBlock(p.name)` — FEC campaign finance section.
   - `accountabilityBlock(p)` — district vs. representative outcomes.
   - Most-traded tickers chip row.
   - Top donors and outside spending tables.
   - Trade timeline (up to 40 entries) with bill correlation data, timing indicators (before/after), and per-trade P&L.
   - Related legislation list.
   - Disclaimer per the framing rule.
4. Calls `openModal(html)`.

---

#### `allTradesView()` (app.js:322–339)

**Signature:** `function allTradesView(): void`

**Behavior:** Renders a complete table of all `D.recent_trades` (not capped at 14 like the Political Watch page renders). Opens in the modal.

---

#### `stockDetail(tk)` (app.js:511–599)

**Signature:** `function stockDetail(tk: string): void`

**Behavior:**
1. Gathers data from `SECBULK[tk]`, `USASTOCK[tk]`, `IWCOS[tk]`, `window.PRICES_DATA.byTicker[tk]`.
2. Computes `TFScores.influenceScore(tk)` and `TFScores.dependencyScore(tk)`.
3. Filters congressional trades and related bills for the ticker.
4. Calls `newsForTicker(tk)` with the relevance filter.
5. **Holistic summary construction**: Builds a 2–4 sentence plain-English narrative using `detectThemes(news)`, revenue/income from SEC data, government contracts from USASpending, and congressional trading activity.
6. Renders a full company detail panel including:
   - Company logo (with initials fallback on `onerror`).
   - Price and change percentage.
   - `tfNewsSummary("ticker", tk)` — Chef GPT summary.
   - Key financial figures (market cap, revenue, net income, assets, federal contracts, exchange).
   - Generation Impact panel (via `genImpactBlock()` or `window.GenImpact`).
   - Congressional trades table.
   - Related legislation chip row.
   - Recent news feed (up to 6 items with relevance filter applied).
7. Calls `openModal(html)`.

---

#### `billDetail(id)` (app.js:602–653)

**Signature:** `function billDetail(id: string): void`

**Behavior:**
1. Calls `billById(id)` to find the bill (preferring `correlation.top_bills` rich data over `bills` basic data).
2. Renders:
   - Header: sector tags, bill title, congress.gov link, action date.
   - Plain-English summary (`b.plain_summary || b.action_text`).
   - `genImpactBlock(b.sectors)` — generation impact with status note.
   - "Who traded it" table with before/after timing highlight.
   - PAC/lobbying chip row.
   - Disclaimer.
3. Calls `openModal(html)`.

---

#### `billById(id)` (app.js:349–356)

**Signature:** `function billById(id: string): object | undefined`

**Behavior:** Lazily builds `_billMap` (a merged dictionary from `D.bills` and `D.correlation.top_bills`). Rich `top_bills` entries overwrite basic `bills` entries for the same `bill_id`. Returns the entry for `id`.

---

#### `eventDetail(id)` (app.js:1218–1235)

**Signature:** `function eventDetail(id: string): void`

**Behavior:** Finds the event in `D.events` by `id`. Renders: category + date range badge, event name, six `row()` sections (What Happened, Why Similar, What Happened After, History's Warning, Personal Impact), modern parallel themes chips. Opens in the modal.

---

### 4.7 Page Render Functions

All `render*()` functions return an HTML string. They are registered in the `PAGES` map and called lazily by `go()` on first navigation to each page.

#### `renderDashboard()` (app.js:656–822)

**Returns:** Four grid sections:
1. **KPIs row**: Market Mood (72%, bullish, sparkline), Recession Risk (computed from `D.recession`), Market Direction, Top Story.
2. **Political block**: Feature politician (top `D.politicians[0]`) with photo, stats, and "Top 6 by Trading Gains" rank list; Investigative Overview gauge (Bill-Trade Correlation Index from `D.correlation`).
3. **Insight row**: What Matters Today (`D.means`), How This Affects You (`D.everyday`), Market Signals (`D.tickers_opp`), Sector Scorecard (bar chart from `D.sectors`).
4. **Bottom row**: Opportunity Scores, My Portfolio KPI, Historical Parallels preview, Quick Actions grid.

---

#### `marketSummary()` (app.js:826–873)

**Signature:** `function marketSummary(): string`  
**Returns:** A plain-English paragraph summarizing the day's news for the `renderNews()` Market Overview card.

**Behavior:**
1. Groups news by sector and company; counts positive/neutral/cautious sentiment.
2. Identifies top sectors (mapped to plain English, e.g., `"Information Technology"` → `"tech companies"`).
3. Detects themes via the `NEWS_THEMES` regex set.
4. Assembles a 3–4 sentence narrative: what sectors, which companies, what themes, what the overall mood is.

---

#### `sectorSummaries()` (app.js:876–913)

**Signature:** `function sectorSummaries(): {name, sec, count, text}[]`  
**Returns:** Array of sector summary objects, sorted by article count descending.

**Behavior:** For each sector group, generates a 4-sentence plain-English paragraph: coverage share, detected themes, company names, overall tone. The leading sentence varies: the top sector says "busiest part of the market today"; others say "has N stories in today's feed."

---

#### `renderNews()` (app.js:933–997)

**Returns:** The News page HTML, with:
- Page header + story count.
- Market Overview card (using `marketSummary()`).
- Market ticker row (6 categories from `D.market_ticker`).
- "What's Happening by Sector" card (from `sectorSummaries()`; each row has a `data-secnews` chip that opens `sectorNewsModal()`).
- Two-column grid: left = impact-sorted (via `tailorNews()`) full news feed; right = "What This Means For You" (`D.everyday` items).

---

#### `renderPolitical()` (app.js:1000–1105)

**Returns:** The Political Watch page HTML, with:
- Top politician feature card (photo, stats).
- Top 10 politicians table (with three accountability score columns via `polBadge()`).
- Recent trades table (14 rows; "View all" triggers `allTradesView()`).
- Investigative Overview card: Correlation Index gauge, four summary stats, "How Bills Were Influenced" timeline (clickable via `data-bill` attributes).
- Disclaimer at page bottom.

---

#### `renderPortfolio()` (app.js:1107–1136)

**Returns:** The Portfolio page HTML: four KPI cards (value, exposure, cash, win rate) from `D.portfolio`, and the open positions table.

---

#### `renderMarkets()` (app.js:1139–1159)

**Returns:** The Markets page HTML: sector opportunity bar chart, ticker signals table.

---

#### `renderReasoning()` (app.js:1162–1179)

**Returns:** The Economic Reasoning page HTML: recession risk gauge (score/max from `D.recession`), "What The Indicators Say" summary and factor list.

---

#### `renderHistory()` (app.js:1182–1215)

**Returns:** The Historical Parallels page HTML:
- Parallel analog cards (from `D.parallels`): each with a timeline of historical periods.
- Historical Events Library grid (from `D.events`): card-per-event with category badge, summary preview, and modern parallel theme chips. Clicking a card triggers `eventDetail()`.

---

#### `renderSettings()` (app.js:1237–1281)

**Returns:** The Settings page HTML:
- Profile stat card (name, plan, data generation date from `D.generated_at`).
- Investor Profile editor card: pre-fills form inputs from `window.Auth.profile()`. Shows current risk tolerance as a pill. "Save profile" button (`#saveProfileBtn`).
- Accessibility toggle card (`#a11yToggle`): the current on/off state read from `window.Auth.a11y()`.
- About ThinkFree card with inline accessibility statement link (`#a11yStatementLink`).

---

#### `renderIntelligence()` (app.js:1302–1381)

**Returns:** The Influence Intelligence page HTML:
- Influence Score top companies table (computed via `TFScores.influenceScore()`).
- Government Dependency top companies table (computed via `TFScores.dependencyScore()`).
- Industry Intelligence Dashboards table (aggregated via `TFScores.industryRollup()`).
- PAC Money top recipients table (from `FEC_DATA`).
- Lobbying industry groups table (from `NP_DATA` via ProPublica).

---

#### `renderStates()` (app.js:1456–1487)

**Returns:** The State Rankings page HTML:
- Four ranking tables: Constituent Prosperity, Constituent Pressure, Housing Affordability, Real Purchasing Power.
- `#leg-watch-mount` div: if `LEGISCAN_DATA` is already loaded, renders the Legislature Watch card; otherwise shows a "Loading..." placeholder. The `go()` router's `ensureStateData()` call will update this mount point asynchronously.

---

#### `renderLegWatch()` (app.js:1489–1508)

**Returns:** The State Legislature Watch card HTML:
- Header with totals (bills, legislators, statehouses).
- `<select id="leg-select">` with all available states, defaulting to `"CA"` if present.
- `#leg-detail` div pre-rendered with `renderLegDetail(defaultState)`.

**`window.tfShowLegState(ab)`** (app.js:1451–1454): The `onchange` handler of `#leg-select`. Replaces `#leg-detail.innerHTML` with `renderLegDetail(ab)`. Exposed on `window` because it is called from an inline `onchange` attribute in the HTML string returned by `renderLegWatch()`.

---

#### `renderLegDetail(ab)` (app.js:1412–1450)

**Signature:** `function renderLegDetail(ab: string): string`  
**Returns:** The HTML for one state's legislature detail: session metadata, bill status breakdown pills, chamber composition bars (`chamberBar()`), economically-relevant bills table, legislator roster with Open States photos.

**Helpers:**
- `osPhotoIndex(ab)`: Builds and caches a lookup map from `lastname|firstInitial` → `{image, url, email}` using Open States data.
- `osKey(name)`: Normalizes a name to the `lastname|firstInitial` key.
- `partyColor(p)`: Returns a hex color for D/R/I/Other.
- `chamberBar(name, c)`: Renders a proportional party-composition bar with legend.

---

#### `renderInfluence()` (app.js:1511–1556)

**Returns:** The InfluenceWeb page HTML: the graph stage (canvas, zoom controls, breadcrumb, legend, tooltip, HUD, drill panel, side panel). The actual graph engine is initialized separately by `influenceweb.js` when `window.IW.activate()` is called.

**Notable:** Optionally prepends `window.Predictions.render()` at the top if the Predictions module is loaded.

---

### 4.8 Search System

#### `searchIndex()` (app.js:1560–1595)

**Signature:** `function searchIndex(): object[]`  
**Returns:** A lazily-built flat array of search items. Memoized after first call via `_searchIndex`.

**Item types:**
- `{type: "pol", key: name, group: "Politicians", label, sub, ico}` — one per politician.
- `{type: "bill", key: bill_id, group: "Bills", label, sub: title, ico: "BILL"}` — deduplicated across `D.bills` and `D.correlation.top_bills`.
- `{type: "event", key: id, group: "Historical Events", label: name, sub: date_range, ico: "HIST"}`.
- `{type: "page", key: "political", group: "Tickers", label: ticker, sub: "N congressional trades", ico}` — from unique tickers in `D.recent_trades`.
- `{type: "page", key: "news", group: "News", label: headline, sub: sector, ico: symbol}` — one per news article.
- `{type: "page", key: "news", group: "Your Costs", label: category, sub: impact, ico: "$"}` — from `D.everyday`.

---

#### `runSearch(q)` (app.js:1598–1625)

**Signature:** `function runSearch(q: string): void`

**Behavior:**
1. If `q.trim().length < 2`: clears and hides `#searchResults`; returns.
2. Iterates `searchIndex()`. For each item where ``${label} ${sub}`.toLowerCase().includes(q)``, pushes to the item's group bucket.
3. Renders results by group (`["Politicians", "Bills", "Tickers", "Historical Events", "News", "Your Costs"]`) with per-group caps (`{Politicians: 6, Bills: 6, "Historical Events": 4, Tickers: 6, News: 4, "Your Costs": 4}`).
4. Sets `#searchResults.innerHTML` and adds class `"open"` if any results exist; otherwise shows a "No matches found" message.

---

#### `searchDispatch(type, key)` (app.js:1627–1635)

**Signature:** `function searchDispatch(type: string, key: string): void`

**Behavior:**
1. Clears and hides `#searchResults`; clears the search input.
2. Routes by `type`:
   - `"pol"` → `politicianProfile(key)`.
   - `"bill"` → `billDetail(key)`.
   - `"event"` → `go("history")` then `eventDetail(key)`.
   - `"page"` → `go(key)` (navigates to the target page).

---

### 4.9 Router

#### `PAGES` (app.js:1638–1650)

A plain object mapping page name strings to their render functions:

```js
const PAGES = {
  dashboard: renderDashboard, influence: renderInfluence, intelligence: renderIntelligence,
  states: renderStates, news: renderNews, political: renderPolitical,
  portfolio: renderPortfolio, markets: renderMarkets, reasoning: renderReasoning,
  history: renderHistory, settings: renderSettings,
};
```

#### `rendered` (app.js:1651)

```js
const rendered = {};
```

A dictionary recording which pages have been rendered at least once. `rendered[page] = true` after first render; `rendered[page] = false` to force a re-render on next `go()` call.

---

#### `go(page)` (app.js:1653–1682)

**Signature:** `function go(page: string): void`

**Behavior:**
1. If `PAGES[page]` is not found, defaults to `"dashboard"`.
2. **Lazy render**: If the host element exists and `rendered[page]` is falsy, calls `PAGES[page]()` and sets `host.innerHTML` to the result. Marks `rendered[page] = true`.
3. **Page activation**: Removes `"active"` from all `.page` elements; adds it to `#page-{page}`. Updates `.nav-item` active state.
4. **Scroll reset**: `document.querySelector(".viewport").scrollTop = 0`.
5. **Hash update**: `location.hash = page`.
6. **State Legislature lazy load** (if `page === "states"`): Calls `ensureStateData()` with a callback that replaces `#leg-watch-mount.innerHTML` with `renderLegWatch()`.
7. **InfluenceWeb activation/deactivation**: If `page === "influence"` → `requestAnimationFrame(() => { window.IW.activate(); window.IW.resetView(); })`. Otherwise → `window.IW.deactivate()`. The `requestAnimationFrame` ensures the page element is visible (display not none) before the graph engine tries to measure canvas dimensions.

**Design note:** Pages are rendered once and cached. Exceptions: `rendered.settings` and `rendered.news` are explicitly reset to `false` after a profile save (in the `#saveProfileBtn` handler in `init()`) so the next navigation re-renders them with fresh tailoring data.

---

#### `initTicker()` (app.js:1684–1688)

**Signature:** `function initTicker(): void`

**Behavior:** Sets `#ticker.innerHTML` to a horizontal strip of market data spans from `D.market_ticker`. Each item has a label, value, and direction-colored change percentage.

**Called by:** `init()` and `window.TF.onRefresh()`.

---

### 4.10 Initialization and Lifecycle

#### `setGreeting()` (app.js:1692–1702)

**Signature:** `function setGreeting(): void`

**Behavior:**
1. Reads the display name: prefers `window.Auth.user().name`, falls back to `D.user.name`, then to the hardcoded default `"Allan"`.
2. Computes the time-of-day greeting: `< 12` → "Good morning"; `< 17` → "Good afternoon"; else "Good evening".
3. Sets text content of `#userName`, `#userPlan`, `#userAvatar`, `#greet`.

**Called by:** `init()` (once) and `window.TF.onRefresh()` (on every re-login or data refresh). Keeping it separate from `init()` means it runs after a second-user login without reinitializing the whole app.

---

#### `init()` (app.js:1703–1833)

**Signature:** `function init(): void`

**Behavior (guarded by `_inited` flag — runs only once):**

1. `setGreeting()`.
2. `initTicker()`.
3. **Nav click** delegation on `#nav`: `go(item.dataset.page)` on click.
4. **Nav keyboard** delegation on `#nav`: `Enter`/`Space` on focused nav items → `go()` (WCAG 2.1.1 compliance).
5. **Global body click** delegation — handles all `data-*` actions in rendered page content:
   - `[data-secnews]` → `sectorNewsModal(sec)`.
   - `[data-stock]` → `stockDetail(ticker)`.
   - `[data-iwco]` → `go("influence")` + `window.IW.openCompany(ticker)`.
   - `[data-pol]` → `politicianProfile(name)`.
   - `[data-action="alltrades"]` → `allTradesView()`.
   - `[data-bill]` → `billDetail(id)`.
   - `[data-event]` → `eventDetail(id)`.
   - `[data-goto]` → `go(page)`.
   - Does not hijack real `<a>` link clicks.
6. **Modal close**: `#modalClose` click → `closeModal()`; overlay `#modal` click (not the box) → `closeModal()`; `Escape` keydown → `closeModal()` + close search dropdown.
7. **Search**: `#searchInput` `input` event → `runSearch()`; `focus` event → re-run if non-empty; `#searchResults` click → `searchDispatch()`; outside-click handler → close dropdown.
8. **Dark/light theme toggle**:
   - Reads `localStorage.getItem("tf-theme")` on init.
   - `applyTheme(light)`: toggles `class="light"` on `<body>` and the toggle's `"off"` class; sets `aria-checked`.
   - `toggleTheme()`: flips `lightMode`, calls `applyTheme`, persists to `localStorage`.
   - `#darkToggle` click and `Enter`/`Space` keydown both trigger `toggleTheme()`.
9. **Accessibility mode toggle** (delegated, because `#a11yToggle` is inside the Settings page which renders lazily):
   - `toggleA11y(t)`: reads current state from toggle's `"off"` class; calls `window.Auth.setA11y(turningOn)`.
   - Wired to both click and `Enter`/`Space` keydown on `#a11yToggle`.
10. **Profile save** (`#saveProfileBtn` click):
    - Reads all five Settings form inputs.
    - Calls `window.Auth.setProfile(answers)`.
    - Sets `rendered.settings = false; rendered.news = false; go("settings")` — forces re-render of both Settings (to show new risk badge) and News (to re-apply tailoring).
11. **Accessibility statement link** (`#a11yStatementLink` click):
    - Prevents default navigation.
    - Calls `openModal()` with the full WCAG 2.1 AA statement, including keyboard navigation claims, accessibility mode description, known limitations (InfluenceWeb graph is visual-only), and feedback email.
12. **Initial route**: `go(location.hash.replace("#", "") || "dashboard")` — restores the last visited page from the URL hash, defaulting to dashboard.

**Fallback**: `document.addEventListener("DOMContentLoaded", function() { if (!window.Auth) init(); })` at app.js:1847 — if the auth gate is somehow absent, `init()` runs directly on DOM ready.

---

#### `window.TF.init` (app.js:1837)

```js
window.TF = window.TF || {};
window.TF.init = init;
```

The public entry point called by `auth.js:unlock()`. Delegates directly to `init()`. The `_inited` guard inside `init()` makes this idempotent — calling it a second time (e.g., if `onRefresh()` triggers a re-auth) is a no-op.

---

#### `window.TF.onRefresh` (app.js:1838–1843)

```js
window.TF.onRefresh = function () {
  setGreeting();
  const p = (location.hash || "#dashboard").slice(1);
  if (rendered[p]) { rendered[p] = false; go(p); }
  if (typeof initTicker === "function") initTicker();
};
```

**Called by:** `auth.js:unlock()` (immediately after `TF.init()` on first login) and `auth.js:refreshLiveData()` (on every data refresh interval tick).

**Behavior:**
1. `setGreeting()` — updates name/greeting/avatar for the current user.
2. Gets the current page from `location.hash`. If it has been rendered (`rendered[p]` is true), resets the flag and calls `go(p)` to re-render it with fresh data.
3. `initTicker()` — refreshes the market ticker strip.

**Design note:** Only the currently-visible page is re-rendered on a data refresh. Other pages' `rendered[page]` flags remain `true`; when the user navigates to them, they will serve the cached version until the next call to `onRefresh()`. This is acceptable because data refreshes happen on the same cadence as a user is likely to browse between pages.

---

## 5. Window Globals Cross-Reference

| Global | Set by | Read by |
|---|---|---|
| `window.TFBoot` | `boot.js` | `auth.js` (all auth calls), `app.js` (`ensureStateData`), `influenceweb.js` |
| `window.Auth` | `auth.js` | `app.js` (`preferredSectors`, `renderSettings`, `init` handlers), other modules |
| `window.TF` | `app.js` | `auth.js` (`unlock`: `TF.init`, `TF.onRefresh`) |
| `window.TF_DATA` | `js/data.js` (static) or `/api/data/bundle` (server) | `app.js` (captured as `const D` at eval time) |
| `window.PRICES_DATA` | `js/prices_data.js` or `/api/data/live` | `app.js` (`tickerCompanyName`, `stockDetail`); refreshed by `auth.js:refreshLiveData` |
| `window.NEWS_INTEL` | `js/news_intel.js` or `/api/data/live` | `app.js` (captured as `const NEWS_INTEL` at eval time); refreshed globally by `refreshLiveData` |
| `window.STATES_DATA` | `js/states_data.js` or `/api/data/bundle` | `app.js` (captured as `const STATES`) |
| `window.LEGISCAN_DATA` | `js/legiscan_data.js` or `/api/data/state` | `app.js:ensureStateData` (lazy) |
| `window.OPENSTATES_DATA` | `js/openstates_data.js` or `/api/data/state` | `app.js:ensureStateData` (lazy) |
| `window.SECBULK_DATA` | `js/secbulk_data.js` or bundle | `app.js` (captured as `const SECBULK`) |
| `window.FEC_DATA` | `js/fec_data.js` or bundle | `app.js` (captured as `const FEC`) |
| `window.IW_DATA` | `js/influence_data.js` or bundle | `app.js` (captured as `const IWCOS`, `const IWNAMES`) |
| `window.USA_DATA` | `js/usaspending_data.js` or bundle | `app.js` (captured as `const USASTOCK`, `const USADATA`) |
| `window.NP_DATA` | `js/nonprofit_data.js` or bundle | `app.js:renderIntelligence` |
| `window.TFScores` | `js/scores.js` | `app.js` (`stockDetail`, `renderIntelligence`, `polScore3`) |
| `window.GenImpact` | `js/genimpact.js` | `app.js:genImpactBlock`, `app.js:stockDetail` |
| `window.ScoreInfo` | `js/scoreinfo.js` | `app.js:polBadge` |
| `window.Predictions` | `js/predictions.js` | `app.js:renderInfluence` |
| `window.IW` | `js/influenceweb.js` | `app.js:go` (activate/deactivate/openCompany) |
| `window.tfShowLegState` | `app.js` | Inline `onchange` in `renderLegWatch()` HTML string |
