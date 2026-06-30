# vibe-guard Security Rules Reference

Extracted from the vibe-guard scanner (Devjosef/vibe-guard), 28 static rules. Use as a grep-driven checklist.

---

## 1. broken-access-control (high)
Detects missing authorization checks and insecure direct object references.

**Detects:** Direct use of user-supplied IDs in DB/file operations without ownership verification; role assignment from request body.
- `findById(req.params.`
- `readFile(req.` / `writeFile(req.` / `unlink(req.`
- `req.session.user = req.body.`
- `role = req.body.`

**Fix:** Add authorization middleware; verify user owns the resource before any DB or file operation; never assign roles from user input.

---

## 2. missing-authentication (high)
Detects potentially unprotected routes and endpoints.

**Detects:** Sensitive route handlers registered without an auth middleware argument.
- `app.get('/admin/` without auth middleware
- `app.get('/user/` / `app.get('/dashboard/` without auth
- `@app.route('/dashboard/` (Flask)
- `@GetMapping('/admin/`

**Fix:** Add auth middleware to every sensitive route (`express-jwt`, `passport`, `@login_required`, `@PreAuthorize`, `[Authorize]`).

---

## 3. sql-injection (high)
Detects potential SQL injection vulnerabilities.

**Detects:** String concatenation or interpolation of user input directly into SQL query strings.
- `query = "SELECT" + req.body.`
- `` query = `SELECT...${req.params.id}` ``
- `f"SELECT...{request.args['id']}"` / `"SELECT...{}".format(`
- `.where("col =" + req.query.`

**Fix:** Use parameterized queries/prepared statements exclusively. For ORMs: `{ where: { id: req.params.id } }` (Sequelize); `session.query(User).filter(User.id == user_id)` (SQLAlchemy).

---

## 4. xss-detection (critical)
Detects potential cross-site scripting (XSS) vulnerabilities.

**Detects:** Unsanitized user input written to HTML sinks or dangerous DOM APIs.
- `.innerHTML = req.` / `.outerHTML = req.`
- `document.write(req.`
- `eval(req.`
- `dangerouslySetInnerHTML={{ __html: req.`
- `echo $_GET['` (PHP)

**Fix:** Use `textContent` instead of `innerHTML`; sanitize with `DOMPurify.sanitize()`; use `htmlspecialchars()` in PHP; use Angular's `DomSanitizer`.

---

## 5. csrf-protection (high)
Detects missing CSRF protection and unsafe cookie configurations.

**Detects:** POST forms without CSRF tokens; cookies with insecure flags; CSRF-exempt decorators.
- `<form method="post">` without `<input name="csrf"`
- `httpOnly: false` / `secure: false` / `sameSite: 'none'`
- `axios.post(url)` without CSRF header
- `@csrf_exempt`

**Fix:** Add CSRF tokens to all state-changing forms; use `csurf` middleware; set cookies with `sameSite: 'strict'`, `httpOnly: true`, `secure: true`.

---

## 6. exposed-secrets (critical)
Detects exposed API keys, tokens, and credentials.

**Detects:** Literal credential strings matching known vendor formats.
- `AKIA[0-9A-Z]{16}` — AWS Access Key
- `ghp_[a-zA-Z0-9]{36}` — GitHub PAT
- `AIza[0-9A-Za-z_-]{35}` — Google API key
- `sk_live_[a-zA-Z0-9]{24}` — Stripe live key
- a PEM private-key armor line (five dashes, then BEGIN, then PRIVATE KEY, then five dashes; literal omitted so this reference doc does not itself trip secret scanners)
- `xox[baprs]-` — Slack token

**Fix:** Move all credentials to environment variables; rotate any exposed secret immediately and purge from git history using `git filter-branch` or BFG Repo Cleaner.

---

## 7. hardcoded-sensitive-data (critical)
Detects hardcoded sensitive information in configuration files.

**Detects:** Database connection strings, encryption keys, and API secrets assigned as literals.
- `database_url = 'postgres://`
- `mongodb://user:pass@host`
- `encryption_key = '` (short literal)
- the RSA variant of the PEM private-key armor line (BEGIN RSA ... PRIVATE KEY; literal omitted for the same reason)
- `stripe_secret = 'sk_live_`

**Fix:** Move to environment variables (`process.env.*`, `os.environ`); use AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault for production secrets.

---

## 8. unvalidated-input (medium)
Detects potentially unvalidated user input flowing into security-sensitive sinks.

**Detects:** Raw request data used in exec, eval, filesystem, or HTML operations without validation.
- `eval(req.` / `exec(req.`
- `os.system(request.`
- `spawn(req.`
- `readFile(req.` / `writeFile(req.`
- `include($_GET[`
- `${req.body.` in template literals

**Fix:** Validate all input with Joi, express-validator, pydantic, or WTForms; use parameterized queries for DB; use `path.join()` for file paths.

---

## 9. directory-traversal (high)
Detects potential directory traversal vulnerabilities.

**Detects:** User-supplied filenames or paths passed directly to filesystem functions.
- `readFile(req.query.`
- `res.sendFile(req.params.`
- `"./uploads/" + req.`
- `fopen($_GET['file']` / `include($_POST['page']`
- `open(request.args['file']`
- `require(req.params.`

**Fix:** Resolve paths with `path.resolve()` + `path.normalize()`; validate the resolved path starts with the allowed base directory; use `realpath()` in PHP; whitelist allowed filenames.

---

## 10. insecure-file-upload (high)
Detects insecure file upload implementations.

**Detects:** File uploads with no type filtering, dangerous extension acceptance, or uncontrolled filenames.
- `file.mv('./uploads/' + file.name)`
- `move_uploaded_file($_FILES[`
- `multer({` without `fileFilter`
- `.any()` — accepts any file type
- Dangerous extensions: `.php`, `.exe`, `.sh`, `.jsp`, `.asp`

**Fix:** Implement `fileFilter` to whitelist safe MIME types; enforce file size limits; generate random unique filenames; block dangerous extensions server-side.

---

## 11. insecure-deserialization (high)
Detects potentially unsafe deserialization of user input.

**Detects:** User-controlled data passed to eval, pickle, PHP unserialize, or unsafe YAML load.
- `eval(req.` / `vm.runInNewContext(req.` / `Function(req.`
- `pickle.loads(req.`
- `unserialize($_GET[`
- `yaml.load(req.` / `yaml.unsafe_load(req.`
- `ObjectInputStream(req.`

**Fix:** Never deserialize untrusted input; use `yaml.safe_load`; avoid `pickle` with user data; if using `JSON.parse`, validate the result schema before trusting it.

---

## 12. insecure-session-management (high)
Detects insecure session management configurations and practices.

**Detects:** Weak or hardcoded session secrets, insecure cookie flags, in-memory session stores.
- `secret: 'keyboard cat'` / any secret shorter than 20 chars
- `secure: false` / `httpOnly: false`
- `store: MemoryStore` / `new MemoryStore()`
- `req.session.user = req.body.`
- `SESSION_COOKIE_SECURE = False`

**Fix:** Use 32+ char secrets from `process.env.SESSION_SECRET` or `crypto.randomBytes(32)`; set `secure: true`, `httpOnly: true`, `sameSite: 'strict'`; use Redis or DB session store in production.

---

## 13. insecure-random-generation (medium)
Detects insecure random number generation used for security purposes.

**Detects:** `Math.random()` or predictably-seeded generators used for tokens, IDs, or credentials.
- `token = Math.random()`
- `Math.random().toString(36)` for tokens
- `random.seed(123)` / `random.seed(time.time())`
- `rand()` / `mt_rand()` in PHP for security use

**Fix:** Use `crypto.randomBytes(32)` or `crypto.randomUUID()` in JS; `secrets.token_hex(32)` in Python; `SecureRandom` in Java; `random_bytes(32)` in PHP.

---

## 14. open-cors (high)
Detects overly permissive CORS configurations.

**Detects:** Wildcard origin allowing any domain to make credentialed cross-origin requests.
- `cors({ origin: '*' })` / `cors()` (no args)
- `cors({ origin: true })`
- `Access-Control-Allow-Origin: *`
- `@CrossOrigin(origins = "*")`
- `CORS_ALLOW_ALL_ORIGINS = True`
- `AllowAnyOrigin()`

**Fix:** Specify exact origins: `cors({ origin: 'https://yourdomain.com' })`; never combine wildcard origin with `credentials: true`.

---

## 15. insecure-http (medium)
Detects insecure HTTP usage instead of HTTPS.

**Detects:** Plaintext HTTP URLs, HTTP server creation, insecure cookie/transport flags.
- `api_url = 'http://`
- `fetch('http://` / `axios.get('http://`
- `http.createServer()` / `require('http')`
- `secure: false` / `httpOnly: false`
- `src="http://external.com/`

**Fix:** Replace all `http://` with `https://`; use `https.createServer()` with SSL certs; configure HSTS; use a reverse proxy for HTTPS termination.

---

## 16. missing-security-headers (medium)
Detects missing HTTP security headers.

**Detects:** Responses served without standard browser-enforced security headers (checked in severity order):
- `Content-Security-Policy` (critical) — XSS mitigation
- `Strict-Transport-Security` (critical) — enforces HTTPS
- `X-Frame-Options` (high) — prevents clickjacking
- `Referrer-Policy` (high)
- `X-Content-Type-Options` (medium) — prevents MIME sniffing
- `Permissions-Policy` (medium)

**Fix:** Use `helmet()` middleware in Express; `Flask-Talisman` in Flask; `SECURE_*` settings in Django; `.headers().contentSecurityPolicy(...)` in Spring Security.

---

## 17. insecure-configuration (medium)
Detects insecure configuration settings that should never reach production.

**Detects:** Debug/verbose flags, dev environment markers, and disabled security controls in config.
- `debug = true` / `verbose = true`
- `environment = development` / `NODE_ENV = development`
- `ssl = false` / `https = false` / `secure = false`
- `auth = disabled` / `auth = none`
- `csrf = false` / `xss_protection = false` / `hsts = false`

**Fix:** Disable debug/verbose in prod; enable SSL/HTTPS; use environment-specific config files; never ship dev settings to production.

---

## 18. insecure-error-handling (medium)
Detects information disclosure through error messages and stack traces.

**Detects:** Stack traces, SQL errors, or raw exception messages sent to clients.
- `console.log(error.stack)` / `res.status(500).send(err.stack)`
- `console.log(sql_error)`
- `print_r(error)` / `var_dump(exception)`
- `res.status(500).json({ error: err.message })`

**Fix:** Never expose stack traces or raw error messages in production responses; use generic error messages for clients; log full details server-side only; use centralized error-handler middleware.

---

## 19. insecure-logging (medium)
Detects sensitive data exposure through application logs.

**Detects:** Passwords, payment data, API keys, session tokens, or full request bodies written to logs.
- `console.log("User password: " + user.password)`
- `logger.info("Credit card: " + payment.cardNumber)`
- `console.log(req.body)` — logs full request body
- `console.log(req.headers)` / `console.log(req.session)`
- `logging.info(api_key)`

**Fix:** Never log passwords, API keys, tokens, or credit cards; use `[REDACTED]` placeholders; implement field-level masking; use structured logging with sensitive-field filtering.

---

## 20. insecure-dependencies (medium)
Detects potentially insecure or backdoored third-party dependencies.

**Detects:** Known-vulnerable package versions and suspicious install scripts.
- `lodash` <4.17.21 — prototype pollution CVE-2021-23337
- `handlebars` <4.7.7 — template injection CVE-2021-23369
- `minimist` <1.2.6 — prototype pollution CVE-2021-44906
- `event-stream` — backdoored (malicious code injection)
- `pyyaml` <5.4 — arbitrary code execution CVE-2020-1747
- `"*"` or `"latest"` version ranges; `postinstall` with `curl`/`wget`

**Fix:** Run `npm audit fix`, `pip audit`, `composer audit`; pin to specific versions; review all `scripts.postinstall` entries; avoid deprecated packages (`moment`, `request`).

---

## 21. dockerfile-security (high)
Detects common Dockerfile security vulnerabilities.

**Detects:** Unpinned base images, root user, secrets in ENV, and unsafe directives.
- `FROM image:latest` — unpinned base image
- `USER root`
- `ENV PASSWORD=` / `ENV API_KEY=`
- `RUN curl https://` without checksum verification
- `ADD` directive (use `COPY` instead)
- Missing: `USER`, `WORKDIR`, `HEALTHCHECK`, `.dockerignore`

**Fix:** Pin image digests: `FROM node:18.17.0-alpine@sha256:...`; add `RUN adduser appuser && USER appuser`; use `COPY` not `ADD`; add `HEALTHCHECK`; create `.dockerignore`.

---

## 22. container-registry-security (medium)
Detects container registry security misconfigurations.

**Detects:** Unverified image tags, insecure registry endpoints, and missing pull secrets.
- `image: nginx:latest` — no pinned digest
- `image: app:v1` without `@sha256:` digest
- `insecure-registry` / `http:` registry URL
- `imagePullPolicy: Always` without digest pinning
- Missing: `imagePullSecrets`, vulnerability scanning, image signing

**Fix:** Use `image@sha256:abc123...`; add `imagePullSecrets`; run Trivy in CI/CD; sign images with cosign; use HTTPS-only registry endpoints.

---

## 23. kubernetes-security (high)
Detects Kubernetes security misconfigurations.

**Detects:** Privileged containers, host namespace sharing, root UIDs, and missing security contexts.
- `privileged: true`
- `hostNetwork: true` / `hostPID: true` / `hostIPC: true`
- `runAsUser: 0` / `runAsNonRoot: false`
- `readOnlyRootFilesystem: false`
- `allowPrivilegeEscalation: true`
- `add: ["SYS_ADMIN"]` / `add: ["NET_ADMIN"]`
- `automountServiceAccountToken: true`

**Fix:** Add `securityContext: { runAsNonRoot: true, runAsUser: 1000, readOnlyRootFilesystem: true, allowPrivilegeEscalation: false, capabilities: { drop: ["ALL"] } }`; set resource limits; implement NetworkPolicy and RBAC.

---

## 24. prompt-injection-detection (critical)
Detects potential prompt injection vulnerabilities in AI systems.

**Detects:** User input concatenated directly into LLM prompts, enabling instruction override.
- `prompt = systemPrompt + userInput`
- `` prompt = `...${userInput}...` ``
- `f"...{request.form['q']}..."` (Python f-string into prompt)
- `prompt = "...ignore previous instructions..."`
- `prompt = "you are admin..."` — role confusion
- `prompt = "...reveal system prompt..."`

**Fix:** Never interpolate user input directly into prompts; use structured API calls with separate `system` and `user` message roles; implement input validation and allowlists; apply content filtering.

---

## 25. ai-agent-access-control (critical)
Detects insecure AI agent access controls and privilege escalation.

**Detects:** Agents configured with admin/root roles, unlimited permissions, or disabled authentication.
- `agent = 'admin'` / `agent = 'root'`
- `permissions = 'all'` / `permissions = 'unlimited'`
- `auth = false` / `auth = disabled`
- `mcp ...unrestricted` / `mcp ...open`
- `agent ...bypass ...auth` / `agent ...system access`

**Fix:** Apply least privilege; use RBAC for AI agents; grant elevated access only temporarily; sandbox all AI agent execution; require authentication for every MCP server interaction.

---

## 26. ai-data-leakage-prevention (high)
Detects potential data leakage in AI systems and training data exposure.

**Detects:** Configurations or code that exposes training data, unfiltered model output, or unencrypted model artifacts.
- `training_data = ...expose` / `training_data = ...public`
- `sensitive = ...training/dataset`
- `ai = ...unfiltered ...output`
- `bypass = ...classification/label`
- `model weights = ...unencrypted` / `...plaintext`
- `log(...sensitive/confidential)`

**Fix:** Implement DLP policies; encrypt model artifacts at rest; filter outputs for sensitive data before returning; apply sensitivity labels; use data anonymization; monitor AI output pipelines.

---

## 27. ai-generated-code-validation (high)
Detects security issues in AI-generated code that has not been reviewed.

**Detects:** Code marked as AI-generated that is unvalidated, or AI-generated patterns that are inherently dangerous.
- `generated_by = unvalidated` / `ai_generated = unreviewed` / `copilot = unreviewed`
- `ai = vulnerable` / `ai = insecure` / `ai = unsafe`
- `eval("...${variable}...")` / `exec("...${userInput}...")`
- `query = "...${variable}..."` — SQL via template literal
- `readFile("...${req.query.` / `fetch("...${url}..."`

**Fix:** Require mandatory security review for all AI-generated code before merge; run SAST tools automatically; never deploy AI-generated code without human validation; add secure-coding checks to CI/CD pipeline.

---

## 28. mcp-server-security (high)
Detects insecure Model Context Protocol (MCP) server configurations.

**Detects:** MCP servers with no auth, no TLS, weak credentials, path traversal, or no rate limiting.
- `auth = none` / `auth = false` / `auth = disabled`
- `ssl = false` / `ssl = disabled`
- `token = 'test'` / `token = 'demo'` / `token = 'password'`
- `context = '../../../etc/passwd'` — path traversal
- `allow = all` / `allow = unrestricted`
- `cors = *` / `bind = 0.0.0.0` / `timeout = 0`

**Fix:** Enable JWT or API-key authentication; enable SSL/TLS; load credentials from env vars; restrict CORS to known origins; implement rate limiting; avoid binding to `0.0.0.0` in production.
