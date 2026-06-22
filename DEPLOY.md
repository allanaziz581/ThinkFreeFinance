# ThinkFree Finance - Deployment & Security Guide

This describes how to host ThinkFree as a real server-backed web app where the
browser receives only a "dumb shell" and everything sensitive (API keys, Python
code, the datasets, auth) stays on the server.

## The security model in one line

> Anything sent to the browser is public. So we send only the UI shell, and keep
> keys, Python, data, and identity on the server, released only to a logged-in user.

What this achieves vs. your goals:

| Goal | Status | How |
|------|--------|-----|
| No API keys exposed | Achieved | Keys live in server env vars (`server/.env` / host dashboard), read only by Python. Never sent to the browser. |
| Python code unreadable | Achieved | Python runs server-side and is never served. Keep `.py` out of `webapp/`. |
| Data files not downloadable | Achieved | Datasets moved to `private_data/` (not web-served) and returned only via `/api/data/*` behind login. The server also hard-404s any `*_data.js` path. |
| Tiers / auth not bypassable | Achieved | Login, sessions, and tier cadence are enforced server-side; editing the browser cannot change them. |
| "Animated JavaScript" unreadable | Not possible | The browser must download JS to run it. We minify it, but UI/animation code is always readable. It contains no secrets or bulk data, so this is fine. |

## Local run (do this first)

```bash
# 1. Clean virtualenv (do NOT reuse tf_env)
python3 -m venv server/.venv
server/.venv/bin/pip install -r server/requirements.txt

# 2. Secrets
cp server/.env.example server/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into TF_SECRET_KEY
# edit server/.env: set TF_SECRET_KEY, TF_BETA_KEY, keep TF_PRODUCTION=0 for local

# 3. Build the gated datasets from the existing webapp/js/*_data.js bundles
python3 scripts/extract_data_to_json.py        # writes private_data/*.json + manifest.json

# 4. Run
server/.venv/bin/uvicorn main:app --app-dir server --reload --port 8000
# open http://localhost:8000
```

Quick checks that gating works:

```bash
curl -i http://localhost:8000/api/data/bundle        # expect 401 (not logged in)
curl -i http://localhost:8000/js/data.js             # expect 404 (blocked)
curl -i http://localhost:8000/api/auth/me            # expect 401
```

## Production hosting (recommended path)

1. **Push to GitHub** (private repo). Confirm `server/.env`, `private_data/*`, and
   `users.db` are gitignored (they are, via the scoped `.gitignore` files).
2. **Deploy to Render / Railway / Fly.io:**
   - Start command: `uvicorn main:app --app-dir server --host 0.0.0.0 --port $PORT`
   - Build command: `pip install -r server/requirements.txt`
   - Set env vars in the dashboard (NOT a committed file): `TF_SECRET_KEY`,
     `TF_BETA_KEY`, `TF_PRODUCTION=1`, `TF_ALLOWED_ORIGINS=https://your-domain`,
     plus the data-pipeline keys.
   - Run `scripts/extract_data_to_json.py` as part of the build or upload
     `private_data/` as a persistent volume.
3. **Put Cloudflare in front** of the host:
   - Automatic HTTPS/TLS, HTTP/2.
   - Enable the WAF (managed ruleset) and Bot Fight Mode.
   - Enable "Always Use HTTPS" and rate limiting on `/api/*`.
   - This is the "backend security safe for beta" layer (DDoS, bots, TLS).

## Pre-launch security checklist

- [ ] `TF_SECRET_KEY` is a fresh 48+ char random value (the app refuses to start in production with the placeholder).
- [ ] `TF_PRODUCTION=1` in prod, so cookies are `Secure` and HSTS is sent.
- [ ] **Rotate every data-pipeline API key** (LegiScan, Open States, Finnhub, OpenAI) before launch. Any key that was ever committed, shared, or pasted into a config must be considered burned and regenerated.
- [ ] Confirm no key string appears anywhere under `webapp/` (it should not): `grep -rEi "api[_-]?key|secret|token" webapp/`.
- [ ] `private_data/`, `server/.env`, `users.db` are NOT in git: `git status --ignored`.
- [ ] The old `webapp/js/*_data.js` are removed from the deployed shell once the front-end fetches from `/api/data/*` (the server blocks them regardless).
- [ ] Cloudflare WAF + rate limiting on `/api/auth/*` (slows credential-stuffing).
- [ ] Backups of `users.db` (or move to managed Postgres before scaling past beta).

## What is still TODO (front-end wiring)

The server is built and gates the data. The remaining step is the browser side:
the shell must (1) call `/api/auth/*` for real login instead of localStorage, and
(2) fetch `/api/data/bundle` (and `/api/data/state`, `/api/data/live`) after login
and set the `window.*_DATA` globals before the page scripts run. This is best done
with the server running locally so the login -> data -> render flow can be tested
end to end.
