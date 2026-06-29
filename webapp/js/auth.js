/*
 * auth.js -- ThinkFree Finance client-side beta gate and tier model
 *
 * What it does:
 *   Manages the login / beta-key / signup / behavioral-quiz / accessibility
 *   onboarding flow. Accounts are persisted in localStorage. On success the
 *   app is revealed with a slide-up unlock animation. A MutationObserver +
 *   interval re-asserts the gate if it is removed via devtools. After unlock,
 *   a per-tier interval fetches fresh prices and news data, pausing when the
 *   US equity market is closed (except for premium fast tiers that pay for
 *   after-hours coverage). Logout shows a brief goodbye screen then returns
 *   to the login view without reloading the page.
 *
 * How it fits:
 *   Loaded with <script defer> on index.html before app.js. Exposes
 *   window.Auth for other modules (tier, profile, a11y, setProfile, logout).
 *   Calls window.TF.init() once on first unlock and window.TF.onRefresh()
 *   on every subsequent data refresh.
 *
 * IMPORTANT: This is a soft, client-side gate for closed beta only.
 *   It is NOT real security. Real auth, payments, and enforced tier gating
 *   require a backend. It is good enough to let invited testers in and create
 *   accounts without exposing the app to the public.
 */
"use strict";
(function () {
  // Hash of the beta invite key. The plaintext key is configured by the operator
  // via TF_BETA_KEY (server) and is intentionally not stored in source.
  const BETA_HASH = "5sw0ilypx6";

  // cyrb53 -- fast non-cryptographic hash used to verify the beta key and
  // store passwords without keeping them in plaintext in localStorage.
  // Good enough for a soft gate; not suitable for real auth.
  function cyrb53(str, seed) {
    seed = seed || 0; let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
    for (let i = 0, ch; i < str.length; i++) { ch = str.charCodeAt(i); h1 = Math.imul(h1 ^ ch, 2654435761); h2 = Math.imul(h2 ^ ch, 1597334677); }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507); h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507); h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }

  // Tier definitions. refreshMin controls how often the live-data interval fires.
  // The SERVER is the single source of truth (config.TIERS); these values mirror
  // it for static/offline mode and are overwritten at boot by GET /api/data/tiers
  // (see loadTierCatalog) so client and server can never drift. The server also
  // ENFORCES the cadence on /api/data/live, so this client copy is convenience
  // only , it cannot be edited to refresh faster than the tier allows.
  const TIERS = {
    free:   { id: "free",   name: "Free",         refreshMin: 1440, price: "$0",     blurb: "Daily market briefing" },
    hourly: { id: "hourly", name: "Pro · Hourly", refreshMin: 60,   price: "$9/mo",  blurb: "Fresh prices every hour" },
    half:   { id: "half",   name: "Pro · 30-min", refreshMin: 30,   price: "$19/mo", blurb: "Refreshes every 30 minutes, including after hours" },
    live:   { id: "live",   name: "Pro · 5-min",  refreshMin: 5,    price: "$39/mo", blurb: "Fastest feed, every 5 minutes, including after hours" },
    beta:   { id: "beta",   name: "Beta Access",  refreshMin: 5,    price: "Free (beta)", blurb: "Full 5-minute access during the closed beta" },
  };

  // Ordered list of purchasable tiers for the upgrade UI (excludes internal/beta).
  // Replaced by the server catalogue when available.
  let TIER_CATALOG = ["free", "hourly", "half", "live"].map((k) => TIERS[k]);

  // Pull the canonical catalogue from the server so prices/cadence stay in sync
  // with config.TIERS. Best-effort: on failure we keep the mirror above.
  async function loadTierCatalog() {
    if (!SERVER()) return;
    try {
      const res = await window.TFBoot.api("/api/data/tiers");
      if (res && res.ok && res.data && Array.isArray(res.data.tiers)) {
        TIER_CATALOG = res.data.tiers.map((t) => ({
          id: t.id, name: t.name, refreshMin: t.refresh_min,
          price: t.price_display, blurb: t.blurb,
        }));
        TIER_CATALOG.forEach((t) => { TIERS[t.id] = Object.assign(TIERS[t.id] || {}, t); });
      }
    } catch (e) { /* keep the built-in mirror */ }
  }

  // LS wraps localStorage so the rest of the module never touches it directly.
  // The accounts object is keyed by email; each value holds name, hashed pass,
  // tier, a11y flag, profile, and created date.
  const LS = {
    get accounts() { try { return JSON.parse(localStorage.getItem("tf_accounts") || "{}"); } catch (e) { return {}; } },
    set accounts(v) { localStorage.setItem("tf_accounts", JSON.stringify(v)); },
    get session() { return localStorage.getItem("tf_session") || ""; },
    set session(v) { v ? localStorage.setItem("tf_session", v) : localStorage.removeItem("tf_session"); },
  };

  // E -- minimal HTML escaper used whenever user-supplied text is written into innerHTML.
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Accept a username (e.g. "admin") OR an email as the login id.
  const validId = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) || /^[a-z0-9_.-]{3,}$/i.test(s);
  // Strict email check used on the signup form (the server also validates).
  // Requires a real-looking TLD (2+ letters) so "a@b" or "a@b.1" are rejected,
  // while still accepting any custom domain. Deeper "does this domain actually
  // exist" checking is done by emailDomainReal() below.
  const validEmail = (s) => /^[^\s@]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/i.test(s);

  // emailDomainReal -- confirms the email's domain actually exists and can take
  // mail, so random nonsense like "sfdjk@fdsjkfhsdkhj.com" is rejected while any
  // legitimate custom domain still passes. Uses public DNS-over-HTTPS (Google),
  // checking for an MX record and falling back to an A record (some domains
  // receive mail without an explicit MX). Fails OPEN: if DNS is unreachable we
  // allow the signup rather than lock out a real user over a flaky network.
  async function emailDomainReal(email) {
    const domain = (email.split("@")[1] || "").toLowerCase();
    if (!domain || domain.indexOf(".") < 0) return false;
    const ask = (type) =>
      fetch("https://dns.google/resolve?name=" + encodeURIComponent(domain) + "&type=" + type, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);
    try {
      const mx = await ask("MX");
      if (mx == null) return true;           // DNS unreachable -> fail open
      if (mx.Status === 3) return false;      // NXDOMAIN -> domain doesn't exist
      if (mx.Answer && mx.Answer.length) return true;  // has a mail server
      const a = await ask("A");               // no MX: accept if the domain resolves at all
      if (a == null) return true;
      return !!(a.Answer && a.Answer.length);
    } catch (e) {
      return true;                            // any failure -> fail open
    }
  }

  // SERVER -- true when boot.js detected the FastAPI backend. Every auth/data
  // branch keys off this; when false we keep the original localStorage gate so
  // the app still runs as a plain static file. boot.js resolves the mode before
  // boot() runs, so window.TFBoot.mode is set by the time these helpers are used.
  const SERVER = () => !!(window.TFBoot && window.TFBoot.mode === "server");

  // betaKeyEntered -- carries the invite key from the "beta" view to the signup
  // POST. In server mode the server validates it; the local cyrb53 check is only
  // a soft pre-check for static mode.
  let betaKeyEntered = "";

  // adoptServerUser -- the server stores only the five raw profile answers; the
  // UI expects the enriched shape (risk_tolerance, profile_id) that computeProfile
  // produces. Re-derive it client-side so server and static modes look identical
  // to app.js (which reads p.risk_tolerance / p.goal). Leaves a null profile null.
  function adoptServerUser(u) {
    if (u && u.profile && u.profile.experience) {
      try { u.profile = computeProfile(u.profile); } catch (e) { /* keep raw */ }
    }
    return u;
  }

  // computeProfile -- behavioral profile quiz scoring, ported from
  // phase1_user_personalization.py so the web and pipeline share the same logic.
  // Answers produce a risk tolerance ("low" / "moderate" / "high") and a
  // two-part profile_id used for personalized briefing tailoring.
  function computeProfile(a) {
    const age = parseInt(a.age, 10) || 30;
    let pts = 0;
    if (age < 30) pts += 2; else if (age < 50) pts += 1;
    if (a.experience === "advanced") pts += 2; else if (a.experience === "intermediate") pts += 1;
    if (a.goal === "growth") pts += 2; else if (a.goal === "income") pts += 1;
    if (a.emotional === "buy more") pts += 2; else if (a.emotional === "hold") pts += 1;
    const risk = pts >= 7 ? "high" : pts >= 4 ? "moderate" : "low";
    const ageGroup = age < 25 ? "A1_<25" : age <= 34 ? "A2_25-34" : age <= 50 ? "A3_35-50" : "A4_50+";
    const riskGroup = risk === "low" ? "R1_Cons" : risk === "moderate" ? "R2_Mod" : "R3_High";
    return { age, experience: a.experience, goal: a.goal, timeline: a.timeline, emotional: a.emotional,
             risk_tolerance: risk, risk_score: pts, profile_id: ageGroup + "_" + riskGroup };
  }

  let currentUser = null, refreshTimer = null, unlocked = false;

  // Lock the body immediately (before DOMContentLoaded) so the app content is
  // hidden from the moment the parser sees this tag. The gate overlay sits on
  // top; if JS is too slow, there is nothing visible behind it anyway.
  if (document.body) document.body.classList.add("tf-locked");

  // accountFor -- reads the current session email from LS and returns the
  // matching account object (with email merged in), or null if no session.
  function accountFor() {
    const a = LS.accounts[LS.session];
    return a ? { email: LS.session, ...a } : null;
  }

  // gate UI helpers
  let gate;

  // killSplash -- removes the static splash screen (server-rendered placeholder)
  // so the auth gate or app can take its place cleanly.
  function killSplash() { const s = document.getElementById("tf-splash"); if (s) s.remove(); }

  // showGate -- create the gate overlay if it does not exist, then render the
  // requested view. Always called before the user has authenticated.
  function showGate(view) {
    killSplash();
    if (!gate) { gate = document.createElement("div"); gate.className = "auth-gate"; document.body.appendChild(gate); }
    gate.style.display = "flex";
    render(view || "login", {});
  }

  function hideGate() { if (gate) gate.style.display = "none"; }

  // shell -- wraps each view's inner HTML in the branded card frame (logo,
  // disclaimer footer). Keeps the individual view templates lean.
  function shell(inner) {
    return `<div class="auth-card">
      <div class="auth-brand"><div class="auth-logo">TF</div><div><div class="auth-name">Think<span>Free</span></div><div class="auth-sub">Finance</div></div></div>
      ${inner}
      <div class="auth-foot">Closed beta. By continuing you agree this is an analytical tool, not financial advice.</div>
    </div>`;
  }

  // render -- builds the HTML for a named view and writes it into the gate.
  // Views: "login", "beta" (key entry), "signup", "quiz" (profile), "a11y".
  function render(view, ctx) {
    let body;
    if (view === "login") {
      body = `<h2 class="auth-h">Welcome back</h2><p class="auth-p">Log in to your ThinkFree account.</p>
        <div class="auth-err" id="auth-err"></div>
        <input class="auth-in" id="au-email" type="email" placeholder="Email" autocomplete="username">
        <input class="auth-in" id="au-pass" type="password" placeholder="Password" autocomplete="current-password">
        <button class="auth-btn" data-act="login">Log in</button>
        <div class="auth-alt">Have a beta invite key? <a data-act="to-beta">Enter it &rsaquo;</a></div>`;
    } else if (view === "beta") {
      body = `<h2 class="auth-h">Beta access</h2><p class="auth-p">ThinkFree is in closed beta. Enter your invite key to create an account.</p>
        <div class="auth-err" id="auth-err"></div>
        <input class="auth-in" id="au-key" type="text" placeholder="Beta invite key" autocomplete="off">
        <button class="auth-btn" data-act="verify">Verify key</button>
        <div class="auth-alt">Already have an account? <a data-act="to-login">Log in &rsaquo;</a></div>`;
    } else if (view === "signup") {
      body = `<h2 class="auth-h">Create your account</h2><p class="auth-p">Beta key accepted. You're in.</p>
        <div class="auth-err" id="auth-err"></div>
        <input class="auth-in" id="au-name" type="text" placeholder="Name" autocomplete="name">
        <input class="auth-in" id="au-email" type="email" placeholder="Email" autocomplete="username">
        <input class="auth-in" id="au-pass" type="password" placeholder="Create a password" autocomplete="new-password">
        <label class="auth-consent"><input type="checkbox" id="au-consent">
          <span>I confirm I am 18 or older, or I am at least 13 and have explicit permission from a parent or guardian to use ThinkFree.</span></label>
        <button class="auth-btn" data-act="signup">Create account &rsaquo;</button>
        <div class="auth-note">Beta accounts get <b>Beta Access</b> (15-minute refresh) free during testing.</div>`;
    } else if (view === "quiz") {
      // Pre-fill from existing profile in case the user revisits Settings.
      const p = (currentUser && currentUser.profile) || {};
      const sel = (id, label, opts, cur) => `<label class="auth-qlabel">${label}</label><select class="auth-in" id="${id}">${opts.map((o) => `<option value="${o[0]}"${cur === o[0] ? " selected" : ""}>${o[1]}</option>`).join("")}</select>`;
      body = `<h2 class="auth-h">Quick profile</h2><p class="auth-p">5 questions so we can tailor your briefing to you. Change these anytime in Settings.</p>
        <label class="auth-qlabel">Your age</label><input class="auth-in" id="q-age" type="number" min="13" max="100" value="${p.age || ""}" placeholder="e.g. 28">
        ${sel("q-exp", "Investing experience", [["beginner", "Beginner"], ["intermediate", "Intermediate"], ["advanced", "Advanced"]], p.experience)}
        ${sel("q-goal", "Primary goal", [["growth", "Growth"], ["income", "Income"], ["stability", "Stability"]], p.goal)}
        ${sel("q-time", "Time horizon", [["short-term", "Short-term"], ["mid-term", "Mid-term"], ["long-term", "Long-term"]], p.timeline)}
        ${sel("q-emo", "When markets drop, you usually", [["sell", "Sell"], ["hold", "Hold"], ["buy more", "Buy more"]], p.emotional)}
        <button class="auth-btn" data-act="quiz-submit">Continue &rsaquo;</button>`;
    } else if (view === "a11y") {
      body = `<h2 class="auth-h">Accessibility</h2>
        <p class="auth-p">Would you like <b>Accessibility mode</b>? It turns on larger text, higher contrast, stronger focus outlines, and reduced motion for an easier-to-read experience. You can change this anytime in Settings.</p>
        <button class="auth-btn" data-act="a11y-on">Turn on Accessibility mode</button>
        <button class="auth-btn auth-btn-ghost" data-act="a11y-off">Use standard view</button>`;
    }
    gate.innerHTML = shell(body);
  }

  // err -- display or clear the inline error banner inside the current view.
  function err(msg) { const e = document.getElementById("auth-err"); if (e) { e.textContent = msg; e.style.display = msg ? "block" : "none"; } }

  // val -- safely read an input's value by id; returns "" if the element is absent.
  const val = (id) => (document.getElementById(id) || {}).value || "";

  // enter -- called on successful login. Persists the session and unlocks with animation.
  // In server mode the session lives in the httpOnly cookie and currentUser is
  // already set from the API response, so we never touch localStorage.
  function enter(email) {
    if (!SERVER()) { LS.session = email; currentUser = accountFor(); }
    unlock(true);
  }

  // applyA11y -- toggles the a11y-mode class on <body>, which CSS uses to
  // switch to larger text, higher contrast, stronger outlines, and reduced motion.
  function applyA11y(on) { document.body.classList.toggle("a11y-mode", !!on); }

  // unlock -- reveals the app. `animated` plays the slide-up unlock animation
  // (new logins); otherwise it is instant (returning session on page load).
  // init() is called here so nothing in app.js renders before authentication.
  //
  // index.html no longer ships the data/logic <script> tags, so we must first
  // ask boot.js to load them (fetch /api/data/* in server mode, or inject the
  // js/*_data.js tags in static mode) BEFORE window.TF.init exists. While that
  // runs, the "Unlocking your dashboard" card is shown for animated logins.
  async function unlock(animated) {
    unlocked = true;                                   // stops the tamper-guard from re-locking
    killSplash();
    // Loading feedback. On a fresh (animated) login the gate shows the welcome
    // card while the data loads. For a returning session there is no gate, so
    // without this the user stared at a blank screen for the whole data load
    // (which can be many seconds on a cold server). Show a themed spinner so it
    // never looks frozen.
    let loadingOv = null;
    if (animated && gate) {
      gate.innerHTML = `<div class="auth-unlocked"><div class="auth-check">&#10003;</div>
        <div class="auth-welcome">Welcome${currentUser && currentUser.name ? ", " + E(currentUser.name) : ""}</div>
        <div class="auth-welcome-sub">Unlocking your dashboard</div></div>`;
    } else {
      loadingOv = document.createElement("div");
      loadingOv.className = "tf-loading";
      loadingOv.setAttribute("role", "status");
      loadingOv.setAttribute("aria-live", "polite");
      loadingOv.innerHTML = `<div class="tf-loading-box"><div class="tf-spinner" aria-hidden="true"></div>`
        + `<div class="tf-loading-msg">Loading your intelligence briefing</div></div>`;
      document.body.appendChild(loadingOv);
    }
    try {
      if (window.TFBoot && window.TFBoot.ensureAppLoaded) await window.TFBoot.ensureAppLoaded();
    } catch (e) {
      if (loadingOv) loadingOv.remove();
      err && err("Could not load your dashboard. Please refresh and try again.");
      return;
    }
    if (loadingOv) loadingOv.remove();
    applyA11y(currentUser && currentUser.a11y);        // honor the user's accessibility preference
    if (window.TF && window.TF.init) window.TF.init(); // build/render the app (guarded; no-op after first login)
    if (window.TF && window.TF.onRefresh) window.TF.onRefresh(); // refresh greeting/views for this account
    applyUser();
    startRefresh();
    const dropGate = () => { if (gate) { gate.remove(); gate = null; } };
    if (animated && gate) {
      // The welcome card was already shown before the data load above; let it
      // settle briefly, then slide the gate up to reveal the rendered app.
      setTimeout(() => {
        document.body.classList.remove("tf-locked");   // reveal the app behind
        gate.classList.add("unlocking");               // slide the gate up off-screen
        gate.addEventListener("animationend", dropGate, { once: true });
        setTimeout(dropGate, 1000);
      }, 700);
    } else {
      document.body.classList.remove("tf-locked");
      dropGate();
    }
  }

  // bind -- single delegated click listener on document handles all button and
  // link actions inside the gate (data-act attributes), keeping the render
  // functions free of event wiring.
  function bind() {
    document.addEventListener("click", async (e) => {
      const t = e.target.closest("[data-act]"); if (!t || !gate || gate.style.display === "none") return;
      const a = t.dataset.act;
      if (a === "to-beta") return render("beta");
      if (a === "to-login") return render("login");
      if (a === "verify") {
        const key = val("au-key").trim();
        // Server mode: no client-side key check (no plaintext key in the bundle);
        // carry the key to the signup POST, where the server validates it in
        // constant time. Static mode: keep the soft cyrb53 pre-check.
        if (SERVER()) { betaKeyEntered = key; return render("signup"); }
        if (cyrb53(key) === BETA_HASH) return render("signup");
        return err("That beta key isn't valid. Check it and try again.");
      }
      if (a === "signup") {
        const name = val("au-name").trim(), email = val("au-email").trim().toLowerCase(), pass = val("au-pass");
        const consent = !!(document.getElementById("au-consent") || {}).checked;
        if (!name) return err("Enter your name.");
        if (!validEmail(email)) return err("Enter a valid email.");
        if (!consent) return err("Please confirm you meet the age requirement to continue.");
        // Confirm the email's domain actually exists (rejects nonsense domains
        // while still allowing any real custom domain). Disable the button so an
        // impatient double-click can't fire two signups during the DNS lookup.
        if (t.disabled) return;
        t.disabled = true; err("");
        const domainOk = await emailDomainReal(email);
        t.disabled = false;
        if (!domainOk) return err("That email domain doesn't seem to exist. Check the address and try again.");
        if (SERVER()) {
          if (pass.length < 8) return err("Password must be at least 8 characters.");
          const res = await window.TFBoot.api("/api/auth/signup", { method: "POST", body: { beta_key: betaKeyEntered, name, email, password: pass, consent: true } });
          if (!res.ok) {
            const d = (res.data && res.data.detail) || "Could not create account.";
            if (res.status === 403) { render("beta"); return err(d); }   // bad key -> back to key entry
            return err(d);
          }
          currentUser = adoptServerUser(res.data.user);
          return render("quiz");   // new users take the profile quiz first
        }
        if (pass.length < 6) return err("Password must be at least 6 characters.");
        const accs = LS.accounts;
        if (accs[email]) return err("An account with that email already exists. Log in instead.");
        accs[email] = { name, pass: cyrb53(pass), tier: "beta", a11y: false, created: new Date().toISOString().slice(0, 10) };
        LS.accounts = accs;
        LS.session = email; currentUser = accountFor();
        return render("quiz");   // new users take the profile quiz first
      }
      if (a === "quiz-submit") {
        const answers = { age: val("q-age"), experience: val("q-exp"), goal: val("q-goal"), timeline: val("q-time"), emotional: val("q-emo") };
        // Hard floor at 13: ThinkFree is not available to children under 13.
        // (13-17 already attested to parental permission on the signup consent.)
        const ageNum = parseInt(answers.age, 10);
        if (!ageNum || ageNum < 13) return err("You must be at least 13 years old to use ThinkFree.");
        if (ageNum > 120) return err("Please enter a valid age.");
        if (SERVER()) {
          // Server persists the raw answers; we enrich for the session via adoptServerUser.
          const res = await window.TFBoot.api("/api/auth/profile", { method: "POST", body: answers });
          if (res.ok && res.data && res.data.user) currentUser = adoptServerUser(res.data.user);
          return render("a11y");
        }
        const prof = computeProfile(answers);
        const accs = LS.accounts; if (accs[LS.session]) { accs[LS.session].profile = prof; LS.accounts = accs; }
        currentUser = accountFor();
        return render("a11y");   // then the accessibility preference, then in
      }
      if (a === "a11y-on" || a === "a11y-off") {
        const on = a === "a11y-on";
        if (SERVER()) {
          await window.TFBoot.api("/api/auth/a11y?on=" + on, { method: "POST" });
          if (currentUser) currentUser.a11y = on;
          applyA11y(on);
          return unlock(true);
        }
        const accs = LS.accounts; if (accs[LS.session]) { accs[LS.session].a11y = on; LS.accounts = accs; }
        currentUser = accountFor(); applyA11y(on);
        return unlock(true);
      }
      if (a === "login") {
        const email = val("au-email").trim().toLowerCase(), pass = val("au-pass");
        if (SERVER()) {
          const res = await window.TFBoot.api("/api/auth/login", { method: "POST", body: { email, password: pass } });
          if (!res.ok) return err((res.data && res.data.detail) || "Email or password is incorrect.");
          currentUser = adoptServerUser(res.data.user);
          return enter(email);
        }
        const acc = LS.accounts[email];
        if (!acc || acc.pass !== cyrb53(pass)) return err("Email or password is incorrect.");
        return enter(email);
      }
    });
  }

  // applyUser -- writes the current user's name, plan label, and avatar initial
  // into the sidebar chrome elements (if they exist in the DOM).
  function applyUser() {
    const u = currentUser; if (!u) return;
    const tier = TIERS[u.tier] || TIERS.free;
    const nameEl = document.getElementById("userName"); if (nameEl) nameEl.textContent = u.name || u.email;
    const planEl = document.getElementById("userPlan"); if (planEl) planEl.textContent = tier.name;
    const av = document.getElementById("userAvatar"); if (av) av.textContent = (u.name || u.email).slice(0, 1).toUpperCase();
  }

  // startRefresh -- sets (or resets) the data-refresh interval based on the
  // current user's tier. Clears any previous interval first so tier changes
  // take effect immediately without doubling up.
  function startRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    const tier = TIERS[(currentUser && currentUser.tier) || "free"] || TIERS.free;
    const ms = tier.refreshMin * 60 * 1000;
    refreshTimer = setInterval(() => refreshLiveData(tier), ms);
    stamp(tier);
  }

  // stampEl -- lazily creates the "last updated" status element in the sidebar
  // footer slot, or returns the existing one.
  function stampEl() {
    let el = document.getElementById("tf-updated");
    if (!el) {
      const slot = document.getElementById("tf-updated-slot") || document.querySelector(".sidebar-foot");
      if (slot) { el = document.createElement("div"); el.id = "tf-updated"; el.className = "tf-updated"; el.setAttribute("role", "status"); slot.appendChild(el); }
    }
    return el;
  }

  // stamp -- updates the sidebar status line to show live / closed market state
  // and the user's tier name + cadence. Called once on unlock and after each refresh.
  function stamp(tier) {
    const el = stampEl();
    if (!el) return;
    if (pausedForClose(tier)) { el.innerHTML = `<span class="tf-dot closed"></span>Markets closed &middot; updates resume 9:30 AM ET`; return; }
    const extended = !marketOpen() ? " &middot; extended-hours" : "";
    el.innerHTML = `<span class="tf-dot"></span>Live &middot; ${E(tier.name)} &middot; every ${tier.refreshMin >= 1440 ? "day" : tier.refreshMin + " min"}${extended}`;
  }

  // marketOpen -- returns true during US equity market core hours (9:30-16:00 ET,
  // Mon-Fri). Uses toLocaleString for DST-correct Eastern time without a library.
  // Holidays are not modeled; refresh simply skips and resumes the next session.
  function marketOpen() {
    try {
      const et = new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
      const day = et.getDay();                       // 0 Sun .. 6 Sat
      if (day === 0 || day === 6) return false;
      const mins = et.getHours() * 60 + et.getMinutes();
      return mins >= 570 && mins < 960;              // 09:30 -> 16:00 ET
    } catch (e) { return true; }                     // if tz lookup fails, don't block refresh
  }

  // pausedForClose -- lower tiers (daily / hourly / 30-min) pause refresh when
  // the market is closed to save API budget. Premium fast tiers (15-min and
  // 30-min) keep refreshing after hours because their subscribers pay for it.
  function pausedForClose(tier) { return !marketOpen() && (tier.refreshMin || 0) > 30; }

  // refreshLiveData -- fetches the two lightweight data scripts (prices and news
  // intel) without a full page reload, then signals app.js to re-render live views.
  // Uses ?t= cache-bust so the browser never serves a stale cached copy.
  async function refreshLiveData(tier) {
    // Server mode: pull /api/data/live. The server itself enforces the per-tier
    // cadence (429 if too soon) and the market-hours pause ({paused:true}), so we
    // just react to its response rather than re-implementing the policy here.
    if (SERVER()) {
      try {
        const res = await window.TFBoot.api("/api/data/live");
        if (res.status === 429) { stamp(tier); return; }              // too soon; keep current data
        if (res.ok && res.data && !res.data.paused) {
          Object.assign(window, res.data);                            // refresh PRICES_DATA / NEWS_INTEL
          if (window.TF && window.TF.onRefresh) window.TF.onRefresh();
          const el = document.getElementById("tf-updated");
          if (el) el.innerHTML = `<span class="tf-dot"></span>Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${E(tier.name)}`;
        } else { stamp(tier); }                                       // paused (market closed)
      } catch (e) { /* offline: keep current data */ }
      return;
    }
    // Lower tiers make no data calls while the market is closed (saves API cost).
    // The build pipeline that holds the paid API budget pauses the same way.
    if (pausedForClose(tier)) { stamp(tier); return; }
    try {
      for (const [src, marker, key] of [["js/prices_data.js", "window.PRICES_DATA =", "PRICES_DATA"], ["js/news_intel.js", "window.NEWS_INTEL =", "NEWS_INTEL"]]) {
        const txt = await (await fetch(src + "?t=" + Date.now(), { cache: "no-store" })).text();
        const json = txt.slice(txt.indexOf(marker) + marker.length).trim().replace(/;\s*$/, "");
        window[key] = JSON.parse(json);
      }
      if (window.TF && window.TF.onRefresh) window.TF.onRefresh();   // let app.js re-render live views
      const el = document.getElementById("tf-updated");
      if (el) el.querySelector(".tf-dot") && (el.firstChild.nextSibling, el.innerHTML = `<span class="tf-dot"></span>Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${tier.name}`);
    } catch (e) { /* offline / file unchanged: keep current data */ }
  }

  // guard -- MutationObserver + periodic interval that re-asserts the gate lock
  // if a user removes the overlay or the tf-locked class via devtools.
  // The observer is disconnected during its own DOM writes to prevent a
  // microtask storm (the tab froze without this guard).
  function guard() {
    let observer = null;
    const reassert = () => {
      if (unlocked) return;
      // Pause observation while we touch the DOM, otherwise our own writes
      // re-trigger the observer as a microtask and starve the page (this froze
      // the tab). Only write when something is actually wrong, then re-observe.
      if (observer) observer.disconnect();
      if (!document.body.classList.contains("tf-locked")) document.body.classList.add("tf-locked");
      if (gate && !document.body.contains(gate)) document.body.appendChild(gate); // re-attach if deleted
      if (gate && gate.style.display !== "flex") gate.style.display = "flex";
      if (observer && !unlocked) observer.observe(document.body, { childList: true });
    };
    try {
      observer = new MutationObserver(reassert);
      observer.observe(document.body, { childList: true });   // detect the gate being deleted
    } catch (e) { /* no observer */ }
    setInterval(reassert, 700);   // periodic fallback for style/class edits
  }

  // Wire up all click handlers and the tamper guard before boot runs.
  bind();
  guard();

  // boot -- entry point called on DOMContentLoaded (or immediately if the DOM is
  // already ready). Waits for boot.js to settle the mode, then:
  //   server  - ask /api/auth/me; a live session unlocks silently, else show login.
  //   static  - a stored localStorage session unlocks silently, else show login.
  async function boot() {
    document.body.classList.add("tf-locked");
    const mode = window.TFBoot ? await window.TFBoot.ready : "static";
    if (mode === "server") {
      loadTierCatalog();   // sync the pricing catalogue from config.TIERS (best-effort)
      let res = null;
      try { res = await window.TFBoot.api("/api/auth/me"); } catch (e) { /* offline */ }
      if (res && res.ok && res.data && res.data.user) { currentUser = adoptServerUser(res.data.user); unlock(false); }
      else showGate("login");
      return;
    }
    if (LS.session && LS.accounts[LS.session]) { currentUser = accountFor(); unlock(false); }
    else showGate("login");
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  // logout -- clears the session, re-locks the app, shows a brief "Goodbye"
  // farewell screen, then transitions back to the login gate.
  // Re-locks in place (no location.reload) because reloading synchronously
  // re-parses ~6 MB of data scripts and trips Chrome's "page unresponsive" warning.
  function logout() {
    // Server mode: clear the httpOnly session cookie server-side (fire-and-forget;
    // the UI proceeds regardless). Static mode: clear the localStorage session.
    if (SERVER()) { try { window.TFBoot.api("/api/auth/logout", { method: "POST" }); } catch (e) {} }
    LS.session = ""; currentUser = null; unlocked = false;
    if (refreshTimer) clearInterval(refreshTimer);
    document.body.classList.add("tf-locked");   // hide the app again
    if (gate) { gate.remove(); gate = null; }   // drop any leftover unlock gate
    const o = document.createElement("div");
    o.className = "auth-gate goodnight"; o.setAttribute("role", "status");
    o.innerHTML = `<div class="auth-unlocked">
      <div class="gn-emoji">
        <svg class="gn-ic gn-face" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="32" cy="32" r="26"/><circle cx="23" cy="27" r="2.6"/><circle cx="41" cy="27" r="2.6"/><path d="M21 39 Q32 49 43 39"/>
        </svg>
        <svg class="gn-ic gn-wave" viewBox="0 0 48 54" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M11 28 C11 14 17 14 17 26 C17 12 23 12 23 25 C23 11 29 11 29 25 C29 13 34 13 34 27 L34 30 C40 27 44 33 38 37 L33 42 C32 46 29 48 25 48 L18 48 C13 48 11 45 11 40 Z"/>
        </svg>
      </div>
      <div class="auth-welcome">Goodbye, friend</div>
      <div class="auth-welcome-sub">See you next session</div></div>`;
    document.body.appendChild(o);
    setTimeout(() => { o.remove(); showGate("login"); }, 1800);
  }

  // Global logout button handler (sidebar). Bound on document so it works even
  // if the sidebar is re-rendered after initial unlock.
  document.addEventListener("click", (e) => { if (e.target.closest("#logoutBtn")) logout(); });

  // window.Auth -- public API consumed by app.js, Settings panel, and other modules.
  window.Auth = {
    TIERS,
    user: () => currentUser,
    tier: () => (currentUser && TIERS[currentUser.tier]) || TIERS.free,
    tiers: () => TIER_CATALOG.slice(),   // ordered, purchasable tiers for the upgrade UI
    // Begin an upgrade. The server is authoritative: this asks the billing seam
    // to start checkout; it can NEVER change the tier client-side. Returns a
    // human-readable status (the seam is stubbed until Stripe is wired up).
    async startCheckout(tierId) {
      if (!SERVER()) return { ok: false, message: "Upgrades require the hosted version." };
      try {
        const res = await window.TFBoot.api("/api/billing/checkout", { method: "POST", body: { tier: tierId } });
        if (res && res.ok && res.data && res.data.checkout_url) { location.href = res.data.checkout_url; return { ok: true }; }
        return { ok: false, message: (res && res.data && res.data.detail) || "Billing isn’t available yet. Coming soon." };
      } catch (e) { return { ok: false, message: "Billing isn’t available yet. Coming soon." }; }
    },
    a11y: () => !!(currentUser && currentUser.a11y),
    profile: () => (currentUser && currentUser.profile) || null,
    computeProfile,
    setProfile(answers) {   // called by the Settings profile editor
      const prof = computeProfile(answers);
      if (SERVER()) {
        // Persist the raw answers server-side; keep the enriched profile for this session.
        try { window.TFBoot.api("/api/auth/profile", { method: "POST", body: answers }); } catch (e) {}
        if (currentUser) currentUser.profile = prof;
        return prof;
      }
      const accs = LS.accounts;
      if (currentUser && accs[LS.session]) { accs[LS.session].profile = prof; LS.accounts = accs; currentUser.profile = prof; }
      return prof;
    },
    setA11y(on) {   // called by the Settings toggle
      if (SERVER()) {
        try { window.TFBoot.api("/api/auth/a11y?on=" + !!on, { method: "POST" }); } catch (e) {}
        if (currentUser) currentUser.a11y = !!on;
        applyA11y(on);
        return;
      }
      const accs = LS.accounts;
      if (currentUser && accs[LS.session]) { accs[LS.session].a11y = !!on; LS.accounts = accs; currentUser.a11y = !!on; }
      applyA11y(on);
    },
    logout,
  };
})();
