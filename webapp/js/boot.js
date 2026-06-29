// boot.js
//
// ThinkFree front-end bootstrap / asset loader (dual-mode).
//
// Why this exists:
//   Every logic module captures its data into a const at script-eval time
//   (e.g. app.js `const D = window.TF_DATA || {}`, scores.js `const D = window.TF_DATA`).
//   So the window.*_DATA globals MUST already exist BEFORE those logic scripts
//   evaluate. In the old static site the <script src="js/*_data.js"> tags set
//   them inline. Under the FastAPI server those data files are 404-blocked
//   (server/main.py) and the datasets are fetched from /api/data/* only AFTER
//   login. You cannot fetch between two fixed `defer` tags, so the whole boot
//   sequence is orchestrated here instead of via static <script> tags.
//
// Modes (auto-detected):
//   "server" - served by the FastAPI backend (/api/healthz responds ok). Data
//              comes from /api/data/{bundle,live,state}; auth from /api/auth/*.
//   "static" - opened as a plain file (file://) or a dumb static host. Data
//              comes from injected js/*_data.js tags; auth from localStorage.
//
// Public API (window.TFBoot), consumed by auth.js and app.js:
//   .ready              Promise<"server"|"static">  resolves once mode is known
//   .mode               "server"|"static"|null      set after .ready resolves
//   .ensureAppLoaded()  Promise<void>   idempotent: populate data globals + inject
//                                       logic scripts, resolves when window.TF is ready
//   .api(path, opts)    Promise<{ok,status,data}>   JSON fetch w/ same-origin cookies
"use strict";
(function () {
  // Data files that define window.* globals. In static mode these are injected
  // (in this order) to set the globals; in server mode they are 404-blocked and
  // the same globals arrive via /api/data/bundle + /api/data/live instead.
  // (legiscan_data.js + openstates_data.js are lazy-loaded by app.js's
  //  ensureStateData() on first State view, not here.)
  const DATA_SCRIPTS = [
    "js/data.js", "js/influence_data.js", "js/relationships_data.js", "js/nonprofit_data.js",
    "js/fec_data.js", "js/sec_data.js", "js/secbulk_data.js", "js/usaspending_data.js",
    "js/states_data.js", "js/sp500_data.js", "js/quant_data.js", "js/member_bills.js",
    "js/presidential_data.js", "js/money_trail_data.js",
    "js/prices_data.js", "js/news_intel.js",
  ];

  // Logic/asset scripts that READ the globals (at eval time and later). Loaded in
  // BOTH modes, always AFTER the data globals exist, in this exact order so the
  // relative eval order from the old index.html is preserved. usmap_paths.js is
  // static map geometry (not sensitive, not blocked) so it loads normally either way.
  const LOGIC_SCRIPTS = [
    "js/scores.js", "js/genimpact.js", "js/app.js", "js/influenceweb.js",
    "js/usmap_paths.js", "js/congress.js", "js/glossary.js", "js/scoreinfo.js",
    "js/predictions.js", "js/presidential.js",
  ];

  // injectScript -- append a <script> and resolve when it loads (reject on error).
  function injectScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = function () { resolve(src); };
      s.onerror = function () { reject(new Error("failed to load " + src)); };
      document.body.appendChild(s);
    });
  }

  // loadInOrder -- inject scripts one at a time so eval order is deterministic.
  async function loadInOrder(list) {
    for (var i = 0; i < list.length; i++) await injectScript(list[i]);
  }

  // api -- thin JSON fetch helper. Always sends the session cookie (same-origin).
  // Returns {ok, status, data}; only rejects on a network failure, not on HTTP errors,
  // so callers can branch on status (401/403/409/429) without try/catch noise.
  // readCookie -- read a non-httpOnly cookie value by name (used for the CSRF token).
  function readCookie(name) {
    var m = document.cookie.match("(?:^|; )" + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, "\\$1") + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : null;
  }

  async function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", credentials: "same-origin", headers: {} };
    if (opts.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body);
    }
    // CSRF double-submit: echo the tf_csrf cookie in a header on state-changing
    // requests. The server requires this on protected mutations; safe (GET) and
    // bootstrap (login/signup) requests do not need it.
    if (init.method !== "GET" && init.method !== "HEAD") {
      var csrf = readCookie("tf_csrf");
      if (csrf) init.headers["X-CSRF-Token"] = csrf;
    }
    var res = await fetch(path, init);
    var data = null;
    try { data = await res.json(); } catch (e) { /* empty / non-JSON body */ }
    return { ok: res.ok, status: res.status, data: data };
  }

  // detectMode -- server if /api/healthz answers ok; otherwise static.
  // file:// throws (network error) -> static; a dumb static host 404s -> static;
  // the FastAPI backend returns 200 -> server.
  async function detectMode() {
    try {
      var res = await fetch("/api/healthz", { credentials: "same-origin" });
      return res.ok ? "server" : "static";
    } catch (e) {
      return "static";
    }
  }

  var ready = detectMode().then(function (m) {
    TFBoot.mode = m;
    // The static-mode localStorage/cyrb53 gate is a DEV fallback only and is not
    // real security (any client-side gate is bypassable). Real protection is the
    // server path; in production the app is always served by the FastAPI backend,
    // where the datasets are never in the static files to begin with.
    if (m === "static") {
      try { console.warn("[ThinkFree] Static mode: the login gate here is a dev fallback, NOT real security. Run the FastAPI backend for real auth + gated data."); } catch (e) {}
    }
    return m;
  });

  var appLoadedPromise = null;

  // populateData -- ensure the window.*_DATA globals exist before logic scripts run.
  // The server bundles each dataset under its window.NAME, so Object.assign(window, .)
  // restores exactly the globals the data <script> tags used to define.
  async function populateData(mode) {
    if (mode === "server") {
      var bundle = await api("/api/data/bundle");
      if (bundle.ok && bundle.data) Object.assign(window, bundle.data);
      // Prices + news for the initial render. Honors server-side market-hours pause.
      var live = await api("/api/data/live");
      if (live.ok && live.data && !live.data.paused) Object.assign(window, live.data);
    } else {
      await loadInOrder(DATA_SCRIPTS); // each tag sets its window.* global
    }
  }

  // ensureAppLoaded -- populate data, then inject the logic scripts, then resolve.
  // Idempotent: the first call does the work; later calls await the same promise.
  // auth.js awaits this right before calling window.TF.init() on unlock.
  function ensureAppLoaded() {
    if (appLoadedPromise) return appLoadedPromise;
    appLoadedPromise = (async function () {
      var mode = await ready;
      await populateData(mode);
      await loadInOrder(LOGIC_SCRIPTS);
      // app.js assigns window.TF.init synchronously on eval; guard just in case.
      if (!(window.TF && window.TF.init)) throw new Error("ThinkFree app failed to initialize");
    })();
    return appLoadedPromise;
  }

  var TFBoot = {
    ready: ready,
    mode: null,
    ensureAppLoaded: ensureAppLoaded,
    api: api,
    DATA_SCRIPTS: DATA_SCRIPTS,
    LOGIC_SCRIPTS: LOGIC_SCRIPTS,
  };
  window.TFBoot = TFBoot;
})();
