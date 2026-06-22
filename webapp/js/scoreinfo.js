// scoreinfo.js
// What it does: implements the progressive score-explanation system -- a hover
//   tooltip on desktop, a bottom sheet on mobile, and a full breakdown modal
//   ("Why this score?") -- so users can understand any accountability score
//   without permanent on-screen formulas.
// How it fits: loaded as a <script defer> in index.html; exposes window.ScoreInfo
//   for congress.js and any other module that renders score badges.

"use strict";
(function () {
  // Pull shared data bundles created by earlier modules.
  const D = window.TF_DATA || {};
  const FEC = (window.FEC_DATA || {}).byName || {};
  const MB = (window.MEMBER_BILLS || {}).byBioguide || {};

  // HTML-escape helper: used before injecting any dynamic string into innerHTML.
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Detect touch-primary devices so we show a bottom sheet instead of a tooltip.
  const isTouch = !!(window.matchMedia && window.matchMedia("(hover: none), (pointer: coarse)").matches);

  // Explainer registry: maps a kind string to a function that returns an
  // explanation object for that kind of score.
  const REG = {};
  function register(kind, fn) { REG[kind] = fn; }

  // Resolve an explanation object from a .si element.
  // Prefers an inline JSON payload (data-si-payload), then falls back to a
  // registered builder function keyed by data-si-kind.
  function explainEl(el) {
    if (el.dataset.siPayload) { try { return JSON.parse(el.dataset.siPayload); } catch (e) { return null; } }
    const fn = REG[el.dataset.siKind];
    return fn ? fn(el.dataset.siKey, el.dataset.siVal) : null;
  }

  // Shared score math used by the political explainer builders below.
  // These mirror the same formulas in congress.js / scores.js so the
  // tooltip numbers are always consistent with the displayed scores.

  // Return the funding breakdown for a politician by name from FEC_DATA.
  function polFunding(name) {
    const f = FEC[name]; if (!f || !f.receipts) return null;
    const total = f.receipts || 1;
    const ind = Math.round((f.from_individuals || 0) / total * 100);
    const pac = Math.round((f.from_pacs || 0) / total * 100);
    return { individual: ind, pac, other: Math.max(0, 100 - ind - pac), total_fmt: f.receipts_fmt };
  }

  // Find a politician record in TF_DATA by exact name.
  function pol(name) { return (D.politicians || []).find((x) => x.name === name); }

  // Extract commonly needed fields from a politician record in one call.
  function polCommon(p) {
    const f = polFunding(p.name); const pacShare = f ? f.pac : 0;
    const mb = MB[p.bioguide] || {};
    return { f, pacShare, mb, trades: p.trades || 0, ret: p.ret || 0 };
  }

  // Political Influence explainer: weighted combination of legislative activity,
  // disclosed trades, PAC funding share, and estimated trading return.
  register("pol-influence", (name) => {
    const p = pol(name); if (!p) return null;
    const { f, pacShare, mb, trades, ret } = polCommon(p);
    const v = Math.round(Math.min(100, 30 + trades * 0.3 + pacShare * 0.6 + Math.abs(ret) * 0.5));
    const bullets = [];
    if (mb.cosponsored) bullets.push(`Cosponsored ${mb.cosponsored.toLocaleString()} bills`);
    if (mb.sponsored) bullets.push(`Sponsored ${mb.sponsored} bills`);
    if (trades) bullets.push(`${trades.toLocaleString()} disclosed market trades`);
    if (pacShare >= 20) bullets.push(`${pacShare}% PAC-funded campaign`);
    if ((p.top_tickers || []).length) bullets.push(`Active across ${p.top_tickers.length}+ companies`);
    return {
      title: "Political Influence Score", value: `${v}/100`,
      bullets: bullets.slice(0, 4),
      why: `${p.name}'s influence score is shaped by their legislative footprint, market-trading activity, and how concentrated their campaign funding is. More bills, more disclosed trades, and a higher share of PAC money all push the score up.`,
      contributors: [
        { label: "Legislative activity", detail: `${(mb.total || 0).toLocaleString()} bills sponsored or cosponsored` },
        { label: "Disclosed trades", detail: `${trades.toLocaleString()} STOCK Act disclosures` },
        { label: "Outside funding exposure", detail: `${pacShare}% of funding from PACs` },
        { label: "Trading performance", detail: `${ret > 0 ? "+" : ""}${ret}% estimated return` },
      ],
      calc: {
        formula: "Influence = 30 base + trades x0.3 + PAC share % x0.6 + |return %| x0.5 (capped 100)",
        rows: [
          { factor: "Base", value: "30" },
          { factor: `Trades (${trades} x0.3)`, value: (trades * 0.3).toFixed(1) },
          { factor: `PAC share (${pacShare}% x0.6)`, value: (pacShare * 0.6).toFixed(1) },
          { factor: `|Return| (${Math.abs(ret)}% x0.5)`, value: (Math.abs(ret) * 0.5).toFixed(1) },
        ], total: `${v}/100`,
      },
      sources: [
        { label: "Congress.gov - sponsored & cosponsored legislation", url: p.bioguide ? `https://www.congress.gov/member/${p.bioguide}` : "" },
        { label: "OpenFEC - campaign finance", url: (FEC[name] && FEC[name].url) || "" },
        { label: "STOCK Act trade disclosures" },
      ],
    };
  });

  // Public Impact explainer: rises when a member relies more on individual
  // donors and less on PAC money -- a proxy for constituent accountability.
  register("pol-public", (name) => {
    const p = pol(name); if (!p) return null;
    const { f, pacShare } = polCommon(p); const indShare = f ? f.individual : 0;
    const v = Math.round(Math.max(10, 70 - pacShare * 0.5 + indShare * 0.2));
    const bullets = [];
    if (indShare >= 40) bullets.push(`${indShare}% individually funded`);
    if (pacShare < 20) bullets.push("Low PAC dependence");
    else bullets.push(`${pacShare}% PAC-funded`);
    bullets.push(f ? `Raised ${f.total_fmt}` : "Limited funding data");
    return {
      title: "Public Impact Score", value: `${v}/100`,
      bullets: bullets.slice(0, 4),
      why: `Public impact rises when a member's funding leans toward individual donors rather than PACs, suggesting accountability to constituents over organized interests.`,
      contributors: [
        { label: "Individual donations", detail: `${indShare}% of funds` },
        { label: "PAC dependence", detail: `${pacShare}% of funds (lowers score)` },
      ],
      calc: { formula: "Public Impact = 70 - PAC share % x0.5 + individual share % x0.2 (floor 10)", rows: [{ factor: "Base", value: "70" }, { factor: `PAC (${pacShare}% x0.5)`, value: "-" + (pacShare * 0.5).toFixed(1) }, { factor: `Individual (${indShare}% x0.2)`, value: "+" + (indShare * 0.2).toFixed(1) }], total: `${v}/100` },
      sources: [{ label: "OpenFEC - campaign finance", url: (FEC[name] && FEC[name].url) || "" }],
    };
  });

  // Transparency explainer: measures exposure rather than intent -- heavy PAC
  // reliance and frequent trading in legislated markets lower the score.
  register("pol-transparency", (name) => {
    const p = pol(name); if (!p) return null;
    const { pacShare, trades } = polCommon(p);
    const v = Math.round(Math.max(5, 100 - pacShare * 1.4 - trades * 0.15));
    const bullets = [];
    bullets.push(pacShare < 20 ? "Largely individually funded" : `${pacShare}% PAC-funded`);
    bullets.push(`${trades.toLocaleString()} disclosed trades`);
    if (pacShare >= 40) bullets.push("High outside-funding exposure");
    return {
      title: "Transparency Score", value: `${v}/100`,
      bullets: bullets.slice(0, 4),
      why: `Transparency is higher when a member relies less on PAC money and trades less frequently in markets they may legislate on. It is a measure of exposure, not an accusation.`,
      contributors: [
        { label: "Outside (PAC) funding", detail: `${pacShare}% of funds (lowers score)` },
        { label: "Trading frequency", detail: `${trades.toLocaleString()} disclosed trades (lowers score)` },
      ],
      calc: { formula: "Transparency = 100 - PAC share % x1.4 - trades x0.15 (floor 5)", rows: [{ factor: "Base", value: "100" }, { factor: `PAC (${pacShare}% x1.4)`, value: "-" + (pacShare * 1.4).toFixed(1) }, { factor: `Trades (${trades} x0.15)`, value: "-" + (trades * 0.15).toFixed(1) }], total: `${v}/100` },
      sources: [{ label: "OpenFEC - campaign finance" }, { label: "STOCK Act trade disclosures" }],
    };
  });

  // Company score builder: delegates to window.TFScores for the raw numbers,
  // then wraps them in the standard explanation shape. The "which" parameter
  // selects between the "influence" and "dependency" score views.
  function companyExp(tk, which) {
    const S = window.TFScores; if (!S) return null;
    const ex = S.politicalExposure(tk);
    const name = (window.PRICES_DATA && window.PRICES_DATA.byTicker[tk] && window.PRICES_DATA.byTicker[tk].name) || tk;
    const bullets = [];
    if (ex.contracts_raw) bullets.push(`${ex.contracts} in federal contracts`);
    if (ex.lobby_spend) bullets.push(`${ex.lobby_spend} on federal lobbying`);
    if (ex.lobby_firms) bullets.push(`Hires ${ex.lobby_firms} lobbying firm${ex.lobby_firms > 1 ? "s" : ""}`);
    if (ex.lobby_bills) bullets.push(`Lobbies on ${ex.lobby_bills} bills`);
    if (ex.bills) bullets.push(`Named in ${ex.bills} tracked bills`);
    if (ex.congressional_traders) bullets.push(`${ex.congressional_traders} members of Congress traded it`);

    // Government Dependency view: focuses on contract revenue vs. total revenue.
    if (which === "dependency") {
      return {
        title: "Government Dependency Score", value: `${ex.dependency}/100`,
        bullets: (ex.contracts_raw ? [`${ex.contracts} in federal contracts`, "Relative to company revenue"] : ["No federal contracts on record"]),
        why: `${name}'s dependency score estimates how much of its business leans on federal contracts versus its overall revenue. A higher score means more reliance on government spending.`,
        contributors: [{ label: "Federal contracts", detail: ex.contracts }, { label: "Company revenue", detail: "5-year basis (SEC)" }],
        calc: { formula: "Dependency = federal contracts / (~5yr revenue) x140 (capped 100)", rows: [{ factor: "Federal contracts", value: ex.contracts }], total: `${ex.dependency}/100` },
        sources: [{ label: "USASpending.gov - federal contracts" }, { label: "SEC EDGAR - revenue" }],
      };
    }

    // Company Influence view: aggregates all government-entanglement signals.
    return {
      title: "Company Influence Score", value: `${ex.influence}/100`,
      bullets: bullets.slice(0, 4).length ? bullets.slice(0, 4) : ["Limited public-entanglement signals"],
      why: `${name}'s influence score reflects its entanglement with government across every dataset we track: federal contract money, federal lobbying money and footprint, mentions in legislation, congressional trading of its stock, and governance.`,
      contributors: [
        { label: "Federal contracts", detail: ex.contracts },
        { label: "Federal lobbying", detail: ex.lobby_spend ? `${ex.lobby_spend} via ${ex.lobby_firms} firm(s), ${ex.lobby_bills} bills` : ex.lobbying },
        { label: "Legislation", detail: `${ex.bills} tracked bills` },
        { label: "Congressional trading", detail: `${ex.trades} trades by ${ex.congressional_traders} members` },
      ],
      calc: { formula: "Influence = contracts(log $, <=38) + lobbying spend(log $, <=16) + lobbying footprint(firms+bills, <=16) + registered(4) + bills(<=12) + trades+members(<=14) + board(<=4)", rows: [{ factor: "Federal contracts", value: ex.contracts }, { factor: "Lobbying spend", value: ex.lobby_spend || "n/a" }, { factor: "Lobbying firms / bills", value: `${ex.lobby_firms} / ${ex.lobby_bills}` }, { factor: "Legislation", value: ex.bills }, { factor: "Congressional trades", value: ex.trades }], total: `${ex.influence}/100` },
      sources: [{ label: "USASpending.gov - federal contracts" }, { label: "Senate LDA - lobbying" }, { label: "Congress.gov - legislation" }, { label: "SEC EDGAR" }, { label: "STOCK Act disclosures" }],
    };
  }

  // Register the two company score kinds using the shared builder above.
  register("company-influence", (tk) => companyExp(tk, "influence"));
  register("company-dependency", (tk) => companyExp(tk, "dependency"));

  // DOM singletons: the tooltip, bottom sheet, and modal are each created once
  // on first use and reused for every subsequent interaction.
  let tipEl, sheetEl, modalEl, built = false;

  // Lazily build all three overlay elements and attach their close handlers.
  function build() {
    if (built) return; built = true;
    tipEl = document.createElement("div"); tipEl.className = "si-tip"; document.body.appendChild(tipEl);
    sheetEl = document.createElement("div"); sheetEl.className = "si-sheet-wrap"; sheetEl.innerHTML = '<div class="si-sheet-bg"></div><div class="si-sheet" role="dialog"></div>'; document.body.appendChild(sheetEl);
    modalEl = document.createElement("div"); modalEl.className = "si-modal-wrap"; modalEl.innerHTML = '<div class="si-modal" role="dialog"><button class="si-modal-x" aria-label="Close">&times;</button><div class="si-modal-body"></div></div>'; document.body.appendChild(modalEl);
    sheetEl.querySelector(".si-sheet-bg").addEventListener("click", closeSheet);
    modalEl.addEventListener("click", (e) => { if (e.target === modalEl || e.target.closest(".si-modal-x")) closeModal(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeSheet(); closeModal(); } });
  }

  // Render an array of bullet strings as a <ul> for use inside tooltips/sheets.
  function bullets(b) { return `<ul class="si-bullets">${(b || []).map((x) => `<li>${E(x)}</li>`).join("")}</ul>`; }

  // Position and show the desktop hover tooltip near the cursor, flipping sides
  // if the default position would overflow the viewport.
  function showTip(exp, x, y) {
    build();
    tipEl.innerHTML = `<div class="si-tip-h">Why this score?</div>${bullets(exp.bullets)}<div class="si-tip-cta">Click for full breakdown &rarr;</div>`;
    tipEl.classList.add("open");
    const w = tipEl.offsetWidth, h = tipEl.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    let lx = x + 16, ly = y + 16;
    if (lx + w > vw - 8) lx = x - w - 16;
    if (ly + h > vh - 8) ly = vh - h - 8;
    tipEl.style.left = Math.max(8, lx) + "px"; tipEl.style.top = Math.max(8, ly) + "px";
  }
  function hideTip() { if (tipEl) tipEl.classList.remove("open"); }

  // Show the mobile bottom sheet with a short summary and a "View Full
  // Breakdown" button that promotes to the modal.
  function openSheet(exp) {
    build(); hideTip();
    sheetEl.querySelector(".si-sheet").innerHTML =
      `<div class="si-sheet-grip"></div>
       <div class="si-sheet-title">${E(exp.title)}</div>
       <div class="si-sheet-val">${E(exp.value || "")}</div>
       <div class="si-tip-h">Why this score?</div>${bullets(exp.bullets)}
       <button class="si-fullbtn" data-si-full="1">View Full Breakdown</button>`;
    sheetEl.querySelector(".si-fullbtn").addEventListener("click", () => { closeSheet(); openModal(exp); });
    sheetEl.classList.add("open");
  }
  function closeSheet() { if (sheetEl) sheetEl.classList.remove("open"); }

  // Render the full breakdown modal: score, plain-English "why", optional
  // upside/downside lists, contributor table, collapsible calculation, and
  // collapsible sources. Glossary.annotate() adds hover definitions if loaded.
  function openModal(exp) {
    build(); hideTip(); closeSheet();
    const contrib = (exp.contributors || []).filter((c) => c && c.detail);
    const calc = exp.calc;
    const src = exp.sources || [];
    const up = exp.upside || [], down = exp.downside || [], inputs = exp.inputs || [];
    const G = (s) => window.Glossary ? window.Glossary.annotate(s) : s;   // wrap finance jargon with hover defs
    modalEl.querySelector(".si-modal-body").innerHTML = `
      <div class="si-m-eyebrow">${E(exp.title)}</div>
      <div class="si-m-score">${E(exp.value || "")}</div>
      <div class="si-m-sec">${E(exp.whyLabel || "Why this score was assigned")}</div>
      <p class="si-m-why">${G(E(exp.why || ""))}</p>
      ${up.length ? `<div class="si-m-sec">Potential upside drivers</div><ul class="si-bullets si-m-up">${up.map((x) => `<li>${G(E(x))}</li>`).join("")}</ul>` : ""}
      ${down.length ? `<div class="si-m-sec">Potential downside risks</div><ul class="si-bullets si-m-down">${down.map((x) => `<li>${G(E(x))}</li>`).join("")}</ul>` : ""}
      ${inputs.length ? `<div class="si-m-sec">Key model inputs</div><div class="si-m-inputs">${inputs.map((x) => `<div><span>${E(x.label)}</span><b>${G(E(x.value))}</b></div>`).join("")}</div>` : ""}
      ${contrib.length ? `<div class="si-m-sec">Largest contributors</div>
        <div class="si-m-contrib">${contrib.map((c, i) => `<div class="si-m-crow"><span class="si-m-rank">${i + 1}</span><div><div class="si-m-clabel">${E(c.label)}</div><div class="si-m-cdetail">${E(c.detail)}</div></div></div>`).join("")}</div>` : ""}
      ${calc ? `<details class="si-m-details"><summary>${E(exp.calcLabel || "How was this calculated?")}</summary>
        <div class="si-m-calc"><div class="si-m-formula">${E(calc.formula)}</div>
        <table class="si-m-table"><tbody>${(calc.rows || []).map((r) => `<tr><td>${E(r.factor)}</td><td class="num">${E(r.value)}</td></tr>`).join("")}<tr class="si-m-total"><td>Final score</td><td class="num">${E(calc.total)}</td></tr></tbody></table></div></details>` : ""}
      ${src.length ? `<details class="si-m-details"><summary>View Sources</summary>
        <ul class="si-m-sources">${src.map((s) => `<li>${s.url ? `<a href="${E(s.url)}" target="_blank" rel="noopener">${E(s.label)} &#8599;</a>` : E(s.label)}</li>`).join("")}</ul></details>` : ""}
      <div class="si-m-foot">${E(exp.foot || "Transparency estimate from public data. Does not imply or allege wrongdoing of any kind.")}</div>`;
    modalEl.classList.add("open");
  }
  function closeModal() { if (modalEl) modalEl.classList.remove("open"); }

  // Delegated event listeners: a single set of listeners on document handles
  // all .si elements, present and future, without per-element binding.
  function bindOnce() {
    if (document._siBound) return; document._siBound = true;

    // Desktop-only: show tooltip on mouseover and track cursor position.
    if (!isTouch) {
      document.addEventListener("mouseover", (e) => { const el = e.target.closest(".si"); if (el) { const exp = explainEl(el); if (exp) showTip(exp, e.clientX, e.clientY); } });
      document.addEventListener("mousemove", (e) => { if (tipEl && tipEl.classList.contains("open")) { const el = e.target.closest(".si"); if (el) showTip(explainEl(el), e.clientX, e.clientY); else hideTip(); } });
      document.addEventListener("mouseout", (e) => { const el = e.target.closest(".si"); if (el && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest(".si"))) hideTip(); });
    }

    // Click on any .si element: open bottom sheet on touch, full modal on desktop.
    document.addEventListener("click", (e) => {
      const el = e.target.closest(".si"); if (!el) return;
      e.stopPropagation();
      const exp = explainEl(el); if (!exp) return;
      if (isTouch) openSheet(exp); else openModal(exp);
    }, true);
  }
  bindOnce();

  // Public markup helper: wrap a score value in a .si span so it automatically
  // gets hover/tap treatment. Callers pass a kind+key to use a registered
  // builder, or supply a payload object for inline explanation data.
  function badge(kind, key, value, opts) {
    opts = opts || {};
    const payload = opts.payload ? ` data-si-payload="${E(JSON.stringify(opts.payload))}"` : "";
    return `<span class="si"${kind ? ` data-si-kind="${E(kind)}"` : ""}${key != null ? ` data-si-key="${E(key)}"` : ""} data-si-val="${E(value)}" tabindex="0"${payload}>${E(value)}<i class="si-i" aria-hidden="true">&#9432;</i></span>`;
  }

  // Expose the public API on window.ScoreInfo for use by congress.js and others.
  window.ScoreInfo = { register, badge, openModal, openSheet, explainEl };
})();
