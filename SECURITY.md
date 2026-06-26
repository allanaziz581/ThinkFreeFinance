# ThinkFree Finance — Security Program & Data Governance

This document describes the security controls implemented in the platform and the
data-governance policies that govern user data. It is maintained alongside the
code; every control listed here maps to a concrete implementation or a documented
infrastructure dependency.

## 1. Control summary (what is implemented in code)

| Domain | Control | Where |
|--------|---------|-------|
| Input security | Pydantic schema validation; control-char stripping + length caps (`sanitize_text`); parameterized SQL only (no string-built queries); front-end HTML escaping (`esc`/`E`); JSON output auto-encoded | `server/security.py`, `server/db.py`, `webapp/js/*` |
| XSS | httpOnly session cookie (JS cannot read it); strict CSP (`script-src 'self'`); output escaping | `server/main.py`, `auth.py` |
| CSRF | Double-submit token: non-httpOnly `tf_csrf` cookie echoed in `X-CSRF-Token`; required on all state-changing endpoints; SameSite=lax cookies | `server/security.py`, `auth.py`, `webapp/js/boot.js` |
| Authentication | bcrypt password hashing; generic login errors (no account enumeration); constant-time beta-key compare | `server/auth.py` |
| MFA | TOTP (RFC 6238) enrollment + verification with recovery codes (stored only as sha256 hashes); enforced at login | `server/security.py`, `auth.py` |
| Authorization / RBAC | Ordered role hierarchy (user < analyst < admin); `require_role` dependency; least-privilege admin-only audit endpoint; object-ownership checks on session revoke | `server/security.py`, `auth.py` |
| Session management | JWT in httpOnly+Secure+SameSite cookie; per-device session registry; per-session revocation (device logout); "log out everywhere"; sliding refresh; account-wide epoch revocation | `server/auth.py`, `db.py` |
| Secrets | No secrets in source; all from env (`server/.env` / host vars); refuses to boot in prod with placeholder key | `server/config.py`, `main.py` |
| Transport | HTTPS redirect in prod (X-Forwarded-Proto); HSTS; Secure cookies; modern TLS at the host/edge | `server/main.py` |
| Abuse prevention | Per-(IP+account) and per-IP login throttle; signup throttle (protects beta key); global per-IP flood throttle | `server/auth.py`, `main.py` |
| Audit & logging | Tamper-evident hash-chained audit log; auth/profile/MFA/session/export/delete events recorded; admin verification endpoint | `server/security.py`, `db.py`, `auth.py` |
| Data governance | GDPR-style data export; account-deletion workflow with confirmation | `server/auth.py`, `db.py` |
| Dependency security | CI runs detect-secrets + bandit + safety + the project audit; lean dependency surface (MFA/CSRF/audit are stdlib, no new packages) | `.github/workflows/security.yml` |

## 2. Infrastructure controls (provisioned by the operator)

These are not application code; they are configured at the host/edge and are
documented so the deployment is complete:

- **DDoS mitigation & WAF** — Cloudflare in front of the host (Bot Fight Mode,
  managed WAF ruleset, edge rate limiting on `/api/*`). The in-app global throttle
  is a baseline beneath this, not a replacement.
- **TLS certificates** — issued by the host/edge (Let's Encrypt / Cloudflare). Set
  `TF_PRODUCTION=1` so the app emits HSTS and Secure cookies.
- **Secret vault** — production secrets live in the host's secret manager
  (Render/Railway/Fly dashboard or a dedicated vault), injected as env vars. The
  repo only ships `server/.env.example` with placeholders.
- **Secret rotation** — rotate `TF_SECRET_KEY`, `TF_BETA_KEY`, and every
  data-pipeline API key on a schedule and after any suspected exposure. NOTE: the
  beta key was exposed in early git history and must be rotated before launch.
- **Bot detection** — Cloudflare Turnstile on the signup/login forms is the
  recommended next addition (hook documented; not yet wired).

## 3. Data governance

### 3.1 Data we collect (data minimization)
- Account: email, display name, bcrypt password hash, tier, role.
- Behavioral profile: the five quiz answers (age band, experience, goal, horizon,
  loss reaction) used to tailor briefings.
- Accessibility preference (on/off).
- Security metadata: session records (device string, IP, timestamps), MFA secret
  + recovery-code hashes (only if the user enables MFA), and audit-log entries.

We do not collect financial account credentials, brokerage links, government IDs,
or payment data. ThinkFree is a research tool, not a brokerage.

### 3.2 PII handling
- Passwords are never stored or logged in plaintext (bcrypt only).
- MFA secrets and recovery codes are never returned after enrollment (recovery
  codes shown once); recovery codes are stored only as sha256 hashes.
- The session cookie is httpOnly so client JavaScript / XSS cannot read identity.
- Data exports strip the password hash, MFA secret, and recovery hashes.

### 3.3 User rights (self-service)
- **Access / portability:** `GET /api/auth/account/export` returns everything
  stored about the caller as JSON.
- **Erasure:** `POST /api/auth/account/delete` (type "DELETE" to confirm) removes
  the account and all its sessions. Security audit entries are retained as a
  legitimate-interest security record and contain only email + action (never
  profile data, passwords, or secrets); they are preserved intact so the
  tamper-evident hash chain remains verifiable.

### 3.4 Retention
- Accounts: retained until the user deletes them.
- Sessions: retained until revoked or the account is deleted.
- Audit log: retained as a security record; chained for integrity. A future
  retention job may prune entries older than a defined horizon while re-anchoring
  the chain.

### 3.5 Consent
- Age-requirement consent is collected and enforced at signup (18+, or 13+ with
  parental permission; hard floor of 13 server-side).
- A cookie/privacy consent banner and a formal consent-management record are the
  next governance additions for a public (non-invite) launch.

## 4. Compliance readiness

The architecture is built to support future compliance work rather than claiming
certification today:
- **GDPR:** data minimization, export (portability), erasure, consent at signup,
  and an audit trail are implemented. Remaining for full GDPR: a public privacy
  policy, a cookie-consent banner, a data-processing record, and a DPA with any
  sub-processors.
- **HIPAA:** not applicable today (no PHI is collected). If health-adjacent data
  is ever introduced, the encryption-at-rest, access-control, and audit
  foundations here are the starting point.
- **SOC 2-style controls:** access control (RBAC), audit logging, change
  management (CI gates), and least privilege are in place; formal policy
  documentation and evidence collection would follow.

## 5. Security event monitoring

The hash-chained audit log records authentication outcomes (login, login_fail,
mfa_fail), account changes (profile_update, mfa_enabled/disabled), session events
(session_revoke, logout_all), and data events (data_export, account_delete).
`GET /api/auth/admin/audit` (admin role only) returns the recent tail and a
`chain_valid` flag so an operator can confirm the log has not been tampered with.
For production, ship these events to an external SIEM / log sink (Datadog, ELK,
or the host's logging) so they survive instance restarts and are alertable.

## 6. Reporting a vulnerability

Email security@thinkfree.finance with details and reproduction steps. This is a
closed beta; coordinated disclosure is appreciated and we will acknowledge
reports promptly.
