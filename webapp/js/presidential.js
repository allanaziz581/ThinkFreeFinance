// presidential.js
//
// Presidential feed with TWO view modes:
//   * "Reels" (default): full-bleed, scroll-snapping vertical cards - one
//     presidential action at a time, swipe/scroll between them (feels native on
//     a phone).
//   * "List": a dense, scannable top-to-bottom layout of the same items.
// A segmented toggle switches modes with an animated crossfade/layout morph
// (skipped under prefers-reduced-motion). Chosen mode persists for the session.
//
// Reads window.PRESIDENTIAL (webapp/build_presidential.py). Official records +
// third-party news; transparency framing only, nothing alleges wrongdoing.
"use strict";
(function () {
  const P = window.PRESIDENTIAL || {};
  const ITEMS = Array.isArray(P.items) ? P.items : [];

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "#");
  const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const BADGE = {
    executive_order: { txt: "Executive Order", cls: "info" },
    proclamation:    { txt: "Proclamation",    cls: "purple" },
    memo:            { txt: "Memorandum",       cls: "warn" },
    signed_law:      { txt: "Signed Law",       cls: "up" },
    tariff_action:   { txt: "Tariff Action",    cls: "down" },
    news:            { txt: "News",              cls: "" },
  };

  let mode = "reels";
  try { const m = sessionStorage.getItem("tf-pres-mode"); if (m === "list" || m === "reels") mode = m; } catch (e) {}

  function fmtDate(d) {
    d = String(d || "");
    const m = d.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
    return d.slice(0, 24);
  }
  function badge(it) { return BADGE[it.type] || { txt: it.type, cls: "" }; }
  function tags(it) {
    const eo = it.eo_number ? `<span class="pres-tag eo">EO ${esc(it.eo_number)}</span>` : "";
    const cat = it.category && it.category !== "General" ? `<span class="pres-tag">${esc(it.category)}</span>` : "";
    const sec = (it.sectors || []).slice(0, 4).map((s) => `<span class="pres-tag sector">${esc(s)}</span>`).join("");
    return eo + cat + sec;
  }
  function srcLink(it) {
    const href = safeUrl(it.url);
    return href === "#" ? "" : `<a class="pres-src" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(it.source || "Official source")} ↗</a>`;
  }

  // ---- Reels: one full-bleed snap card per item ----
  function reelCard(it) {
    const b = badge(it);
    const summary = it.summary ? `<p class="reel-sum">${esc(it.summary)}</p>` : "";
    return `<article class="reel-card" tabindex="0">
      <div class="reel-glow"></div>
      <div class="reel-inner">
        <div class="reel-badge pill ${b.cls}">${esc(b.txt)}</div>
        <div class="reel-date">${esc(fmtDate(it.date))}</div>
        <h3 class="reel-title">${esc(it.title || "")}</h3>
        ${summary}
        <div class="reel-tags">${tags(it)}</div>
        <div class="reel-foot">${srcLink(it)}<span class="reel-hint">scroll ↓</span></div>
      </div>
    </article>`;
  }

  // ---- List: dense rows ----
  function listRow(it) {
    const b = badge(it);
    const summary = it.summary ? `<p class="pres-sum">${esc(it.summary)}</p>` : "";
    return `<div class="pres-card">
      <div class="pres-top">
        <span class="pill ${b.cls}">${esc(b.txt)}</span>
        ${it.eo_number ? `<span class="pres-tag eo">EO ${esc(it.eo_number)}</span>` : ""}
        <span class="pres-cat">${esc(it.category || "")}</span>
        <span class="pres-date">${esc(fmtDate(it.date))}</span>
      </div>
      <div class="pres-title">${esc(it.title || "")}</div>
      ${summary}
      <div class="pres-foot">${(it.sectors || []).slice(0, 4).map((s) => `<span class="pres-tag sector">${esc(s)}</span>`).join("")}${srcLink(it)}</div>
    </div>`;
  }

  function stageHtml() {
    if (mode === "reels") return `<div class="pres-reels" id="pres-stage-inner">${ITEMS.map(reelCard).join("")}</div>`;
    return `<div class="pres-listwrap" id="pres-stage-inner">${ITEMS.map(listRow).join("")}</div>`;
  }

  function toggle() {
    const seg = (id, label, svg) => `<button type="button" class="pres-seg${mode === id ? " active" : ""}" data-presmode="${id}" aria-pressed="${mode === id}">${svg}<span>${label}</span></button>`;
    return `<div class="pres-toggle" role="tablist" aria-label="View mode">
      ${seg("reels", "Reels", '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9"><rect x="5" y="3" width="14" height="18" rx="3"/><path d="M10 8l5 3-5 3V8Z"/></svg>')}
      ${seg("list", "List", '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9"><line x1="8" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="20" y2="12"/><line x1="8" y1="18" x2="20" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>')}
    </div>`;
  }

  // Swap mode with an animated crossfade/morph (unless reduced-motion).
  function setMode(next) {
    if (next === mode) return;
    mode = next;
    try { sessionStorage.setItem("tf-pres-mode", mode); } catch (e) {}
    const stage = document.getElementById("pres-stage");
    const bar = document.getElementById("pres-toggle");
    if (bar) bar.innerHTML = toggle().replace(/^<div[^>]*>|<\/div>$/g, "");
    if (!stage) return;
    if (reduceMotion()) { stage.innerHTML = stageHtml(); return; }
    stage.classList.add("pres-morph-out");
    setTimeout(() => {
      stage.innerHTML = stageHtml();
      stage.classList.remove("pres-morph-out");
      stage.classList.add("pres-morph-in");
      setTimeout(() => stage.classList.remove("pres-morph-in"), 320);
    }, 180);
  }

  if (!window.__presModeWired) {
    window.__presModeWired = true;
    document.addEventListener("click", (e) => {
      const seg = e.target.closest("[data-presmode]");
      if (!seg) return;
      setMode(seg.dataset.presmode);
    });
  }

  window.renderPresidential = function () {
    if (!ITEMS.length) return `<div class="page-head"><h2>Presidential</h2><p>Presidential feed not loaded yet.</p></div>`;
    return `
      <div class="page-head pres-head">
        <div><h2>Presidential Actions</h2>
          <p>Executive orders, proclamations, memoranda, signed laws, and tariff actions from the Federal Register and Congress.gov, most recent first. Official records update on business days; EOs publish a few days after signing.</p></div>
        <div id="pres-toggle">${toggle()}</div>
      </div>
      <div id="pres-stage" class="pres-stage ${mode === "reels" ? "is-reels" : "is-list"}">${stageHtml()}</div>
      <div class="sample-note" style="margin-top:12px;">${esc(P.disclaimer || "")} Generated ${esc(String(P.generated_at || "").slice(0, 10))}.</div>`;
  };
})();
