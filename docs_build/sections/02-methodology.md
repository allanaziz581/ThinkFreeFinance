# Part 2 — Development Methodology & Engineering Pipeline

This part records *how* ThinkFree was built: the inputs that governed every
decision, the working method, and the chronological engineering narrative. It is
written so an external engineer can understand not just *what* the code does but
*why* it is shaped the way it is.

## 2.1 The three inputs that governed development

Every change was made against three sources of truth, in priority order:

1. **The founder's direct instructions** — the feature requests and corrections
   issued conversationally (e.g. "make login always land on the dashboard",
   "no emojis in the UI", "make the backend completely safe for beta testing").
2. **The canonical blueprint (`CLAUDE.md`)** — a committed project charter that
   defines the mission statement, the eight-question framework, the political-
   intelligence framing rule, the 13-phase roadmap with per-phase status, the
   security requirements, and the planned verification-agent layer. This file is
   treated as non-negotiable: the mission ("research analyst, not trading bot")
   and the framing rule ("transparency, not accusation") override any other
   consideration.
3. **The prior code base** — the existing Python pipeline, the Streamlit
   prototype, and the data already built (e.g. the QuiverQuant integration and
   the government-contract files). New work extends this rather than replacing it.

## 2.2 Working method (the "analyze before coding" loop)

The blueprint mandates a senior-architect discipline. Before any code is written,
five questions are answered:

1. What phase are we currently in?
2. What dependencies already exist?
3. What modules should be created next?
4. Does the requested feature fit the roadmap?
5. How does the new code integrate into the existing ecosystem?

Three principles are enforced throughout:

- **Respect phase dependencies** — never build Phase 8 logic on broken Phase 3 data.
- **Preserve financial facts** — summaries and analyses must never lose numerical precision.
- **Behavior-preserving change** — when refactoring or hardening, function must not change; only readability or safety improves. This was verified mechanically (see 2.4).

## 2.3 The dual-mode architecture decision

A central architectural decision was to make the front end **dual-mode** so it
runs both as a plain static site (for development and offline use) and as a
server-backed app (for secure cloud hosting), with no code fork:

- **Static mode** — the page loads `*_data.js` bundles directly and gates access
  with a soft client-side overlay (localStorage + a non-cryptographic `cyrb53`
  hash). Suitable for local `file://` use.
- **Server mode** — the same shell detects a FastAPI backend via `GET
  /api/healthz`, then performs real login against `/api/auth/*` and fetches data
  from `/api/data/*` (keys, Python, and datasets never reach the browser).

`webapp/js/boot.js` is the switch: it probes health, sets the mode, and injects
the data and logic scripts **in the correct order** only after authentication.
This was necessary because every logic module captures its data at evaluation
time (e.g. `const D = window.TF_DATA || {}`), so data globals must exist before
the logic scripts run.

## 2.4 Behavior-preserving verification (the readability pass)

The founder requested the codebase be made readable to an external engineer —
normal human comments instead of decorative `===== banners =====`, with textual
and visual structure — **without changing what the code does**. To guarantee the
"no behavior change" constraint, a **stack-based JavaScript normalizer** was used:
it strips comments and whitespace while correctly handling string literals,
nested template literals (`${...}` containing backticks), and regex literals,
then compares the normalized bytes before and after. After the pass, all nine
reformatted modules were proven byte-identical in behavior. This is the standard
applied to any future cleanup work.

## 2.5 Chronological engineering narrative

The following is the actual sequence of engineering work, with the problem, the
diagnosis, and the resolution for each item. It doubles as a record of the
non-obvious bugs that were found and fixed.

### 2.5.1 Behavioral onboarding quiz + settings styling
The signup flow was completed with a five-question behavioral profile quiz
(age, experience, goal, time horizon, loss reaction) and the CSS for quiz and
settings inputs. The quiz scores the user into a risk tolerance and a two-part
`profile_id` used to tailor the briefing (see Part 6A, `computeProfile`).

### 2.5.2 Logout hang ("page unresponsive")
**Symptom:** logging out buffered back to the loading screen and Chrome reported
"page unresponsive."
**Diagnosis:** logout called `location.reload()`, which re-parsed the ~6 MB
single-page app synchronously.
**Fix:** logout was rewritten to re-lock the gate *in place* (clear session,
re-add the lock overlay) without reloading the document.

### 2.5.3 The three-minute full hang on load
**Symptom:** the site "just reloaded for three minutes" — a complete freeze.
**Diagnosis (via headless-Chrome bisection):** the `guard()` function installed a
`MutationObserver` on `document.body` and its callback wrote to the body's class,
which re-triggered the observer — an infinite microtask loop that starved the
`load` event.
**Fix:** the observer now watches only `childList`, disconnects itself while it
performs its own writes, and reconnects afterward; a low-frequency `setInterval`
provides a safety re-assert. The page loads normally.

### 2.5.4 Broken accessibility-statement link
The "accessibility statement" link pointed at `#` and led nowhere. It was wired
to open a modal containing a full WCAG-style accessibility statement
(`#a11yStatementLink` → `openModal(...)` in `app.js`).

### 2.5.5 Market-hours API economy
**Request:** stop generating API calls after the market closes, *unless* the user
is on a higher tier (the 30-minute and 15-minute refresh subscriptions), which
should keep refreshing after hours.
**Implementation:** `marketOpen()` computes US Eastern market minutes
(Mon–Fri 09:30–16:00 via `toLocaleString` with `America/New_York`);
`pausedForClose(tier)` pauses refresh only for slower tiers when the market is
closed; the live-data refresh returns early and stamps "Markets closed" when
paused. The same pause is enforced server-side in `data.py`.

### 2.5.6 The neon goodbye animation (no emojis)
**Request evolution:** change the logout farewell to "Goodbye, friend" with a
smiley + wave; then explicitly *not* an Apple emoji wave but a custom
hand-drawn SVG with a neon line outline, hollow and transparent inside; and a
hard rule of **no emojis anywhere in the UI**.
**Implementation:** two inline SVGs (a smiley face and a waving hand) drawn as
stroked paths with `currentColor`, given a neon glow via layered
`drop-shadow` filters and gentle bob/wave keyframe animations.

### 2.5.7 De-vibe-coding the codebase
Per the founder's "developer's hell" feedback, all decorative banner comments
were replaced with normal human comments and file headers, and the code was
given textual/visual structure for an external reader — verified behavior-
identical per 2.4. The `app.js` reformat had to be done by hand because its size
exceeded a single agent's output budget.

### 2.5.8 Cloud-hosting security hardening
**Request:** prepare for cloud hosting with maximum security — no API keys
exposed, the Python unreadable from the page, data files not downloadable, and
the whole thing served from a server. This produced the FastAPI backend
(Part 5), the data extractor that moves datasets into gitignored `private_data/`,
the per-tier server-side rate limiting and market-hours pause, the security-
headers/HTTPS/CORS middleware, brute-force throttling, JWT revocation, and the
CI security workflow. The honest caveat was communicated and recorded: front-end
JavaScript is always readable by the browser; only keys, Python, and bulk data
can truly be hidden — and those are.

### 2.5.9 Login lands on the Dashboard; test account; beta key
Login was changed to always open the Dashboard (not the last-visited page) via a
`window.TF.home` entry point. A `test1` account was seeded locally (in the
gitignored `auth_seed.js`) and a beta invite key was provided for trials.

### 2.5.10 GitHub upload with secret-safety gate
Before pushing, every sensitive path (`.env`, `auth_seed.js`, `users.db`,
`private_data/*`, `.claude/`) was confirmed gitignored *and* never previously
tracked, and a key-pattern scan was run over everything committable. Only then
was the commit pushed.

### 2.5.11 Signup age-gating + real email validation
**Request:** restrict under-age signups (accept 18+, or 13+ with parental
permission) to limit liability, and reject nonsense emails like
`sfdjk@fdsjkfhsdkhj.com` while still accepting legitimate **custom domains**.
**Implementation:** a required consent checkbox on signup; a hard age floor of 13
enforced both client- and server-side; a stricter email-format regex; and a
DNS-over-HTTPS domain-existence check (MX, falling back to A record) that rejects
unregistered domains but accepts any real custom domain, failing **open** if the
DNS service is unreachable so real users are never blocked.

### 2.5.12 The cybersecurity sub-agent and its training
A Claude Code sub-agent was created for attacker-perspective security review,
then **trained** on a curated knowledge base extracted from the founder's
security-research folder (see Part 9).

## 2.6 A note on the environment

Development occurred under real-world constraints worth recording for
reproducibility: the working tree was at one point offloaded by iCloud
("Optimize Mac Storage") into zero-byte placeholder files, which had to be
re-materialized before git could operate; the legacy `tf_env` virtualenv was
broken by a stale conda path; and the sandbox had no outbound network. Where the
pipeline could not be executed end-to-end in this environment, that is stated
honestly in the relevant section rather than asserted as verified.
