# Fix log

## 2026-10-08: Close website access and MFA verification gaps

**Seen:** Local review found an anonymously accessible core data bundle, an MFA login that advanced without a challenge, and enabled-factor replacement through the setup endpoint. Forwarding headers could change the application rate-limit identity; IP edits escaped audit verification.

**Cause:** `data.js` was absent from the static blocklist. The frontend treated every HTTP 200 login response as authenticated. Setup overwrote active MFA state. The backend trusted arbitrary forwarding headers and the original audit hash omitted IP.

**Fix:** `server/main.py` blocks the missing bundle; `server/auth.py`/`server/db.py` prevent active-factor replacement, atomically confirm enrollment and consume recovery codes, and throttle factor verification. `webapp/js/auth.js` completes code/recovery login; `security-settings.js` exposes enrollment and session controls. Failed data loads stay locked and can retry. `server/security.py` resolves IPs only across configured trusted proxies. New audit rows cover IP using a versioned format; legacy hashes are preserved. Backend dependencies were updated after the dependency audit reported vulnerable pins.

**Checked:** See the final verification results recorded below. Tests use synthetic accounts and isolated databases. No production accounts, deployed site or real financial operations were tested.

**Open:** Deployment-specific proxy configuration; shared throttling for multiple workers; independent security review. Audit hashes are not externally anchored and cannot prove absence of recomputed/truncated history.

## 2026-10-08: Apply numerical checks to website-generated summaries

**Seen:** Main report checks did not run on the separate website summary generator. Small integer percentages were ignored, and failed generation could replace an existing output.

**Cause:** Separate output paths; numeric filtering discarded all small integers; website generator lacked scoped validation and an empty-output failure gate.

**Fix:** Explicit financial values are checked even in legacy mode; report and website callers use strict mode. Website checks use ticker-scoped supplied evidence, withhold failing/missing-evidence outputs, record generation/check metadata and disclose unverified cached summaries. Full generation failure preserves the prior file. Report bookkeeping is excluded from prose validation.

**Checked:** Tests exercise actual website generation using mocked API responses and temporary source/output files, plus numeric edge cases and existing report regression tests.

**Open:** Numeric membership is not factual entailment, attribution or unit verification. Real model quality and cached-summary regeneration need authorized source/model runs; no paid calls were made during this repair.

## 2026-10-08: Make pipeline checks enforceable and reviewable

**Seen:** Scanner exit logic read a nonexistent field, scanner prefixes could flag themselves, normal pipeline execution ignored failed audits, and small embedding batches crashed. FAISS assets were unavailable to reviewers and the old retrieval adapter used outdated imports/empty row mappings.

**Cause:** Inconsistent result contracts and ignored return values; fixed minimum cluster count; missing reproducible retrieval setup.

**Fix:** Replaced the credential-pattern scanner with a redacting, offline repository scan whose result drives its exit status. CI runs blocking tests, static analysis and backend dependency checks. All controller generation entry points enforce preflight unless explicitly skipped. Clustering handles empty/singleton/small batches. Added a shared FAISS adapter, round-trip tests, and an explicit API-backed reference builder; economic reasoning now uses the shared adapter. Added review instructions and actual extraction-run logging without inventing historical volume.

**Checked:** Final local check results below. Scanner coverage is explicitly limited; runtime credentials are not read. FAISS tests use synthetic vectors and real FAISS indexing, not an embedding API.

**Open:** Full model pipeline execution requires external inputs and credentials. Historical article volume remains unverified until dated run evidence is supplied. The large ML environment is separate from the pinned offline review environment.

## Final local verification — 2026-10-08

- 103 Python tests passed (including existing regressions, security API cases, scoped website generation, extraction logging and real FAISS round trips); none skipped.
- Four JavaScript flow tests passed, including MFA challenge/recovery and retry after unauthorized data loading.
- Repository credential-pattern scan: PASS, zero findings across the complete checkout.
- Bandit: no findings at the configured medium/high severity and confidence gate.
- Backend pip-audit: no known vulnerabilities reported for the updated requirements at verification time.
- Modified/new Python syntax and changed JavaScript syntax checked; git diff whitespace check passed.
- Browser: incorrect synthetic-account MFA code remained locked, valid code reached the post-login notice, and the actual security dialog loaded in a test-only local harness. No liability waiver was accepted; setup/disable logic was exercised through isolated API tests.
- No production deployment or paid API runs; historical throughput remains unverified.
