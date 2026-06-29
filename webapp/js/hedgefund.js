// hedgefund.js
//
// Renders the "Hedge Funds" view + a compact systemic-risk snapshot card that
// app.js injects into the Intelligence page. Reads window.HEDGEFUND, produced by
// webapp/build_hedgefund.py from the OFR Hedge Fund Monitor (Form PF aggregates).
//
// Data is public (OFR); transparency framing only - this describes aggregate
// positioning, it does not allege wrongdoing or identify any individual fund.
"use strict";
(function () {
  const HF = window.HEDGEFUND || {};
  const SER = HF.series || {};
  const SUM = HF.summary || {};

  // self-contained escape (app.js's esc is module-local)
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function usd(n) {
    if (n == null || isNaN(n)) return "n/a";
    const a = Math.abs(n);
    if (a >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (a >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (a >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    return `$${Math.round(n).toLocaleString()}`;
  }
  function fmtVal(v, unit) {
    if (v == null) return "n/a";
    if (unit === "count") return Math.round(v).toLocaleString();
    if (unit === "ratio") return v.toFixed(1) + "x";
    return usd(v);
  }
  function trendChip(pct) {
    if (pct == null) return "";
    const cls = pct > 0 ? "up" : pct < 0 ? "down" : "warn";
    const arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "→";
    return `<span class="pill mini ${cls}">${arrow} ${Math.abs(pct)}% QoQ</span>`;
  }

  // Real SVG line chart from [[date, value], ...]. Theme-token colors only.
  function lineChart(points, color) {
    if (!points || points.length < 2) return `<div class="faint">No series data.</div>`;
    const w = 520, h = 130, pad = 4;
    const vals = points.map((p) => p[1]);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = max - min || 1;
    const x = (i) => pad + (i / (points.length - 1)) * (w - 2 * pad);
    const y = (v) => pad + (1 - (v - min) / span) * (h - 2 * pad);
    const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
    const area = `${path} L${x(points.length - 1).toFixed(1)},${h - pad} L${x(0).toFixed(1)},${h - pad} Z`;
    const gid = "hfg" + Math.abs((points.length * 7 + Math.round(max)) % 99999);
    const first = points[0][0], last = points[points.length - 1][0];
    return `<svg class="hf-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="time series">
      <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.26"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#${gid})"/>
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
    </svg>
    <div class="hf-axis"><span>${esc(first)}</span><span>${esc(last)}</span></div>`;
  }

  function group(name) {
    return Object.values(SER).filter((s) => s.group === name);
  }
  // horizontal composition bars for latest values of a group
  function compBars(items, color) {
    const max = Math.max(...items.map((s) => Math.abs(s.latest || 0))) || 1;
    return items.sort((a, b) => (b.latest || 0) - (a.latest || 0)).map((s) => {
      const pct = Math.abs(s.latest || 0) / max * 100;
      return `<div class="hf-bar-row">
        <div class="hf-bar-label">${esc(s.label)}</div>
        <div class="hf-bar-track"><div class="hf-bar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div></div>
        <div class="hf-bar-val">${esc(usd(s.latest))} ${trendChip(s.qoq_pct)}</div>
      </div>`;
    }).join("");
  }

  // Compact snapshot card for the Intelligence page ("refine the data" hook).
  window.renderHedgeFundCard = function () {
    if (!HF.summary) return "";
    const lev = SUM.leverage_ratio_largest;
    const sevCls = (SUM.leverage_qoq_pct || 0) > 2 ? "down" : (SUM.leverage_qoq_pct || 0) < -2 ? "up" : "warn";
    return `<div class="card pad-lg">
      <div class="card-head"><div class="card-title"><span class="dot"></span>Systemic Risk — Hedge Fund Positioning</div>
        <div class="card-action" data-goto="hedgefund">Hedge Funds →</div></div>
      <div class="hf-snap">
        <div class="hf-stat"><div class="hf-stat-v">${esc(usd(SUM.gross_asset_value))}</div><div class="hf-stat-l">Gross assets</div></div>
        <div class="hf-stat"><div class="hf-stat-v">${esc(usd(SUM.gross_notional_exposure))}</div><div class="hf-stat-l">Gross notional exposure</div></div>
        <div class="hf-stat"><div class="hf-stat-v">${lev == null ? "n/a" : lev.toFixed(1) + "x"} ${trendChip(SUM.leverage_qoq_pct)}</div><div class="hf-stat-l">Leverage (largest funds)</div></div>
      </div>
      <div class="hf-read ${sevCls}">${esc(SUM.systemic_read || "")}</div>
      <div class="sample-note">Source: U.S. Office of Financial Research — Hedge Fund Monitor (Form PF), as of ${esc(SUM.as_of || HF.as_of || "n/a")}. Aggregate positioning only; not fund-specific.</div>
    </div>`;
  };

  window.renderHedgeFund = function () {
    if (!HF.summary) {
      return `<div class="page-head"><h2>Hedge Funds</h2><p>Hedge Fund Monitor data not loaded.</p></div>`;
    }
    const gav = SER["FPF-ALLQHF_GAV_SUM"];
    const lever = SER["FPF-ALLQHF_GAVN10_LEVERAGERATIO_AVERAGE"];
    const sizeStats = group("size");
    const gne = group("gne");
    const borrow = group("borrow");
    const cdsUp = SER["FPF-ALLQHF_CDSUP250BPS_P50"];
    const cdsDn = SER["FPF-ALLQHF_CDSDOWN250BPS_P50"];

    const statTiles = sizeStats.map((s) =>
      `<div class="hf-stat"><div class="hf-stat-v">${esc(fmtVal(s.latest, s.unit))} ${trendChip(s.qoq_pct)}</div><div class="hf-stat-l">${esc(s.label)}</div></div>`).join("");

    return `
      <div class="page-head"><h2>Hedge Fund Positioning</h2>
        <p>What hedge funds are doing in aggregate — size, leverage, and where their risk sits — from regulatory Form PF filings. A real systemic-risk read: crowded, highly-levered positioning is a classic stress signal.</p></div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title"><span class="dot"></span>Industry Size &amp; Leverage</div>
          <div class="faint">as of ${esc(HF.as_of || "n/a")}</div></div>
        <div class="hf-snap wide">${statTiles}</div>
        <div class="grid cols-2" style="margin-top:14px;">
          <div><div class="hf-chart-title">Gross Asset Value</div>${lineChart(gav && gav.data, "var(--info)")}</div>
          <div><div class="hf-chart-title">Leverage ratio (largest funds)</div>${lineChart(lever && lever.data, "var(--warning)")}</div>
        </div>
      </div>

      <div class="grid cols-2">
        <div class="card pad-lg">
          <div class="card-head"><div class="card-title">Gross Notional Exposure by Asset Class</div></div>
          ${compBars(gne, "var(--info)")}
          <div class="sample-note">Latest gross notional exposure (long + short) per asset class. QoQ change shows where funds are adding or cutting risk.</div>
        </div>
        <div class="card pad-lg">
          <div class="card-head"><div class="card-title">Borrowing by Strategy</div></div>
          ${compBars(borrow, "var(--purple)")}
          <div class="sample-note">Dollar borrowing by hedge-fund strategy. Rising borrowing concentrated in one strategy can signal a crowded trade.</div>
        </div>
      </div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Systemic Read &amp; Credit (CDS) Stress Sensitivity</div></div>
        <div class="hf-read ${(SUM.leverage_qoq_pct || 0) > 2 ? "down" : "warn"}">${esc(SUM.systemic_read || "")}</div>
        <div class="hf-snap" style="margin-top:12px;">
          <div class="hf-stat"><div class="hf-stat-v">${cdsUp ? esc(usd(cdsUp.latest)) : "n/a"}</div><div class="hf-stat-l">Median P&amp;L if CDS spreads +250bps</div></div>
          <div class="hf-stat"><div class="hf-stat-v">${cdsDn ? esc(usd(cdsDn.latest)) : "n/a"}</div><div class="hf-stat-l">Median P&amp;L if CDS spreads -250bps</div></div>
        </div>
        <div class="tf-methodology">
          <div class="tf-meth-title">Source &amp; method</div>
          <p>Data: <a href="${esc(HF.source_url || "https://www.financialresearch.gov/hedge-fund-monitor/")}" target="_blank" rel="noopener">U.S. Office of Financial Research — Hedge Fund Monitor</a>, derived from SEC/CFTC Form PF filings. Free, public, no API key. ${esc(HF.count || 0)} series tracked; updated quarterly as filings are processed.</p>
          <p class="faint">Informational. Describes aggregate hedge-fund positioning to illustrate systemic risk. It does not identify any individual fund or allege wrongdoing of any kind.</p>
        </div>
      </div>`;
  };
})();
