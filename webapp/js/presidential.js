// presidential.js
//
// Renders the "Presidential" view: a deduped, most-recent-first feed of
// presidential actions from official primary sources (Federal Register +
// Congress.gov) plus a clearly-labeled secondary news layer. Reads
// window.PRESIDENTIAL, produced by webapp/build_presidential.py.
//
// Transparency framing only: these are public official records and third-party
// news; nothing here alleges wrongdoing.
"use strict";
(function () {
  const P = window.PRESIDENTIAL || {};
  const ITEMS = Array.isArray(P.items) ? P.items : [];

  // self-contained escape (app.js's esc is module-local)
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // only ever emit http(s) links; anything else becomes a non-navigating anchor
  const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "#");

  const TYPES = [
    { id: "all",             label: "All" },
    { id: "executive_order", label: "Executive Orders" },
    { id: "proclamation",    label: "Proclamations" },
    { id: "memo",            label: "Memoranda" },
    { id: "signed_law",      label: "Signed Laws" },
    { id: "tariff_action",   label: "Tariffs" },
    { id: "news",            label: "News" },
  ];
  const BADGE = {
    executive_order: { txt: "Executive Order", cls: "info" },
    proclamation:    { txt: "Proclamation",    cls: "purple" },
    memo:            { txt: "Memorandum",       cls: "warn" },
    signed_law:      { txt: "Signed Law",       cls: "up" },
    tariff_action:   { txt: "Tariff Action",    cls: "down" },
    news:            { txt: "News",              cls: "" },
  };

  let activeType = "all";

  function fmtDate(d) {
    d = String(d || "");
    const m = d.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) {
      const dt = new Date(+m[1], +m[2] - 1, +m[3]);
      return dt.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    }
    return d.slice(0, 24);
  }

  function card(it) {
    const b = BADGE[it.type] || { txt: it.type, cls: "" };
    const eo = it.eo_number ? `<span class="pill mini">EO ${esc(it.eo_number)}</span>` : "";
    const sectors = (it.sectors || []).slice(0, 4)
      .map((s) => `<span class="pill mini">${esc(s)}</span>`).join("");
    const summary = it.summary ? `<p class="pres-sum">${esc(it.summary)}</p>` : "";
    const href = safeUrl(it.url);
    const link = href === "#" ? ""
      : `<a class="pres-src" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(it.source || "Source")} ↗</a>`;
    return `<div class="pres-card">
      <div class="pres-top">
        <span class="pill ${b.cls}">${esc(b.txt)}</span> ${eo}
        <span class="pres-cat">${esc(it.category || "")}</span>
        <span class="pres-date">${esc(fmtDate(it.date))}</span>
      </div>
      <div class="pres-title">${esc(it.title || "")}</div>
      ${summary}
      <div class="pres-foot">${sectors}${link}</div>
    </div>`;
  }

  function listHtml() {
    const rows = ITEMS.filter((it) => activeType === "all" || it.type === activeType);
    if (!rows.length) return `<div class="faint" style="padding:24px;">No items in this category yet.</div>`;
    return rows.map(card).join("");
  }

  function chips() {
    const counts = P.counts || {};
    return TYPES.map((t) => {
      const n = t.id === "all" ? ITEMS.length : (counts[t.id] || 0);
      if (t.id !== "all" && !n) return "";
      return `<button type="button" class="pres-chip${t.id === activeType ? " active" : ""}" data-presfilter="${t.id}" aria-pressed="${t.id === activeType}">${esc(t.label)} <span class="pres-chip-n">${n}</span></button>`;
    }).join("");
  }

  // One document-level listener (added once) handles the filter chips. CSP-safe:
  // no inline handlers; we re-render only the list container on click.
  if (!window.__presFilterWired) {
    window.__presFilterWired = true;
    document.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-presfilter]");
      if (!chip) return;
      activeType = chip.dataset.presfilter;
      const bar = document.getElementById("pres-chips");
      const list = document.getElementById("pres-list");
      if (bar) bar.innerHTML = chips();
      if (list) list.innerHTML = listHtml();
    });
  }

  window.renderPresidential = function () {
    if (!ITEMS.length) {
      return `<div class="page-head"><h2>Presidential</h2><p>Presidential feed not loaded yet.</p></div>`;
    }
    return `
      <div class="page-head"><h2>Presidential Actions</h2>
        <p>Executive orders, proclamations, memoranda, signed laws, and tariff actions — straight from the Federal Register and Congress.gov, most recent first. Official records update on business days; executive orders are published a few days after signing.</p></div>
      <div id="pres-chips" class="pres-chips">${chips()}</div>
      <div id="pres-list" class="pres-list">${listHtml()}</div>
      <div class="sample-note" style="margin-top:14px;">${esc(P.disclaimer || "")} Generated ${esc(String(P.generated_at || "").slice(0, 10))}.</div>`;
  };
})();
