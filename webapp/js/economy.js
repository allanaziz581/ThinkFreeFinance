// economy.js
//
// Economic / Cost-of-Living tracker view. Reads window.ECONOMY (built by
// webapp/build_economy.py) and renders a category-grouped grid of indicator
// cards, each measured against a fixed January 2025 baseline, plus a search
// box and category filter chips. Clicking a card opens a modal with a line
// chart (with a Jan 2025 marker), the three headline stats, and the source.
//
// Conventions reused from app.js (loaded earlier in boot.js LOGIC_SCRIPTS):
//   esc(), openModal()  - global helpers
//   theme tokens only   - var(--danger/--success/--warning/--info), no white
"use strict";
(function () {
  const ECON = window.ECONOMY || {};
  const CATS = ECON.categories || [];

  // current filter state (module-scoped so the delegated handlers can repaint)
  let _q = "";
  let _cat = "All";

  // flatten for search/filter
  function allIndicators() {
    const out = [];
    CATS.forEach((c) => (c.indicators || []).forEach((i) => out.push(Object.assign({ _cat: c.name }, i))));
    return out;
  }

  // headline change: rate indicators move in percentage points, everything
  // else in percent. Returns {text, pct, isBad, isGood, tone, label}.
  function severity(ind) {
    const p = (typeof ind.since_baseline_pct === "number") ? ind.since_baseline_pct : null;
    const a = (typeof ind.since_baseline_abs === "number") ? ind.since_baseline_abs : null;
    const up = (p ?? 0) > 0;
    const isBad = (ind.direction === "price" && up) || (ind.direction === "good" && (p ?? 0) < 0);
    const isGood = (ind.direction === "price" && (p ?? 0) < 0) || (ind.direction === "good" && up);
    const m = Math.abs(p ?? 0);
    let label, tone;
    if (p === null) { label = "No data"; tone = "info"; }
    else if (m < 1) { label = "Flat"; tone = "info"; }
    else {
      const dir = up ? "Up" : "Down";
      label = m >= 10 ? ("Major " + dir) : (up ? "Rise" : "Drop");
      tone = isBad ? "danger" : (isGood ? "success" : "warning");
    }
    const sign = (n) => (n > 0 ? "+" : "");
    const text = ind.is_rate
      ? (a === null ? "n/a" : `${sign(a)}${a.toFixed(2)} pts`)
      : (p === null ? "n/a" : `${sign(p)}${p.toFixed(1)}%`);
    return { text, pct: p, isBad, isGood, tone, label };
  }

  function toneColor(tone) {
    return tone === "danger" ? "var(--danger)"
      : tone === "success" ? "var(--success)"
      : tone === "warning" ? "var(--warning)" : "var(--info)";
  }

  function yoyText(ind) {
    if (ind.is_rate) return (typeof ind.yoy_abs === "number") ? `${ind.yoy_abs > 0 ? "+" : ""}${ind.yoy_abs.toFixed(2)} pts` : "n/a";
    return (typeof ind.yoy_pct === "number") ? `${ind.yoy_pct > 0 ? "+" : ""}${ind.yoy_pct.toFixed(1)}%` : "n/a";
  }

  function card(ind) {
    const s = severity(ind);
    const col = toneColor(s.tone);
    return `<button type="button" class="econ-card" data-econ="${esc(ind.id)}" aria-label="${esc(ind.name)} details">
      <div class="econ-card-head">
        <div class="econ-name">${esc(ind.name)}</div>
        <span class="econ-pill" style="color:${col};border-color:${col};background:transparent;">${esc(s.label)}</span>
      </div>
      <div class="econ-head-num" style="color:${col};">${esc(s.text)}</div>
      <div class="econ-sub">since ${esc(ECON.baseline_label || "Jan 2025")}</div>
      <div class="econ-meta">
        <div><span class="econ-meta-l">Now</span><span class="econ-meta-v">${esc(ind.current_fmt)}</span></div>
        <div><span class="econ-meta-l">Year over year</span><span class="econ-meta-v">${esc(yoyText(ind))}</span></div>
      </div>
      <div class="econ-src">${esc(ind.source)}</div>
    </button>`;
  }

  function paintGrid() {
    const host = document.getElementById("econ-grid");
    if (!host) return;
    const q = _q.trim().toLowerCase();
    const groups = CATS
      .filter((c) => _cat === "All" || c.name === _cat)
      .map((c) => {
        const items = (c.indicators || []).filter((i) => !q || i.name.toLowerCase().includes(q) || c.name.toLowerCase().includes(q));
        if (!items.length) return "";
        return `<div class="econ-cat">
          <div class="econ-cat-title">${esc(c.name)} <span class="faint">${items.length}</span></div>
          <div class="econ-cards">${items.map(card).join("")}</div>
        </div>`;
      })
      .filter(Boolean)
      .join("");
    host.innerHTML = groups || `<div class="faint" style="padding:24px;">No indicators match that search.</div>`;
  }

  function paintChips() {
    const host = document.getElementById("econ-chips");
    if (!host) return;
    const names = ["All"].concat(CATS.map((c) => c.name));
    host.innerHTML = names.map((n) =>
      `<button type="button" class="econ-chip${n === _cat ? " active" : ""}" data-econcat="${esc(n)}">${esc(n)}</button>`
    ).join("");
  }

  // --- modal chart: line with a vertical Jan 2025 marker -------------------
  function chart(series, color, baselineDate) {
    if (!series || series.length < 2) return `<div class="faint">No series data.</div>`;
    const w = 560, h = 180, padX = 6, padY = 10;
    const vals = series.map((p) => p[1]);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = (max - min) || 1;
    const x = (i) => padX + (i / (series.length - 1)) * (w - 2 * padX);
    const y = (v) => padY + (1 - (v - min) / span) * (h - 2 * padY);
    const path = series.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
    const area = `${path} L${x(series.length - 1).toFixed(1)},${h - padY} L${x(0).toFixed(1)},${h - padY} Z`;
    const gid = "eg" + Math.abs((series.length * 13 + Math.round(max)) % 99999);
    // baseline marker: nearest index to the Jan 2025 date
    let bi = -1, bgap = 1e15;
    const bt = Date.parse((baselineDate || "2025-01-01") + "T00:00:00Z");
    series.forEach((p, i) => { const g = Math.abs(Date.parse(p[0] + "T00:00:00Z") - bt); if (g < bgap) { bgap = g; bi = i; } });
    let marker = "";
    if (bi >= 0) {
      const mxN = x(bi);
      const mx = mxN.toFixed(1);
      // a tidy label pill on whichever side of the marker line has more room, so
      // it never overlaps the data line. Two clean lines: the date, then a small
      // caption noting Jan 2025 is the inauguration (no em dash).
      const rightSide = bi > series.length * 0.55;
      const pw = 90, ph = 31, gap = 7;
      const px0 = (rightSide ? (mxN - gap - pw) : (mxN + gap)).toFixed(1);
      marker = `
        <line x1="${mx}" y1="${padY}" x2="${mx}" y2="${h - padY}" stroke="var(--warning)" stroke-width="1.4" stroke-dasharray="5 4" opacity="0.85"/>
        <circle cx="${mx}" cy="${padY + 1}" r="2.6" fill="var(--warning)"/>
        <g transform="translate(${px0},${padY + 2})">
          <rect x="0" y="0" width="${pw}" height="${ph}" rx="6" fill="var(--bg-card)" stroke="var(--warning)" stroke-opacity="0.6"/>
          <text x="${pw / 2}" y="13" text-anchor="middle" fill="var(--warning)" font-size="11" font-weight="700">${esc(ECON.baseline_label || "Jan 2025")}</text>
          <text x="${pw / 2}" y="24.5" text-anchor="middle" fill="var(--text-secondary)" font-size="9">Inauguration</text>
        </g>`;
    }
    const first = series[0][0], last = series[series.length - 1][0];
    return `<svg class="econ-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="time series">
      <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.24"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#${gid})"/>
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
      ${marker}
    </svg>
    <div class="econ-axis"><span>${esc(first)}</span><span>${esc(last)}</span></div>`;
  }

  function openIndicator(id) {
    const ind = allIndicators().find((i) => i.id === id);
    if (!ind) return;
    const s = severity(ind);
    const col = toneColor(s.tone);
    const stat = (label, val, color) =>
      `<div class="econ-stat"><div class="econ-stat-v" ${color ? `style="color:${color};"` : ""}>${esc(val)}</div><div class="econ-stat-l">${esc(label)}</div></div>`;
    const html = `<div class="modal-head"><h2>${esc(ind.name)}</h2>
      <div class="faint">${esc(ind._cat)} . Source: ${esc(ind.source)}</div></div>
      ${chart(ind.series, col, ECON.baseline_date)}
      <div class="econ-modal-stats">
        ${stat("Current (" + (ind.current_date || "") + ")", ind.current_fmt, null)}
        ${stat("Since " + (ECON.baseline_label || "Jan 2025"), s.text, col)}
        ${stat("Year over year", yoyText(ind), null)}
      </div>
      <div class="sample-note">Measured against a fixed ${esc(ECON.baseline_label || "Jan 2025")} baseline${ind.baseline_fmt ? " (" + esc(ind.baseline_fmt) + ")" : ""}. ${esc(ECON.source_note || "")}</div>`;
    if (typeof openModal === "function") openModal(html);
  }

  window.renderEconomy = function () {
    if (!CATS.length) {
      return `<div class="page-head"><h2>Economy Tracker</h2><p class="faint">Economic data has not been built yet. Run webapp/build_economy.py.</p></div>`;
    }
    const total = CATS.reduce((n, c) => n + (c.indicators || []).length, 0);
    // paint chips + grid right after the host innerHTML is set
    requestAnimationFrame(() => { paintChips(); paintGrid(); });
    return `<div class="page-head">
        <h2>Economy and Cost of Living</h2>
        <p>How everyday costs, jobs, and incomes have moved since the ${esc(ECON.baseline_label || "Jan 2025")} baseline. ${total} indicators across ${CATS.length} categories. Prices rising shows red, falling shows green; for jobs and income the colors invert.</p>
      </div>
      <div class="econ-controls">
        <input id="econ-search" class="econ-search" type="search" placeholder="Search indicators, for example eggs, rent, gas" aria-label="Search indicators" value="${esc(_q)}">
      </div>
      <div id="econ-chips" class="econ-chips"></div>
      <div id="econ-grid" class="econ-grid"></div>`;
  };

  // delegated handlers (registered once)
  document.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-econcat]");
    if (chip) { _cat = chip.getAttribute("data-econcat"); paintChips(); paintGrid(); return; }
    const c = e.target.closest("[data-econ]");
    if (c) { openIndicator(c.getAttribute("data-econ")); }
  });
  document.addEventListener("input", (e) => {
    if (e.target && e.target.id === "econ-search") { _q = e.target.value || ""; paintGrid(); }
  });
})();
