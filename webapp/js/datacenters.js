// datacenters.js
//
// Renders the "Data Centers" view. Reads window.DATACENTERS, produced by
// webapp/build_datacenters.py (Census ACS county data + EIA electricity +
// curated public data-center locations).
//
// Framing: informational, compiled from public records. The page links the
// data-center buildout to LOCAL cost of living (electricity rates + rent burden)
// and shows a fully transparent risk-score methodology. It does not allege
// wrongdoing by any company or jurisdiction.
"use strict";
(function () {
  const DC = window.DATACENTERS || {};
  const REGIONS = DC.regions || [];
  const M = DC.methodology || {};

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const dollars = (n) => (n == null ? "n/a" : "$" + Math.round(n).toLocaleString());
  const pop = (n) => (n == null ? "n/a" : Math.round(n).toLocaleString());

  function riskClass(v) { return v >= 50 ? "down" : v >= 30 ? "warn" : "up"; }
  function riskBar(v) {
    const cls = riskClass(v);
    const col = cls === "down" ? "var(--danger)" : cls === "warn" ? "var(--warning)" : "var(--success)";
    return `<div class="dc-risk"><div class="dc-risk-track"><div class="dc-risk-fill" style="width:${Math.min(100, v).toFixed(0)}%;background:${col}"></div></div><span class="dc-risk-num ${cls}">${esc(v)}</span></div>`;
  }

  // mini 4-segment bar showing the weighted inputs behind a region's score
  function inputBars(inp) {
    const items = [
      ["Power", inp.power_availability, "var(--info)"],
      ["Water", inp.water_capacity, "var(--success)"],
      ["Land", inp.land_availability, "var(--purple)"],
      ["Exposure", inp.datacenter_exposure, "var(--warning)"],
    ];
    return items.map(([l, v, c]) =>
      `<div class="dc-inp" title="${esc(l)}: ${esc(v)}/100"><span class="dc-inp-l">${esc(l)}</span><div class="dc-inp-track"><div class="dc-inp-fill" style="width:${Math.min(100, v || 0).toFixed(0)}%;background:${c}"></div></div></div>`
    ).join("");
  }

  window.renderDataCenters = function () {
    if (!REGIONS.length) {
      return `<div class="page-head"><h2>Data Centers</h2><p>Data Centers dataset not loaded.</p></div>`;
    }
    const w = M.weights || {};
    const topRent = [...REGIONS].filter((r) => r.rent_burden_pct).sort((a, b) => b.rent_burden_pct - a.rent_burden_pct)[0];

    const rows = REGIONS.map((r) => `
      <tr>
        <td><div style="font-weight:700;">${esc(r.county)}, ${esc(r.state)}</div><div class="faint">${esc(r.hub || "")}</div></td>
        <td>${riskBar(r.buildout_risk)}<div class="dc-inputs">${inputBars(r.inputs || {})}</div></td>
        <td class="num">${esc(r.dc_count)}</td>
        <td class="num">${r.electricity_cents_kwh == null ? "n/a" : esc(r.electricity_cents_kwh) + "¢"}</td>
        <td class="num">${esc(dollars(r.median_rent))}</td>
        <td class="num">${r.rent_burden_pct == null ? "n/a" : `<span class="pill mini ${r.rent_burden_pct >= 30 ? "down" : "warn"}">${esc(r.rent_burden_pct)}%</span>`}</td>
      </tr>`).join("");

    const inputDocs = Object.entries(M.inputs || {}).map(([k, v]) =>
      `<li><b>${esc(k.replace(/_/g, " "))}</b> , ${esc(v)}</li>`).join("");
    const sources = (DC.sources || []).map((s) => `<li>${esc(s)}</li>`).join("");

    return `
      <div class="page-head"><h2>Data Centers &amp; Cost of Living</h2>
        <p>The hyperscale data-center buildout competes with households for local electricity, water, and land , which can push up utility rates and housing costs in host counties. This tracks where buildout pressure is highest and shows the cost-of-living side directly.</p></div>

      <div class="tf-disclaimer compact" style="margin-bottom:16px;">
        <strong>Informational, sourced from public records.</strong>
        ${esc(DC.disclaimer || "")}
      </div>

      <div class="grid cols-3">
        <div class="card pad-lg dc-kpi"><div class="dc-kpi-v">${esc(REGIONS.length)}</div><div class="dc-kpi-l">Counties tracked</div></div>
        <div class="card pad-lg dc-kpi"><div class="dc-kpi-v">${esc(REGIONS[0].county)}, ${esc(REGIONS[0].state)}</div><div class="dc-kpi-l">Highest buildout-risk county</div></div>
        <div class="card pad-lg dc-kpi"><div class="dc-kpi-v">${topRent ? esc(topRent.rent_burden_pct) + "%" : "n/a"}</div><div class="dc-kpi-l">Highest rent burden${topRent ? " , " + esc(topRent.county) : ""}</div></div>
      </div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title"><span class="dot"></span>Buildout Risk by County</div>
          <div class="faint">ACS ${esc(DC.acs_year || "")}${DC.eia_live ? " · EIA live" : " · EIA 2024 ref"}</div></div>
        <table class="tf"><thead><tr>
          <th>County</th><th>Buildout risk &amp; inputs</th><th class="num">Data centers</th>
          <th class="num">Electricity</th><th class="num">Median rent</th><th class="num">Rent burden</th>
        </tr></thead><tbody>${rows}</tbody></table>
        <div class="sample-note">Rent burden = annualized median rent ÷ median household income (Census ACS). Electricity = residential ¢/kWh (EIA). Buildout risk is an estimate; see methodology below.</div>
      </div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Methodology , every input &amp; weight is visible</div></div>
        <div class="tf-methodology">
          <p>${esc(M.summary || "")}</p>
          <p class="dc-formula"><code>${esc(M.formula || "")}</code></p>
          <div class="dc-weights">
            ${["power", "water", "land", "exposure"].map((k) => `<div class="dc-weight"><div class="dc-weight-v">${Math.round((w[k] || 0) * 100)}%</div><div class="dc-weight-l">${esc(k)}</div></div>`).join("")}
          </div>
          <ul class="dc-doclist">${inputDocs}</ul>
          <p class="faint">${esc(M.cost_of_living_link || "")}</p>
          <div class="tf-meth-title">Sources</div>
          <ul class="dc-doclist">${sources}</ul>
          <p class="faint">Extension point: the location list is a curated seed from public records. Per-project / per-county detail (e.g. a Florida-county curation) can be added without changing the schema or scoring.</p>
        </div>
      </div>`;
  };
})();
