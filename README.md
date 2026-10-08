# ThinkFree Finance

A financial-information project combining Python news processing, economic-reference retrieval, generated explanations, public-record dashboards, and a FastAPI website. It is a research/engineering prototype. Generated explanations and derived statistics need independent review.

## Reproduce the checks

Use Python 3.12 and Node.js 22 or newer. The review environment excludes large embedding-model downloads and paid model requests.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-review.txt
.venv/bin/python -m pytest tests -q
node --test tests/*.test.cjs
.venv/bin/python agents/security_audit.py
```

Tests create isolated synthetic accounts/databases and fixture inputs. They do not use production accounts, secrets, external financial feeds, or paid generation calls. The FAISS test uses deterministic synthetic vectors: it establishes correct indexing/source lookup, not economic answer quality. Test results substantiate the named cases, not a blanket claim of security or factual accuracy.

CI also runs blocking Bandit checks (medium/high severity and confidence) and `pip-audit -r server/requirements.txt`. The repository scanner checks credential patterns; it is not a comprehensive secret detector. Dependency audits depend on the advisory service and fail if the check cannot complete. Review all findings before merging.

## Run the website locally

```sh
.venv/bin/python scripts/extract_data_to_json.py
```

Set `TF_SECRET_KEY` to a freshly generated long random value and `TF_DB_PATH` to a local test database. To seed your own local account, set `TF_ADMIN_EMAIL` and `TF_ADMIN_PASSWORD` before first startup; credentials are never required in committed source. Then run:

```sh
.venv/bin/uvicorn main:app --app-dir server --no-proxy-headers --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app`. The sidebar's **Account security** control supports authenticator enrollment, backup recovery codes, factor disablement with a current code, and revoking other sessions. Credentials and recovered accounts are your responsibility; password-reset/email delivery is not implemented.

The browser serves committed data snapshots extracted into `private_data/`. Running the website does not regenerate every upstream dataset or AI summary. Its in-process economy refresher and separate deployment scheduler have different scopes. See `scheduler/README.md` and `server/refresher.py`; do not infer current data merely from a live web page.

## Resume/evidence map

| Capability | Implementation | Reproducible evidence / limit |
| --- | --- | --- |
| Numerical checks on generated reports | `numeral_validation.py`, `chef_gpt.py` | Tests cover normalization, rounding, unsupported values and bookkeeping exclusion; value matching does not verify meaning or units |
| Checks on website summaries | `webapp/build_news_intel.py`, `webapp/js/app.js` | Mocked-generation integration test verifies unsupported-number summaries are withheld; checks are scoped to the supplied ticker/sector evidence |
| Exclusion of contaminated backtest metrics | `chef_gpt.py` | `tests/test_chef_backtest_suppressed.py`; does not establish a new clean backtest |
| Embedding clustering | `phase4_clustering.py` | Small-batch regression tests exercise clustering with synthetic vectors; sentence-transformer execution needs the full pipeline environment |
| FAISS economic-reference retrieval | `retrieval_index.py`, `GPT_Economy/Reasoning_Report.py` | Round-trip/source mapping tests; full retrieval requires reference assets and embedding API access |
| Website security controls | `server/auth.py`, `server/security.py`, `server/db.py`, `webapp/js/auth.js` | API tests plus JavaScript flow tests cover access, CSRF, MFA, recovery, revocation, audit fields and proxy-header handling |
| Article volume | `phase3_extraction.py`, `pipeline_metrics.py` | Future actual extraction runs produce records; historical 1,000+ articles/day needs dated operating evidence |

A repository does not independently establish authorship, dates of work, historical throughput, production availability, or research impact. The changes documented in [FIXLOG.md](FIXLOG.md) were made during the October 2026 review; do not describe new capabilities as having existed earlier without evidence. Explain your own contribution and any development assistance accurately.

## Run the AI pipeline

The larger `requirements.txt` environment is separate from the lightweight website/review environment. External inputs, source credentials and authorized reference materials are not bundled. Do not expect a fresh checkout to reproduce historical production outputs without them.

The controller stops on failed security/data audit checkpoints and required phase failures, including `--phase` and `--chef-only`. `--skip-audit` is an explicit diagnostic override; output produced with that flag is unaudited. Directly running a component script does not invoke the controller's preflight.

### Reference assets

Prepare a JSON array of authorized text chunks, e.g. `[{"title":"Reference title","text":"Reference passage"}]`. With an embedding API key supplied through the environment:

```sh
.venv/bin/python scripts/build_reference_index.py /path/to/authorized-documents.json
```

**This command sends the supplied text to the configured OpenAI embedding API and incurs API charges.** It is not part of the offline test suite. Both builder and query path use `text-embedding-ada-002`. Keep the index and metadata together in `Economic_Books/FAISS_Store/`; rebuilding with another model requires changing both sides. Use trusted local assets only.

### Website summaries and their limits

`webapp/build_news_intel.py` applies strict numeric membership checks to each generated summary. Unsupported-number outputs are replaced with a review notice; missing ticker evidence also withholds an output. Complete generation failure preserves the existing artifact. Successful outputs carry generation time, check scope and missing-context labels.

The UI labels old saved summaries without check metadata as unverified. It does not retroactively certify them. Regenerate them with actual source inputs/API access before claiming they passed the new checks. Numeric values can still match while referring to the wrong fact, currency, unit, or entity; independent factual/adversarial evaluation remains open. The main Chef report flags numeric issues in its JSON rather than silently correcting facts.

### Observed throughput

Each completed extraction run writes hashed article identifiers, input/processed counts, duration and UTC completion time under ignored `run_metrics/`. Summarize them with:

```sh
.venv/bin/python scripts/summarize_extraction_runs.py
```

The summary deduplicates identifiers across recorded runs by UTC completion date. It measures completed extraction, not unique publications, full model-pipeline throughput, or a historical daily average. No records means no evidence; tests use temporary synthetic logs only.

## Deployment and security boundaries

- Set `TF_PRODUCTION=1`, a strong signing key, persistent `TF_DB_PATH`, and explicit allowed origins.
- Keep Uvicorn `--no-proxy-headers`. By default application rate limits use the socket peer and ignore forwarding headers. Behind an ingress proxy, configure `TF_TRUSTED_PROXY_CIDRS` with **only that deployment's verified proxy networks**. Otherwise users behind one proxy share its limits. Never configure a universal trust range; ensure the ingress strips untrusted forwarding headers. The app walks the chain from the trusted end.
- Limits are in memory and per process. Multiple workers require shared limiter state; a process restart resets counters.
- The MFA secret cannot be replaced while enabled. Recovery codes are consumed atomically. Rate limits also protect setup/disable verification. This does not claim resistance to every stolen-session or phishing scenario.
- New audit records use version 2 hashes covering IP and other recorded event fields. Legacy version 1 records remain verifiable but their IPs were not hashed. Hashes detect covered-field edits/interior deletion; a trusted external checkpoint is required to detect full-history recomputation or tail truncation by a database writer.
- Billing endpoints remain stubs. These repairs do not enable charging or subscriptions.
- No live deployment is verified by the offline suite. Test the intended deployment, proxy configuration and real authorized feeds separately.
