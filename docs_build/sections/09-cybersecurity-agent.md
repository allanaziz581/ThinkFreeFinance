# Part 9 — The Cybersecurity Sub-Agent and Its Training

ThinkFree ships with a development-time **AI sub-agent**: an attacker-perspective
security reviewer defined as a Claude Code sub-agent. This part documents the
agent's definition, its operating rules, and — in full — the knowledge base it
was **trained** on (extracted from the founder's curated security-research
folder). "Training" here means embedding distilled, verified knowledge into the
agent's prompt and reference files; a Claude Code sub-agent learns through its
system prompt plus the files it loads, not through fine-tuning.

## 9.1 Agent definition

**File:** `.claude/agents/cybersecurity-agent.md`

The file is a Markdown document with YAML front-matter (the agent's metadata) and
a system-prompt body. Front-matter fields:

| Field | Value | Meaning |
|-------|-------|---------|
| `name` | `cybersecurity-agent` | The invocable agent name |
| `description` | attacker-perspective reviewer; triggers on "check security", "audit before launch", etc. | When the harness auto-selects it |
| `tools` | `Read, Grep, Glob, Bash, WebFetch` | Read + search + run scanners + fetch references |
| `model` | `inherit` | Uses the session model (so reviews get the strongest model) |

The agent runs in a read/search/execute posture — it audits and reports, and can
drive scanners — but is not given Edit/Write by default, so it cannot silently
change code.

## 9.2 Operating rules (baked into the prompt)

1. **Never break functionality.** Any proposed fix must preserve behavior; if it
   changes behavior, that is called out explicitly. This mirrors the project-wide
   constraint in Part 2.4.
2. **Authorized scope only.** It audits ThinkFree's own repository and its own
   running instance. It never uses the offensive tooling against third parties.
3. **Verify before you alarm.** A finding is real only with an exact `file:line`
   and a concrete attack path; speculation is labeled as such.
4. **Defense in depth.** Client-side checks are UX, never security; controls that
   matter are enforced server-side; the browser is assumed hostile.
5. **No secrets in output.** It never prints a real key, token, password, or hash.

## 9.3 Stack translation (why generic advice was not enough)

The source material assumes a Supabase/Postgres "Row-Level Security" stack.
ThinkFree is **FastAPI + stdlib SQLite + bcrypt + PyJWT**. The agent was given an
explicit map so it audits the real architecture: the "enable RLS" lesson becomes
**"every `/api/*` endpoint must scope results to the authenticated `current_user`
and must never trust an id, email, or tier sent by the client"** — the FastAPI/
SQLite way to prevent IDOR / broken access control. The agent's prompt contains a
full description of ThinkFree's real components (the static gate, the JWT cookie,
the gated `private_data/` endpoints, the tier model, the market-hours pause).

## 9.4 The training corpus (source folder)

The knowledge was extracted from `ThinkFree/Agents/Cybersecurity Sub Agent/`,
which contains three written guides and a set of GitHub repositories:

**Written guides (read in full):**

- *How to Prevent Vibe Coded Apps From Being Hacked: Security Checklist and
  Prompts* (Giga AI / Namanyay Goel) — the three highest-leverage controls:
  row-level security / access control, rate limiting, and keeping API keys out of
  code.
- *I'm a Bug Hunter. Here is how I prevent my Vibe-Coded apps from getting
  hacked.* (BehiSec) — the attacker mindset ("security is finding the exceptions
  developers forgot"), eight infrastructure mistakes, and a pre-launch checklist
  (no secrets in front end, all routes verify auth server-side, users can only
  access their own data — test with two accounts, dependencies current, `.env`
  gitignored, DB not internet-exposed, debug off in prod).
- *How to ACTUALLY make your (vibe coded) apps secure (from an actual hacker)*
  (cryptoviksant) — CAPTCHA/bot gating, HTTPS everywhere, sanitize every input on
  both sides, update dependencies (including transitive), WAF, logging/monitoring,
  and the closing advice: "Read the OWASP Top 10 and dig deeper."

**Repositories (inspected directly):**

| Repo | What it is | How it trained the agent |
|------|-----------|--------------------------|
| vibe-guard | 28-rule static scanner (TypeScript) | Source of the rule checklist (9.5) |
| vibe-pen-tester / vibe-coding-penetration-tester | LLM multi-agent pen-testers (Python) | Source of the active-test playbook (9.6) |
| PayloadsAllTheThings | Payloads per vuln class | Source of the payload cheatsheet (9.7) |
| SecLists | Wordlists (passwords, discovery, fuzzing) | Source of the wordlist path index (9.7) |
| public-pentesting-reports | Real reports (Cure53, Doyensec, Bishop Fox, Trail of Bits, NCC) | Reference for finding write-up style |
| PentestGPT | USENIX Security 2024 autonomous pen-test agent | Methodology reference |
| awesome-pentest | Curated tool index | Reference index |
| supabase-js | Supabase client | **Excluded** — not ThinkFree's stack |

## 9.5 Knowledge file 1 — `vibe-guard-rules.md` (the 28-rule checklist)

Extracted from vibe-guard's `src/rules/*.ts`, this file distills all 28 static
rules into a grep-driven checklist. Each rule carries a severity, a plain-English
description of the dangerous code shape, 2–4 concrete signatures to grep for, and
the fix. The 28 rules:

**Web/application (20):** broken-access-control, missing-authentication,
sql-injection, xss-detection, csrf-protection, exposed-secrets,
hardcoded-sensitive-data, unvalidated-input, directory-traversal,
insecure-file-upload, insecure-deserialization, insecure-session-management,
insecure-random-generation, open-cors, insecure-http, missing-security-headers,
insecure-configuration, insecure-error-handling, insecure-logging,
insecure-dependencies.

**Infrastructure (3):** dockerfile-security, container-registry-security,
kubernetes-security.

**AI-specific (5):** prompt-injection-detection, ai-agent-access-control,
ai-data-leakage-prevention, ai-generated-code-validation, mcp-server-security.
These matter because ThinkFree runs GPT / Chef GPT, so prompt injection and
AI-data-leakage are live risks, not hypotheticals.

A notable direct hit: the **insecure-random-generation** rule flags non-crypto
randomness used as a security boundary — which is exactly what the static-mode
gate's `cyrb53` hash is. The agent therefore knows to flag any reliance on
`cyrb53` for real security (it is acceptable only as soft UX).

## 9.6 Knowledge file 2 — `pentest-playbook.md` (active-test methodology)

Extracted from the two LLM pen-testers, this file documents *how* to actively
test each vulnerability class and, crucially, *how to validate a finding before
reporting it* (the swarm explicitly drops unvalidated findings).

- **Architecture:** discovery → a specialist agent per vuln class → validation →
  report.
- **Vuln classes documented:** XSS (browser-instrumented `window.__xss_triggered`
  confirmation plus reflection checks across four contexts), SQL injection
  (error/auth-bypass/UNION/time-based with the real SQL error-string set), CSRF
  (token + SameSite inspection, PoC generation as evidence), Authentication
  (weak policy, insecure cookies, session-id-in-URL, enumeration, missing
  lockout, default creds, client-side bypass), IDOR (id-parameter probing with
  access-denied suppression logic), and SSRF (URL/param discovery with internal-IP
  confirmation).
- **Validation discipline:** a two-stage gate (LLM expert review, then a
  deterministic re-check) so plausible-but-wrong findings do not survive.
- **SSRF defenses worth copying:** block targets that resolve to private/loopback
  IPs, and only trust `X-Forwarded-For` behind a verified proxy.

## 9.7 Knowledge file 3 — `payloads-cheatsheet.md` (payloads + wordlists)

Extracted from PayloadsAllTheThings and SecLists, with an authorization-only
notice at the top. It provides the canonical, compact payload set per class —
XSS, SQLi, SSRF, IDOR, command injection, directory traversal, CSRF, insecure
file upload, and JWT attacks (none-algorithm, RS256→HS256 confusion, null
signature, weak-secret brute force, `kid`/`jku` injection) — and an index of the
most useful specific SecLists wordlist paths (common passwords, default creds,
web-content discovery, usernames, vuln-specific fuzzing lists). The JWT section is
directly relevant because ThinkFree's sessions are JWTs.

## 9.8 How the agent uses its training

The agent's prompt instructs it to **read all three knowledge files at the start
of every audit**, then work the checklist top-down in priority order: broken
access control → secret leakage → rate limiting → injection → transport/headers
→ infrastructure/deploy → dependencies. Its output is a structured report: a
PASS/FAIL verdict, findings (each with severity, OWASP category, `file:line`, the
attack, the minimal non-breaking fix, and a confidence level), manual tests to
run (e.g. the two-account IDOR test), and pre-launch reminders (key rotation,
production flags). It can also drive the existing Python static scanner
`agents/security_audit.py` (Part 8).

## 9.9 Relationship to the runtime verification agents

This sub-agent is a **development-time reviewer** (it reasons over the code and
helps an engineer). It complements — but is distinct from — the **runtime**
Python verification agents in `agents/` (Part 8), which execute inside the data
pipeline and gate it with pass/fail verdicts. Together they implement the
blueprint's "two LLMs catch more than one" principle: independent review plus
automated static gating.

## 9.10 Distribution note

The agent and its knowledge base live under `.claude/`, which is gitignored, so
they are local to the development machine and were not pushed to the public
repository. Making them shareable would require either relocating them or adding
a scoped gitignore exception; this is a deliberate, reversible choice.
