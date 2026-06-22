# Part 11 — Security Model & Deployment

## 11.1 The security model in one line

> Anything sent to the browser is public. So the hosted app sends only the UI
> shell and keeps keys, Python, data, and identity on the server, released only to
> a logged-in user.

## 11.2 What the model achieves

| Goal | Status | How |
|------|--------|-----|
| No API keys exposed | Achieved | Keys live in server env vars (`server/.env` / host dashboard), read only by Python; never sent to the browser |
| Python code unreadable | Achieved | Python runs server-side and is never served; `.py` stays out of `webapp/` |
| Data files not downloadable | Achieved | Datasets moved to `private_data/` (not web-served), returned only via `/api/data/*` behind login; the server hard-404s any `*_data.js` path |
| Tiers / auth not bypassable | Achieved | Login, sessions, and tier cadence are enforced server-side; editing the browser cannot change them |
| "Animated JavaScript" unreadable | Not possible | The browser must download JS to run it; it is minified, but UI/animation code is always readable. It contains no secrets or bulk data, so this is acceptable |

The honest caveat is stated plainly to stakeholders: front-end JavaScript is
always readable by the browser. Only keys, Python, and bulk data can truly be
hidden — and those are.

## 11.3 Authentication & session security

- **Passwords** are hashed with **bcrypt** (slow by design). Plaintext is never
  stored.
- **Sessions** are **PyJWT** tokens placed in a cookie that is **httpOnly**
  (JavaScript, and therefore an XSS payload, cannot read it), **Secure** in
  production, and **SameSite=lax**.
- **JWT revocation:** the user row carries a `token_valid_after` epoch; a token
  whose `iat` predates it is rejected. Logout bumps this value to "now," which
  immediately invalidates any older or stolen cookie.
- **Brute-force throttling (in-memory):** login is limited per IP+email
  (5 / 15 min) and per IP (a 20 / 15 min spray cap); signup is limited per IP
  (10 / hour) to protect the closed-beta invite key. Failures clear on success.
- **Beta-key check** uses `hmac.compare_digest` (constant time) so the invite key
  cannot be guessed by timing.

## 11.4 Signup integrity controls

- **Age gating (liability):** a required consent checkbox ("I confirm I am 18 or
  older, or I am at least 13 and have explicit permission from a parent or
  guardian"), plus a hard floor of 13 enforced **both** client-side (the quiz
  rejects ages below 13) and server-side (the profile endpoint re-checks). Neither
  can be bypassed by editing the browser.
- **Email validity:** a stricter format regex (real TLD required) on both client
  and server, plus a client-side **DNS-over-HTTPS domain-existence check** (MX,
  falling back to A record) that rejects unregistered nonsense domains while
  accepting any real **custom** domain. It fails **open** if DNS is unreachable so
  legitimate users are never locked out. The documented limitation: this catches
  nonexistent domains, not typos at real domains; true mailbox verification would
  require sending a confirmation code (a future enhancement).

## 11.5 Transport & HTTP hardening (server middleware)

- **Security headers** on every response: Content-Security-Policy, HSTS
  (Strict-Transport-Security), X-Frame-Options / frame-ancestors,
  X-Content-Type-Options.
- **HTTPS redirect** in production via `X-Forwarded-Proto` (defaults to https to
  avoid redirect loops; exempts `/healthz`).
- **CORS** wired from `config.ALLOWED_ORIGINS` (inert under a single-origin
  deployment, ready if the front end and API are ever split).
- **Per-tier rate limiting + market-hours pause** on the live-data endpoint
  (`_last_live` tracking; zoneinfo-based market check), so lower tiers stop
  generating API calls after the close while premium tiers keep refreshing.
- The server **refuses to boot in production** if `TF_SECRET_KEY` is still the
  placeholder value.

## 11.6 Secret hygiene

- Secrets live only in gitignored `.env` (root, for the pipeline) and
  `server/.env` (for the backend), or in the host's dashboard env vars.
- Gitignored and confirmed never-tracked: `.env`, `server/.env`,
  `webapp/js/auth_seed.js` (holds password hashes), `private_data/*`,
  `server/users.db`, and `.claude/` (except the security agent, which is
  deliberately re-included for sharing — see Part 9.10).
- Before every push, sensitive paths are verified gitignored *and* absent from
  the tracked tree, and a key-pattern scan is run over everything committable.

## 11.7 CI security gate

`.github/workflows/security.yml` runs on push/PR and executes **detect-secrets**,
**bandit**, **safety**, and the project's own `agents/security_audit.py`. The
audit `sys.exit(1)`s on FAIL, so a failing security check blocks the pipeline.

## 11.8 Local run

```bash
# 1. Clean virtualenv (do NOT reuse tf_env)
python3 -m venv server/.venv
server/.venv/bin/pip install -r server/requirements.txt

# 2. Secrets
cp server/.env.example server/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # -> TF_SECRET_KEY
# edit server/.env: set TF_SECRET_KEY, TF_BETA_KEY, keep TF_PRODUCTION=0 locally

# 3. Build the gated datasets from the webapp/js/*_data.js bundles
python3 scripts/extract_data_to_json.py    # writes private_data/*.json + manifest.json

# 4. Run
server/.venv/bin/uvicorn main:app --app-dir server --reload --port 8000
# open http://localhost:8000
```

Gating sanity checks:

```bash
curl -i http://localhost:8000/api/data/bundle    # expect 401 (not logged in)
curl -i http://localhost:8000/js/data.js         # expect 404 (blocked)
curl -i http://localhost:8000/api/auth/me        # expect 401
```

## 11.9 Production hosting (recommended path)

1. Push to a **private** GitHub repo; confirm `server/.env`, `private_data/*`, and
   `users.db` are gitignored.
2. Deploy to Render / Railway / Fly.io:
   - Start: `uvicorn main:app --app-dir server --host 0.0.0.0 --port $PORT`
   - Build: `pip install -r server/requirements.txt`
   - Set env vars in the dashboard (not a committed file): `TF_SECRET_KEY`,
     `TF_BETA_KEY`, `TF_PRODUCTION=1`, `TF_ALLOWED_ORIGINS=https://your-domain`,
     plus the data-pipeline keys.
   - Run `scripts/extract_data_to_json.py` at build time or mount `private_data/`
     as a persistent volume.
3. Put **Cloudflare** in front: automatic HTTPS/TLS, HTTP/2, WAF (managed
   ruleset), Bot Fight Mode, "Always Use HTTPS," and rate limiting on `/api/*`.
   This is the DDoS/bot/TLS layer that makes the backend "safe for beta."

## 11.10 Pre-launch security checklist

- [ ] `TF_SECRET_KEY` is a fresh 48+ char random value (app refuses to start in prod with the placeholder).
- [ ] `TF_PRODUCTION=1` in prod (cookies `Secure`, HSTS sent).
- [ ] **Rotate every data-pipeline API key** (LegiScan, Open States, Finnhub, OpenAI, etc.) before launch. Any key ever committed, shared, or pasted into a config is considered burned.
- [ ] No key string appears anywhere under `webapp/`: `grep -rEi "api[_-]?key|secret|token" webapp/`.
- [ ] `private_data/`, `server/.env`, `users.db` are not in git: `git status --ignored`.
- [ ] The old `webapp/js/*_data.js` are removed from the deployed shell once the front end fetches from `/api/data/*` (the server blocks them regardless).
- [ ] Cloudflare WAF + rate limiting on `/api/auth/*`.
- [ ] Backups of `users.db` (or move to managed Postgres before scaling past beta).

## 11.11 Known not-yet-done (by design)

- Password reset and email verification (needs an email provider; arguably
  redundant for an invite-key beta).
- The TLS certificate itself (the host's responsibility; set `TF_PRODUCTION=1`).
- End-to-end run of the extractor + uvicorn in this sandbox (no network, broken
  legacy venv); the backend Python all compiles cleanly and the JS parses, but
  the founder must run the full login → data → render flow on a real machine.
