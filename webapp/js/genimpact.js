// genimpact.js
// What it does: Builds "Generation Impact" scores that quantify how a bill,
//   company, sector, or state's economic activity lands on each of the five
//   U.S. generational cohorts across six life dimensions (cost of living,
//   housing, income, healthcare, jobs, retirement). Produces a signed score
//   (-100..+100), a confidence %, and a plain-English reason for each cohort.
// How it fits: Loaded as a deferred <script> in index.html; exposes
//   window.GenImpact for use by app.js and influenceweb.js when rendering
//   bill cards, politician drawers, company panels, and state views.

// genimpact.js
//
// What it does:
//   The Generation Impact engine (window.GenImpact). A reusable, heuristic
//   translation layer that estimates how a bill, company, sector, or state's
//   economic activity may land on each generation. It outputs per-generation
//   scores across 6 life dimensions plus an overall score, a confidence %, and
//   a plain-English reason.
//
// How it fits:
//   Used by app.js on the stock and bill pages to render the shared "Generation
//   Impact" view. Framing rule (non-negotiable): it describes likely exposure in
//   plain English, as estimates only, and never alleges intent or wrongdoing.
"use strict";
(function () {
  // The five generational cohorts ThinkFree tracks.
  const GENS = ["Gen Z", "Millennials", "Gen X", "Baby Boomers", "Retirees"];

  // Pairs of [dimensionKey, displayLabel] iterated in a stable order throughout
  // the module so every loop touches the same six dimensions consistently.
  const DIMS = [
    ["costOfLiving", "Cost of Living"],
    ["housing", "Housing"],
    ["income", "Income"],
    ["healthcare", "Healthcare"],
    ["jobs", "Job Market"],
    ["retirement", "Retirement"],
  ];

  // How exposed each generation is to each dimension (0..1). Drives both how
  // strongly a generation feels an effect and how the overall score is weighted.
  const GEN_WEIGHT = {
    "Gen Z":         { costOfLiving: 0.9, housing: 0.7, income: 0.8, healthcare: 0.3, jobs: 1.0, retirement: 0.1 },
    "Millennials":   { costOfLiving: 0.9, housing: 1.0, income: 0.9, healthcare: 0.5, jobs: 0.8, retirement: 0.3 },
    "Gen X":         { costOfLiving: 0.7, housing: 0.7, income: 0.9, healthcare: 0.6, jobs: 0.6, retirement: 0.7 },
    "Baby Boomers":  { costOfLiving: 0.6, housing: 0.3, income: 0.5, healthcare: 0.9, jobs: 0.2, retirement: 1.0 },
    "Retirees":      { costOfLiving: 0.7, housing: 0.2, income: 0.3, healthcare: 1.0, jobs: 0.05, retirement: 1.0 },
  };

  // Per-policy-area effect on each dimension for a typical bill/activity in
  // that area. Signed: negative = added pressure/cost on households,
  // positive = relief/benefit. Values -1..1. Keys are matched loosely against
  // sector / industry strings (see matchArea).
  const AREA = {
    "Real Estate":   { housing: -0.8, costOfLiving: -0.4, income: 0.1, retirement: 0.3 },
    "Housing":       { housing: -0.8, costOfLiving: -0.4, income: 0.1, retirement: 0.2 },
    "Financials":    { housing: -0.4, costOfLiving: -0.2, income: -0.2, retirement: -0.2 },
    "Consumer & Credit": { costOfLiving: -0.5, income: -0.3, housing: -0.2 },
    "Health Care":   { healthcare: -0.7, costOfLiving: -0.3, retirement: -0.4 },
    "Healthcare":    { healthcare: -0.7, costOfLiving: -0.3, retirement: -0.4 },
    "Pharmaceuticals": { healthcare: -0.8, costOfLiving: -0.2, retirement: -0.5 },
    "Energy":        { costOfLiving: -0.6, jobs: 0.3, income: 0.1, retirement: 0.2 },
    "Energy & Utilities": { costOfLiving: -0.6, jobs: 0.3, retirement: 0.2 },
    "Oil & Gas":     { costOfLiving: -0.5, jobs: 0.3, income: 0.1, retirement: 0.2 },
    "Utilities":     { costOfLiving: -0.5, retirement: -0.1 },
    "Technology":    { jobs: 0.4, income: 0.3, costOfLiving: 0.2, retirement: -0.1 },
    "Communication Services": { jobs: 0.2, income: 0.2, costOfLiving: 0.1 },
    "Industrials":   { jobs: 0.5, income: 0.3, costOfLiving: -0.1 },
    "Defense":       { jobs: 0.3, income: 0.2 },
    "Materials":     { jobs: 0.3, costOfLiving: -0.2 },
    "Consumer Staples": { costOfLiving: -0.4, income: -0.1 },
    "Consumer Discretionary": { costOfLiving: -0.2, jobs: 0.2, income: 0.1 },
    "Wages & Labor": { income: 0.6, jobs: 0.4, costOfLiving: 0.2 },
    "Taxes":         { income: -0.4, costOfLiving: -0.2, retirement: -0.2 },
    "Budget":        { income: 0.1, jobs: 0.2, healthcare: 0.1 },
    "Education":     { income: 0.4, jobs: 0.4, costOfLiving: -0.1 },
    "Benefits":      { income: 0.3, healthcare: 0.3, retirement: 0.5, costOfLiving: 0.2 },
    "Business":      { jobs: 0.4, income: 0.2 },
    "default":       { costOfLiving: -0.2, income: -0.1, housing: -0.1 },
  };

  // Plain-English reason templates keyed by dimension and direction.
  // Sentence fragments appended after the generation name (e.g. "Gen Z <harm>").
  const REASON_DIM = {
    housing: { harm: "are more likely to rent or be first-time buyers exposed to housing and mortgage costs",
               help: "could see some relief on housing and mortgage costs" },
    costOfLiving: { harm: "spend more of their income on everyday costs like food, gas, and utilities",
                    help: "could feel a little more breathing room in everyday costs" },
    income: { harm: "rely heavily on wage income that this could squeeze",
              help: "could benefit from stronger wage and income conditions" },
    healthcare: { harm: "depend more on healthcare and prescriptions, where costs hit hardest",
                  help: "could see healthcare or drug costs ease" },
    jobs: { harm: "are most sensitive to hiring slowdowns and a weaker job market",
            help: "could benefit from stronger hiring and job opportunities" },
    retirement: { harm: "rely on retirement savings and fixed income that this could pressure",
                  help: "could see retirement savings or fixed income hold up better" },
  };

  // Utility: clamp v to [lo, hi].
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  // map a free-form sector/industry/topic string to an AREA key
  function matchArea(s) {
    if (!s) return null;
    // Exact match first -- avoids substring collisions.
    if (AREA[s]) return s;
    const t = String(s).toLowerCase();
    const hit = (kw) => t.indexOf(kw) >= 0;
    if (hit("real estate") || hit("housing") || hit("mortgage") || hit("rent")) return "Real Estate";
    if (hit("pharma") || hit("drug") || hit("biotech")) return "Pharmaceuticals";
    if (hit("health")) return "Health Care";
    if (hit("oil") || hit("gas")) return "Oil & Gas";
    if (hit("util")) return "Utilities";
    if (hit("energy")) return "Energy";
    if (hit("bank") || hit("financ") || hit("credit") || hit("insur")) return "Financials";
    if (hit("tech") || hit("software") || hit("semiconduct") || hit("computer")) return "Technology";
    if (hit("commun") || hit("media") || hit("telecom")) return "Communication Services";
    if (hit("industr") || hit("manufact") || hit("aero")) return "Industrials";
    if (hit("defen")) return "Defense";
    if (hit("material") || hit("chemical") || hit("metal")) return "Materials";
    if (hit("staple") || hit("food") || hit("grocer")) return "Consumer Staples";
    if (hit("discretion") || hit("retail")) return "Consumer Discretionary";
    if (hit("wage") || hit("labor") || hit("employ")) return "Wages & Labor";
    if (hit("tax")) return "Taxes";
    if (hit("budget") || hit("appropriat")) return "Budget";
    if (hit("educat") || hit("school") || hit("student")) return "Education";
    if (hit("benefit") || hit("medicaid") || hit("snap") || hit("pension")) return "Benefits";
    return null;
  }

  // Core: given a list of area strings, compute the full generation matrix.
  // Each matched area contributes its signed dimension vector; effects are
  // averaged so adding more areas does not artificially amplify the result.
  function fromAreas(areas, opts) {
    opts = opts || {};
    const keys = (areas || []).map(matchArea).filter(Boolean);
    const used = keys.length ? keys : ["default"];

    // aggregate signed effect per dimension
    const eff = {}; DIMS.forEach(([d]) => (eff[d] = 0));
    used.forEach((k) => {
      const row = AREA[k] || AREA.default;
      DIMS.forEach(([d]) => (eff[d] += row[d] || 0));
    });
    DIMS.forEach(([d]) => (eff[d] /= used.length));

    // orientation: +1 helps households, -1 hurts. Bills can be flagged; default neutral pass-through.
    const orient = opts.orientation != null ? opts.orientation : 1;

    const gens = GENS.map((g) => {
      const w = GEN_WEIGHT[g];
      const dims = {};
      let wsum = 0, acc = 0;
      DIMS.forEach(([d]) => {
        // Scale by 110 so a full-magnitude effect saturates near 100 after
        // the generational weight is applied; clamp to [-100, 100].
        const score = clamp(Math.round(eff[d] * w[d] * 110 * orient), -100, 100);
        dims[d] = score;
        acc += score * w[d];
        wsum += w[d];
      });
      const overall = clamp(Math.round(acc / (wsum || 1)), -100, 100);

      // strongest-magnitude dimension drives the plain-English reason
      let topDim = "costOfLiving", topMag = -1;
      DIMS.forEach(([d]) => { if (Math.abs(dims[d]) > topMag) { topMag = Math.abs(dims[d]); topDim = d; } });
      const dir = overall < 0 ? "harm" : "help";
      const reason = `${g} ${REASON_DIM[topDim][dir]}.`;
      return { gen: g, overall, dims, reason };
    });

    // Confidence rises with each area successfully mapped; capped at 95.
    const matched = keys.length;
    const confidence = clamp(50 + matched * 12 + (opts.confidenceBoost || 0), 35, 95);
    return { gens, confidence, areas: used, matched };
  }

  // ---- public builders for each entity type ----

  // Thin wrapper: compute impact directly from an array of sector strings.
  function forSectors(sectors, opts) { return fromAreas(sectors, opts); }

  // Build impact for a legislative bill object, then attach bill metadata so
  // callers can render status badges, linked politicians, and tickers.
  function forBill(bill, opts) {
    if (!bill) return fromAreas([], opts);
    const areas = [].concat(bill.sectors || [], bill.topics || []);
    const res = fromAreas(areas, opts);
    res.status = billStatus(bill);
    res.title = bill.title || bill.bill_id || "";
    res.id = bill.bill_id || bill.number || "";
    res.politicians = (bill.politicians || []).slice(0, 8);
    res.companies = (bill.tickers || []).slice(0, 10);
    res.sectors = bill.sectors || [];
    return res;
  }

  // Build impact for a single company identified by ticker and industry.
  // Falls back to "default" area when no usable sector/industry is provided.
  function forCompany(ticker, industry, sectors, opts) {
    const areas = [].concat(sectors || [], industry ? [industry] : []);
    const res = fromAreas(areas.length ? areas : ["default"], opts);
    res.ticker = ticker;
    return res;
  }

  // state cost conditions -> generational pressure (uses ThinkFree state scores)
  // Translates raw state economic statistics into the same signed dimension
  // vector format used by fromAreas, then runs the generation weighting pass.
  function forState(s, opts) {
    if (!s) return fromAreas([], opts);
    const pressure = s.pressure_score || 0, afford = s.affordability != null ? s.affordability : 50;
    const infl = s.inflation != null ? s.inflation : 2.5, unemp = s.unemployment != null ? s.unemployment : 4;

    // synthesize a signed dimension vector directly from real state stats
    const eff = {
      costOfLiving: clamp(-((pressure - 40) / 60), -1, 0.4),
      housing: clamp(-((60 - afford) / 60), -1, 0.4),
      income: clamp((s.income_growth || 0) / 6, -1, 1),
      healthcare: clamp(-(infl - 2) / 6, -1, 0.3),
      jobs: clamp((4.5 - unemp) / 4, -1, 1),
      retirement: clamp(-(infl - 2) / 8, -1, 0.3),
    };
    const gens = GENS.map((g) => {
      const w = GEN_WEIGHT[g]; const dims = {}; let wsum = 0, acc = 0;
      DIMS.forEach(([d]) => { const sc = clamp(Math.round(eff[d] * w[d] * 110), -100, 100); dims[d] = sc; acc += sc * w[d]; wsum += w[d]; });
      const overall = clamp(Math.round(acc / (wsum || 1)), -100, 100);
      let topDim = "costOfLiving", topMag = -1;
      DIMS.forEach(([d]) => { if (Math.abs(dims[d]) > topMag) { topMag = Math.abs(dims[d]); topDim = d; } });
      const reason = `${g} ${REASON_DIM[topDim][overall < 0 ? "harm" : "help"]}.`;
      return { gen: g, overall, dims, reason };
    });
    return { gens, confidence: 70, areas: ["state-conditions"], matched: 1, state: s.name };
  }

  // Derive a canonical bill status string from whatever text the data source
  // provides (status field or action_text). Returns "Passed", "Failed", or "Proposed".
  function billStatus(bill) {
    const s = (bill.status || bill.action_text || "").toString().toLowerCase();
    if (s.indexOf("became") >= 0 || s.indexOf("enacted") >= 0 || s.indexOf("passed") >= 0 || s.indexOf("signed") >= 0) return "Passed";
    if (s.indexOf("fail") >= 0 || s.indexOf("vetoed") >= 0 || s.indexOf("dead") >= 0) return "Failed";
    return "Proposed";
  }

  // Render helpers: each returns an HTML string, styled by the .gi-* CSS rules.

  // HTML-escape helper used before inserting any dynamic value into markup.
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Score-to-color mapping: red for harm, green for benefit, gray for neutral.
  const col = (v) => v < -8 ? "#EF4444" : v > 8 ? "#22C55E" : "#94A3B8";

  // Prepend "+" for positive values so the sign is always explicit in the UI.
  const sign = (v) => (v > 0 ? "+" : "") + v;

  // build the ScoreInfo explainer payload for one generation's impact score
  function siGen(g, res) {
    const ds = DIMS.map(([d, label]) => ({ label, v: g.dims[d] })).sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
    const bl = [g.reason];
    ds.slice(0, 2).forEach((x) => { if (x.v) bl.push(`${x.label}: ${x.v > 0 ? "+" : ""}${x.v}`); });
    return {
      title: g.gen + " - Generation Impact", value: (g.overall > 0 ? "+" : "") + g.overall,
      bullets: bl.slice(0, 4), why: g.reason,
      contributors: ds.map((x) => ({ label: x.label, detail: (x.v > 0 ? "+" : "") + x.v })),
      calc: {
        formula: "Per-generation impact = average policy-area effect x that generation's exposure to each life dimension (cost of living, housing, income, healthcare, jobs, retirement), weighted by exposure.",
        rows: ds.map((x) => ({ factor: x.label, value: (x.v > 0 ? "+" : "") + x.v })), total: (g.overall > 0 ? "+" : "") + g.overall,
      },
      sources: [{ label: "Policy areas analyzed: " + (res.areas || []).join(", ") }],
    };
  }

  // Render a horizontal bar chart (one row per generation) as an HTML string.
  // When window.ScoreInfo is available, scores become clickable info chips.
  function bars(res, opts) {
    opts = opts || {};
    const rows = res.gens.map((g) => {
      const c = col(g.overall), w = Math.min(100, Math.abs(g.overall) * 1.1);
      const num = window.ScoreInfo
        ? `<span class="si" data-si-payload="${E(JSON.stringify(siGen(g, res)))}" tabindex="0">${sign(g.overall)}<i class="si-i">&#9432;</i></span>`
        : sign(g.overall);
      return `<div class="gimp-row">
        <div class="gimp-row-head"><span class="gimp-gen">${E(g.gen)}</span><b style="color:${c}">${num}</b></div>
        <div class="gimp-track"><div class="gimp-fill" style="width:${w}%;background:${c};${g.overall < 0 ? "" : "margin-left:auto"}"></div></div>
        ${opts.reasons ? `<div class="gimp-note">${E(g.reason)}</div>` : ""}
      </div>`;
    }).join("");
    return `<div class="gimp-bars">${rows}</div>`;
  }

  // Render a confidence badge. Uses ScoreInfo chip when available so users can
  // read an explanation of how the confidence figure was calculated.
  function confBadge(res) {
    if (!window.ScoreInfo) return `${res.confidence}% confidence`;
    const payload = {
      title: "Confidence", value: res.confidence + "%",
      bullets: ["Based on " + res.matched + " mapped policy area(s)", res.matched >= 3 ? "Strong signal" : "Limited signal"],
      why: "Confidence reflects how many of the source record's policy areas we could map to known generational exposures. More mapped areas means a more reliable estimate.",
      contributors: [{ label: "Mapped policy areas", detail: String(res.matched) }],
      sources: [{ label: "Sector and topic tags on the source record" }],
    };
    return `<span class="si" data-si-payload="${E(JSON.stringify(payload))}" tabindex="0">${res.confidence}% confidence<i class="si-i">&#9432;</i></span>`;
  }

  // detailed per-dimension grid for the strongest-affected generation
  function dimGrid(res) {
    // detailed per-dimension grid for the strongest-affected generation
    const lead = res.gens.slice().sort((a, b) => Math.abs(b.overall) - Math.abs(a.overall))[0];
    if (!lead) return "";
    const cells = DIMS.map(([d, label]) => {
      const v = lead.dims[d];
      return `<div class="gimp-dim"><span>${E(label)}</span><b style="color:${col(v)}">${sign(v)}</b></div>`;
    }).join("");
    return `<div class="gimp-dim-head">Most affected: <b>${E(lead.gen)}</b> · detail</div><div class="gimp-dim-grid">${cells}</div>`;
  }

  // Assemble a full Generation Impact panel: header, bar chart, optional
  // dimension grid, confidence line, and the non-partisan disclaimer footer.
  function panel(res, opts) {
    opts = opts || {};
    const status = res.status ? `<span class="gimp-status gimp-${res.status.toLowerCase()}">${E(res.status)}</span>` : "";
    const head = opts.title
      ? `<div class="gimp-head"><span class="gimp-eyebrow">Generation Impact</span>${status}</div><div class="gimp-title">${E(opts.title)}</div>`
      : `<div class="gimp-head"><span class="gimp-eyebrow">Generation Impact</span>${status}<span class="gimp-conf">${confBadge(res)}</span></div>`;
    const conf = opts.title ? `<div class="gimp-conf-line">${res.confidence}% confidence · estimate</div>` : "";
    return `<div class="gimp-panel">${head}${bars(res, { reasons: opts.reasons !== false })}${opts.dims ? dimGrid(res) : ""}${conf}
      <div class="gimp-foot">Estimate of likely exposure by generation. Plain-English, non-partisan; does not imply wrongdoing.</div></div>`;
  }

  // Publish the public API on window so any module can call GenImpact.forBill(),
  // GenImpact.panel(), etc. without importing a module system.
  window.GenImpact = {
    GENS, DIMS,
    forSectors, forBill, forCompany, forState, billStatus,
    bars, dimGrid, panel,
  };
})();
