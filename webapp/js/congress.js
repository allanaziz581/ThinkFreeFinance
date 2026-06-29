// congress.js
// What it does: Renders the U.S. Congress drill-down panel inside the InfluenceWeb overlay.
//   Provides three sub-views -- House constellation, Senate constellation, and Governors tile/SVG map --
//   plus a Generation Impact overlay that scores how a bill's sectors land on each age cohort.
//   Per-member "funding influence" hover cards surface FEC receipt breakdowns (individual vs. PAC vs. other).
// How it fits: Mounted by CongressDrill.open() (called from influenceweb.js when the user clicks the
//   Congress node). Reads window.TF_DATA, window.FEC_DATA, window.STATES_DATA, and window.MEMBER_BILLS.
//   Delegates to window.GenImpact (generation-impact module) and window.ScoreInfo (badge renderer) when
//   those modules are present. Framing is transparency, not accusation.
"use strict";

(function () {
  // Pull shared data bundles off the global window namespace.
  // All are optional; missing data degrades gracefully to empty arrays / fallback text.
  const D = window.TF_DATA || {};
  const FEC = (window.FEC_DATA || {}).byName || {};
  const STATES = (window.STATES_DATA || {}).byState || {};
  const MB = (window.MEMBER_BILLS || {}).byBioguide || {};   // real Congress.gov sponsored/cosponsored counts

  // Escape a value for safe HTML insertion.
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // Render a score value, optionally wrapped in a ScoreInfo badge with hover/tap explanation.
  const SB = (k, key, v) => window.ScoreInfo ? window.ScoreInfo.badge(k, key, v) : String(v);   // score w/ hover/tap explainer

  // Map party abbreviation to a CSS color used throughout all views.
  const PARTY_COLOR = (ab) => ab === "R" ? "#EF4444" : ab === "D" ? "#38BDF8" : ab === "L" ? "#22C55E" : "#94A3B8";
  // Map party abbreviation to its full display name.
  const PARTY_NAME = (ab) => ab === "R" ? "Republican" : ab === "D" ? "Democrat" : ab === "L" ? "Libertarian" : "Independent";

  // Current U.S. governors (reference data, 2025): state abbreviation -> [name, party abbreviation].
  const GOVERNORS = {
    AL: ["Kay Ivey", "R"], AK: ["Mike Dunleavy", "R"], AZ: ["Katie Hobbs", "D"], AR: ["Sarah Huckabee Sanders", "R"],
    CA: ["Gavin Newsom", "D"], CO: ["Jared Polis", "D"], CT: ["Ned Lamont", "D"], DE: ["Matt Meyer", "D"],
    FL: ["Ron DeSantis", "R"], GA: ["Brian Kemp", "R"], HI: ["Josh Green", "D"], ID: ["Brad Little", "R"],
    IL: ["JB Pritzker", "D"], IN: ["Mike Braun", "R"], IA: ["Kim Reynolds", "R"], KS: ["Laura Kelly", "D"],
    KY: ["Andy Beshear", "D"], LA: ["Jeff Landry", "R"], ME: ["Janet Mills", "D"], MD: ["Wes Moore", "D"],
    MA: ["Maura Healey", "D"], MI: ["Gretchen Whitmer", "D"], MN: ["Tim Walz", "D"], MS: ["Tate Reeves", "R"],
    MO: ["Mike Kehoe", "R"], MT: ["Greg Gianforte", "R"], NE: ["Jim Pillen", "R"], NV: ["Joe Lombardo", "R"],
    NH: ["Kelly Ayotte", "R"], NJ: ["Mikie Sherrill", "D"], NM: ["Michelle Lujan Grisham", "D"], NY: ["Kathy Hochul", "D"],
    NC: ["Josh Stein", "D"], ND: ["Kelly Armstrong", "R"], OH: ["Mike DeWine", "R"], OK: ["Kevin Stitt", "R"],
    OR: ["Tina Kotek", "D"], PA: ["Josh Shapiro", "D"], RI: ["Dan McKee", "D"], SC: ["Henry McMaster", "R"],
    SD: ["Larry Rhoden", "R"], TN: ["Bill Lee", "R"], TX: ["Greg Abbott", "R"], UT: ["Spencer Cox", "R"],
    VT: ["Phil Scott", "R"], VA: ["Abigail Spanberger", "D"], WA: ["Bob Ferguson", "D"], WV: ["Patrick Morrisey", "R"],
    WI: ["Tony Evers", "D"], WY: ["Mark Gordon", "R"],
  };

  // Tile cartogram positions [row, col] for a clean map-like grid.
  // Used as a fallback when window.US_MAP_PATHS is not available.
  const TILE = {
    AK: [0, 0], ME: [0, 11], WI: [1, 6], VT: [1, 10], NH: [1, 11],
    WA: [2, 1], ID: [2, 2], MT: [2, 3], ND: [2, 4], MN: [2, 5], IL: [2, 6], MI: [2, 7], NY: [2, 9], MA: [2, 10], RI: [2, 11],
    OR: [3, 1], NV: [3, 2], WY: [3, 3], SD: [3, 4], IA: [3, 5], IN: [3, 6], OH: [3, 7], PA: [3, 8], NJ: [3, 9], CT: [3, 10],
    CA: [4, 1], UT: [4, 2], CO: [4, 3], NE: [4, 4], MO: [4, 5], KY: [4, 6], WV: [4, 7], VA: [4, 8], MD: [4, 9], DE: [4, 10],
    AZ: [5, 2], NM: [5, 3], KS: [5, 4], AR: [5, 5], TN: [5, 6], NC: [5, 7], SC: [5, 8], DC: [5, 9],
    OK: [6, 4], LA: [6, 5], MS: [6, 6], AL: [6, 7], GA: [6, 8],
    HI: [7, 1], TX: [7, 4], FL: [7, 9],
  };

  // Compute funding breakdown percentages from FEC receipts for a given politician name.
  // Returns null when no FEC record exists so callers can show a "no data" notice.
  function funding(name) {
    const f = FEC[name];
    if (!f || !f.receipts) return null;
    const total = f.receipts || 1;
    const ind = Math.round((f.from_individuals || 0) / total * 100);
    const pac = Math.round((f.from_pacs || 0) / total * 100);
    const other = Math.max(0, 100 - ind - pac);
    return { individual: ind, pac, other, total_fmt: f.receipts_fmt, raised: f.receipts };
  }

  // Derive simple 0-100 scores from real signals (trades, PAC share, return).
  // These drive the Influence / Transparency / Public Impact badges in hover cards.
  function scores(p) {
    const f = funding(p.name);
    const pacShare = f ? f.pac : 0;
    const influence = Math.round(Math.min(100, 30 + (p.trades || 0) * 0.3 + pacShare * 0.6 + Math.abs(p.ret || 0) * 0.5));
    const transparency = Math.round(Math.max(5, 100 - pacShare * 1.4 - (p.trades || 0) * 0.15));
    const publicImpact = Math.round(Math.max(10, 70 - pacShare * 0.5 + (f ? f.individual : 0) * 0.2));
    return { influence, transparency, publicImpact, exposure: pacShare };
  }

  // Generation cohorts used throughout the generation-impact overlay.
  const GENS = ["Gen Z", "Millennials", "Gen X", "Baby Boomers", "Retirees"];

  // Per-sector sensitivity weights for each generation.
  // Positive values indicate a policy area tends to benefit that cohort;
  // negative values indicate likely harm. Scale is roughly -1..+1.
  const SECTOR_GEN = {
    "Real Estate": { "Gen Z": -0.7, "Millennials": -0.9, "Gen X": -0.4, "Baby Boomers": 0.3, "Retirees": 0.4 },
    "Financials": { "Gen Z": -0.4, "Millennials": -0.6, "Gen X": -0.3, "Baby Boomers": 0.1, "Retirees": -0.2 },
    "Health Care": { "Gen Z": -0.1, "Millennials": -0.2, "Gen X": -0.3, "Baby Boomers": -0.6, "Retirees": -0.8 },
    "Pharmaceuticals": { "Gen Z": -0.1, "Millennials": -0.2, "Gen X": -0.3, "Baby Boomers": -0.6, "Retirees": -0.8 },
    "Energy": { "Gen Z": -0.5, "Millennials": -0.5, "Gen X": -0.4, "Baby Boomers": -0.3, "Retirees": -0.3 },
    "Oil & Gas": { "Gen Z": -0.5, "Millennials": -0.4, "Gen X": -0.3, "Baby Boomers": -0.2, "Retirees": -0.2 },
    "Technology": { "Gen Z": 0.3, "Millennials": 0.2, "Gen X": 0.0, "Baby Boomers": -0.1, "Retirees": -0.2 },
    "default": { "Gen Z": -0.2, "Millennials": -0.3, "Gen X": -0.2, "Baby Boomers": -0.2, "Retirees": -0.2 },
  };

  // Plain-English reason strings displayed alongside each generation's impact score.
  const GEN_REASON = {
    "Millennials": "more likely to be first-time homebuyers and exposed to high mortgage rates",
    "Gen Z": "early in their careers, renting, and most sensitive to job-market and cost-of-living shifts",
    "Gen X": "balancing mortgages, raising kids, and saving for retirement at the same time",
    "Baby Boomers": "nearing or in retirement and more reliant on healthcare and fixed income",
    "Retirees": "on fixed incomes and most exposed to healthcare and drug-pricing changes",
  };

  // Compute a per-generation impact score (-70..+70) for a given bill by averaging
  // the sector weights that apply to it. Falls back to the "default" sector row when
  // the bill has no recognised sectors.
  function billGenerationImpact(bill) {
    const secs = (bill && bill.sectors) || [];
    const w = {};
    GENS.forEach((g) => (w[g] = 0));
    const sets = secs.length ? secs : ["default"];
    sets.forEach((s) => {
      const row = SECTOR_GEN[s] || SECTOR_GEN.default;
      GENS.forEach((g) => (w[g] += row[g] || 0));
    });
    return GENS.map((g) => {
      const score = Math.round((w[g] / sets.length) * 70); // -70..+70
      return { gen: g, score, reason: GEN_REASON[g] };
    });
  }

  // Overlay host element management.
  // `host` is the #iw-drill panel; all views are rendered into it via show().
  let host;
  function ensureHost() {
    host = document.getElementById("iw-drill");
    if (!host) return null;
    return host;
  }
  function show(html) { ensureHost(); host.innerHTML = html; host.classList.add("open"); host.scrollTop = 0; }
  function close() { if (host) host.classList.remove("open"); if (window.IW && window.IW.resetView) window.IW.resetView(); }

  // Level 1: three-module selector (House / Senate / Governors / Generation Impact).
  function modulesView() {
    const house = (D.politicians || []).filter((p) => (p.chamber || "").toLowerCase().startsWith("h"));
    const senate = (D.politicians || []).filter((p) => (p.chamber || "").toLowerCase().startsWith("s"));
    show(`
      <button class="iw-drill-close" data-dc="x">&times;</button>
      <div class="cd-head"><div class="iw-eyebrow">U.S. Congress</div><h2>Branches of Power</h2>
        <p class="cd-sub">Click a module to explore the people, money, and impact behind it.</p></div>
      <div class="cd-modules">
        <div class="cd-module" data-dc="house">
          <div class="cd-mod-ico" style="--c:#38BDF8">${ICON.house}</div>
          <div class="cd-mod-name">House of Representatives</div>
          <div class="cd-mod-count">435 members${house.length ? " · " + house.length + " tracked" : ""}</div>
          <div class="cd-mod-desc">Trade, lobbying, PAC, and public impact data</div>
        </div>
        <div class="cd-module" data-dc="senate">
          <div class="cd-mod-ico" style="--c:#A855F7">${ICON.senate}</div>
          <div class="cd-mod-name">Senate / Congress</div>
          <div class="cd-mod-count">100 senators${senate.length ? " · " + senate.length + " tracked" : ""}</div>
          <div class="cd-mod-desc">Legislation, lobbying, industry exposure, voting impact</div>
        </div>
        <div class="cd-module" data-dc="gov">
          <div class="cd-mod-ico" style="--c:#E9C46A">${ICON.gov}</div>
          <div class="cd-mod-name">Governors</div>
          <div class="cd-mod-count">50 states</div>
          <div class="cd-mod-desc">State leadership, cost of living, Census data, state impact</div>
        </div>
        <div class="cd-module" data-dc="gen">
          <div class="cd-mod-ico" style="--c:#22C55E">${ICON.gen}</div>
          <div class="cd-mod-name">Generation Impact</div>
          <div class="cd-mod-count">5 age groups</div>
          <div class="cd-mod-desc">How passed and proposed legislation lands on Gen Z to Retirees</div>
        </div>
      </div>
      <div class="cd-foot">${E(D.disclaimer || "Describes timing and funding relationships from public data. Does not imply wrongdoing.")}</div>`);
  }

  // Level 2: House or Senate member constellation.
  // Dots are scatter-plotted using a golden-angle spiral so members distribute evenly
  // without overlapping. Party color encodes affiliation at a glance.
  function constellation(kind) {
    const isHouse = kind === "house";
    let people = (D.politicians || []).filter((p) => {
      const c = (p.chamber || "").toLowerCase();
      // House matches "house"/"rep"/"representative"; Senate matches "senate"/"sen".
      return isHouse ? (c.startsWith("h") || c.startsWith("rep")) : (c.startsWith("s"));
    });
    if (!people.length) people = (D.politicians || []); // fallback: show all tracked
    // Scatter dots organically inside a circle using the golden-angle spiral.
    const dots = people.map((p, i) => {
      const ang = (i * 137.5) * Math.PI / 180;          // golden-angle scatter
      const r = 6 + 40 * Math.sqrt(i / people.length);  // 6%..46% radius
      const x = 50 + Math.cos(ang) * r, y = 50 + Math.sin(ang) * r;
      return `<span class="cd-dot" data-dc="poldot" data-name="${E(p.name)}"
        style="left:${x.toFixed(2)}%;top:${y.toFixed(2)}%;background:${PARTY_COLOR(p.party_abbr)};box-shadow:0 0 8px ${PARTY_COLOR(p.party_abbr)}"
        title="${E(p.name)}"></span>`;
    }).join("");
    const counts = people.reduce((m, p) => { m[p.party_abbr] = (m[p.party_abbr] || 0) + 1; return m; }, {});
    show(`
      <button class="iw-drill-close" data-dc="x">&times;</button>
      <div class="cd-head"><div class="iw-back" data-dc="modules">&lsaquo; Back to Congress</div>
        <h2>${isHouse ? "House of Representatives" : "Senate / Congress"}</h2>
        <p class="cd-sub">${people.length} tracked members. Hover a dot for funding influence, then Expand for the full breakdown.</p></div>
      <div class="cd-legend">
        <span><i style="background:#EF4444"></i>Republican ${counts.R || 0}</span>
        <span><i style="background:#38BDF8"></i>Democrat ${counts.D || 0}</span>
        <span><i style="background:#94A3B8"></i>Independent ${counts.I || 0}</span>
        <span><i style="background:#22C55E"></i>Other ${counts.L || 0}</span>
      </div>
      <div class="cd-constellation" id="cd-const">${dots}<div class="cd-ring"></div></div>
      <div class="cd-hovercard" id="cd-hover"></div>`);
  }

  // Build an SVG pie chart representing the three funding categories.
  // When only one non-zero segment exists, renders a plain filled circle to avoid
  // degenerate arc math. `size` defaults to 40px.
  function fundingPie(f, size) {
    if (!f) return "";
    size = size || 40; const c = size / 2, rad = size / 2 - 2;
    const segs = [[f.individual, "#22C55E"], [f.pac, "#EF4444"], [f.other, "#64748B"]];
    const nonzero = segs.filter((s) => s[0] > 0);
    if (nonzero.length === 1) return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="cd-pie"><circle cx="${c}" cy="${c}" r="${rad}" fill="${nonzero[0][1]}"/></svg>`;
    let a0 = -Math.PI / 2, paths = "";
    segs.forEach(([v, col]) => {
      if (!v) return;
      const a1 = a0 + (v / 100) * Math.PI * 2;
      const x0 = c + rad * Math.cos(a0), y0 = c + rad * Math.sin(a0);
      const x1 = c + rad * Math.cos(a1), y1 = c + rad * Math.sin(a1);
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      paths += `<path d="M${c},${c} L${x0.toFixed(1)},${y0.toFixed(1)} A${rad},${rad} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z" fill="${col}"/>`;
      a0 = a1;
    });
    return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="cd-pie">${paths}</svg>`;
  }

  // Track the currently pinned hover card so expand/collapse can refresh it in place.
  let curPolName = null, curDotEl = null;

  // Render the politician hover card anchored near dotEl.
  // `big` switches between a compact summary (false) and the full funding breakdown (true).
  function hoverCard(name, dotEl, big) {
    const p = (D.politicians || []).find((x) => x.name === name);
    if (!p) return;
    curPolName = name; if (dotEl) curDotEl = dotEl;
    const sc = scores(p), f = funding(name);
    const tickers = (p.top_tickers || []).slice(0, 6);
    const leg = MB[p.bioguide] || {};
    const legTotal = leg.total != null ? leg.total : (p.related_bills || []).length;
    const supporters = (p.supporters || []).slice(0, 6);
    const donors = (p.donors || []).slice(0, 6);
    // Derive a plain-English funding note based on the PAC share threshold.
    const fundNote = !f ? "No FEC funding data on record."
      : f.pac >= 40 ? "Potential influence concentration: high outside-funding exposure."
      : f.pac >= 20 ? "Moderate industry-linked support." : "Largely individually funded.";
    const card = document.getElementById("cd-hover");
    if (!card) return;

    // Compact view: small pie, activity summary, top tickers.
    const collapsed = `
      ${f ? `<div class="cd-hc-fund">
        <div class="cd-hc-fund-label">Funding Influence Breakdown</div>
        <div class="cd-hc-fund-row">${fundingPie(f, 42)}
          <div class="cd-hc-fund-list">
            <div><i style="background:#22C55E"></i>Individual ${f.individual}%</div>
            <div><i style="background:#EF4444"></i>PACs &amp; committees ${f.pac}%</div>
            <div><i style="background:#64748B"></i>Other ${f.other}%</div>
          </div></div></div>` : `<div class="cd-hc-note">No FEC funding data on record.</div>`}
      <div class="cd-hc-activity">
        <span><b>${p.trades || 0}</b> trades</span>
        <span><b>${legTotal}</b> bills</span>
        <span><b>${(p.ret != null ? (p.ret > 0 ? "+" : "") + p.ret + "%" : "n/a")}</b> return</span>
      </div>
      ${tickers.length ? `<div class="cd-hc-tickers">${tickers.map((t) => `<span class="cd-hc-tk">${E(t.ticker)}</span>`).join("")}</div>` : ""}`;

    // Expanded view: large pie, itemised supporters, top donors, disclaimer footer.
    const expanded = `
      ${f ? `<div class="cd-hc-fund">
        <div class="cd-hc-fund-label">Funding Influence Breakdown</div>
        <div class="cd-hc-fund-big">${fundingPie(f, 104)}
          <div class="cd-hc-fund-list">
            <div><i style="background:#22C55E"></i>Individual donations <b>${f.individual}%</b></div>
            <div><i style="background:#EF4444"></i>PACs &amp; committees <b>${f.pac}%</b></div>
            <div><i style="background:#64748B"></i>Other <b>${f.other}%</b></div>
            <div class="cd-hc-raised">Total raised ${E(f.total_fmt || "")}</div>
          </div></div>
        <div class="cd-hc-note">${E(fundNote)}</div></div>` : `<div class="cd-hc-note">No FEC funding data on record.</div>`}
      ${leg.total != null ? `<div class="cd-hc-fund-label">Legislative Activity (career total)</div>
      <div class="cd-hc-list"><div><span>Bills sponsored</span><b>${leg.sponsored}</b></div><div><span>Bills cosponsored</span><b>${leg.cosponsored}</b></div></div>` : ""}
      <div class="cd-hc-fund-label">PACs &amp; Outside Spending</div>
      <div class="cd-hc-list">${supporters.length ? supporters.map((s) => `<div><span>${E(s.org)}</span><b>${E(s.amount_fmt || "")}</b></div>`).join("") : `<div class="cd-hc-empty">No outside spending on record.</div>`}</div>
      <div class="cd-hc-fund-label">Top Donors &amp; Industries</div>
      <div class="cd-hc-list">${donors.length ? donors.map((d) => `<div><span>${E(d.org)} ${d.industry ? `<i class="cd-hc-ind">${E(d.industry)}</i>` : ""}</span><b>${E(d.amount_fmt || "")}</b></div>`).join("") : `<div class="cd-hc-empty">No itemized donors on record.</div>`}</div>
      <div class="cd-hc-foot">Funding influence breakdown from FEC and OpenSecrets-style disclosures. Describes outside-funding exposure; does not imply wrongdoing.</div>`;

    card.innerHTML = `
      <button class="cd-hc-x" data-dc="hclose" title="Close">&times;</button>
      <div class="cd-hc-top">
        <div><div class="cd-hc-name">${E(p.name)}</div>
        <div class="cd-hc-meta">${E(p.state || "")} · ${E(PARTY_NAME(p.party_abbr))} · ${E(p.chamber || "House")}</div></div>
        <span class="cd-hc-party" style="background:${PARTY_COLOR(p.party_abbr)}"></span>
      </div>
      <div class="cd-hc-scores">
        <div><span>Influence</span><b>${SB("pol-influence", p.name, sc.influence)}</b></div>
        <div><span>Public Impact</span><b>${SB("pol-public", p.name, sc.publicImpact)}</b></div>
        <div><span>Transparency</span><b>${SB("pol-transparency", p.name, sc.transparency)}</b></div>
      </div>
      ${big ? expanded : collapsed}
      <div class="cd-hc-btns">
        ${big ? `<button data-dc="hcollapse">&lsaquo; Less</button>` : `<button data-dc="hexpand" data-name="${E(name)}">Expand breakdown &rsaquo;</button>`}
        <button class="cd-hc-primary" data-dc="pol" data-name="${E(name)}">View full profile</button>
      </div>`;
    card.classList.toggle("big", !!big);
    card.classList.add("open");
    placeCard(dotEl || curDotEl);
  }

  // Position the hover card so it stays inside the drill panel.
  // Flips to the left of the dot when the right side would overflow.
  function placeCard(dotEl) {
    const host = document.getElementById("iw-drill"), card = document.getElementById("cd-hover");
    if (!host || !card) return;
    const hr = host.getBoundingClientRect();
    const cw = card.offsetWidth || 280, ch = card.offsetHeight || 240;
    let x, y;
    if (dotEl) {
      const dr = dotEl.getBoundingClientRect();
      x = dr.right - hr.left + 14; y = dr.top - hr.top - 12;
      if (x + cw > hr.width - 8) x = dr.left - hr.left - cw - 14; // flip to left
    } else { x = hr.width - cw - 16; y = 80; }
    x = Math.max(8, Math.min(x, hr.width - cw - 8));
    y = Math.max(8, Math.min(y, hr.height - ch - 8));
    card.style.left = x + "px"; card.style.top = y + "px";
  }

  // Hide the hover card and clear the pinned politician reference.
  function hideHover() { const c = document.getElementById("cd-hover"); if (c) { c.classList.remove("open", "big"); } curPolName = null; }

  // Level 2: Governors view with an SVG choropleth map (or tile cartogram fallback).
  // Pan and zoom state is stored in mapTf; mapMoved prevents click from firing after drag.
  let mapTf = { x: 0, y: 0, s: 1 }, mapMoved = false;

  // Apply the current pan/zoom transform to the SVG group element.
  function applyMapTf() {
    const g = document.getElementById("cd-map-g");
    if (g) g.setAttribute("transform", `translate(${mapTf.x} ${mapTf.y}) scale(${mapTf.s})`);
  }

  // Count governors of a given party abbreviation for the legend.
  function partyCount(ab) { return Object.values(GOVERNORS).filter((g) => g[1] === ab).length; }

  // Render the Governors panel. Prefers SVG paths from window.US_MAP_PATHS;
  // falls back to a CSS grid tile cartogram when path data is absent.
  function governorsView() {
    mapTf = { x: 0, y: 0, s: 1 };
    const PATHS = window.US_MAP_PATHS || {};
    const vb = window.US_MAP_VIEWBOX || "174 100 959 593";
    const shapes = Object.keys(GOVERNORS).map((st) => {
      const d = PATHS[st]; if (!d) return "";
      const c = PARTY_COLOR(GOVERNORS[st][1]);
      return `<path class="cd-state-path" data-dc="state" data-st="${st}" d="${d}" style="fill:${c}33;stroke:${c}"></path>`;
    }).join("");
    const fallback = !Object.keys(PATHS).length;
    const body = fallback
      ? `<div class="cd-usmap">${Object.entries(TILE).map(([st, [r, cc]]) => { const c = PARTY_COLOR((GOVERNORS[st] || ["", "I"])[1]); return `<div class="cd-state" data-dc="state" data-st="${st}" style="grid-row:${r + 1};grid-column:${cc + 1};border-color:${c}"><span>${st}</span></div>`; }).join("")}</div>`
      : `<div class="cd-map-wrap" id="cd-map-wrap">
          <svg class="cd-usmap-svg" id="cd-usmap-svg" viewBox="${vb}" preserveAspectRatio="xMidYMid meet"><g id="cd-map-g">${shapes}</g></svg>
          <div class="cd-map-zoom"><button data-dc="zin" title="Zoom in">+</button><button data-dc="zout" title="Zoom out">&minus;</button><button data-dc="zfit" title="Reset">&#9974;</button></div>
        </div>`;
    show(`
      <button class="iw-drill-close" data-dc="x">&times;</button>
      <div class="cd-head"><div class="iw-back" data-dc="modules">&lsaquo; Back to Congress</div>
        <h2>Governors</h2><p class="cd-sub">Hover a state for its governor and Census economics. Click for detail. Scroll or use +/&minus; to zoom, drag to pan.</p></div>
      <div class="cd-legend">
        <span><i style="background:#EF4444"></i>Republican ${partyCount("R")}</span>
        <span><i style="background:#38BDF8"></i>Democrat ${partyCount("D")}</span>
        <span><i style="background:#94A3B8"></i>Independent ${partyCount("I")}</span>
      </div>
      ${body}
      <div class="cd-hovercard" id="cd-hover"></div>`);
  }

  // Show a transient tooltip card with Census economics for the hovered state.
  // Positioned relative to the mouse cursor, clamped inside the drill panel.
  function stateHover(st, ev) {
    const g = GOVERNORS[st] || ["Unknown", "I"];
    const s = STATES[st] || {};
    const card = document.getElementById("cd-hover");
    const m0 = (v, suf = "") => v == null ? "&mdash;" : v + suf;
    card.innerHTML = `
      <div class="cd-hc-name">${E(s.name || st)}</div>
      <div class="cd-hc-meta">Governor: ${E(g[0])} · ${E(PARTY_NAME(g[1]))}</div>
      <div class="cd-hc-grid">
        <div><span>Cost of Living</span><b style="color:${(s.cost_of_living||0)>110?"var(--danger)":(s.cost_of_living||0)>100?"var(--warning)":(s.cost_of_living||0)>90?"var(--info)":"var(--success)"}">${m0(Math.min(100, Math.round(s.cost_of_living||0)))}</b></div>
        <div><span>Median Income</span><b>${s.median_household_income ? "$" + Math.round(s.median_household_income).toLocaleString() : "n/a"}</b></div>
        <div><span>Poverty</span><b>${m0(s.poverty_rate, "%")}</b></div>
        <div><span>Unemployment</span><b>${m0(s.unemployment, "%")}</b></div>
        <div><span>Inflation</span><b>${m0(s.inflation, "%")}</b></div>
        <div><span>Affordability</span><b>${m0(s.affordability)}</b></div>
      </div>
      <div class="cd-hc-impact">
        <span class="${(s.pressure_score || 0) >= 50 ? "bad" : "ok"}">Cost Pressure: ${(s.pressure_score || 0) >= 50 ? "High" : "Moderate"}</span>
        <span class="${(s.prosperity_score || 0) >= 50 ? "ok" : "bad"}">Prosperity: ${s.prosperity_score || 0}/100</span>
      </div>`;
    const r = document.getElementById("iw-drill").getBoundingClientRect();
    let x = ev.clientX - r.left + 16, y = ev.clientY - r.top + 16;
    x = Math.min(x, r.width - 280); y = Math.min(y, r.height - 200);
    card.style.left = x + "px"; card.style.top = y + "px"; card.classList.add("open");
  }

  // Generation impact overlay tied to a specific bill.
  // Delegates to window.GenImpact when available; falls back to the local
  // billGenerationImpact() calculation otherwise.
  function generationView(billId) {
    const bills = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])];
    const bill = bills.find((b) => b.bill_id === billId) || bills[0];
    const GI = window.GenImpact;
    let impactHtml, status = "Proposed", pols = [], cos = [], secs = [];
    if (GI && bill) {
      const res = GI.forBill(bill);
      status = res.status || "Proposed"; pols = res.politicians || []; cos = res.companies || []; secs = res.sectors || [];
      impactHtml = `<div style="max-width:680px;margin:0 auto;">${GI.panel(res, { reasons: true, dims: true })}</div>`;
    } else {
      // Fallback: compute and render generation bars locally.
      const impacts = billGenerationImpact(bill);
      impactHtml = `<div class="cd-gens">${impacts.map((g) => { const neg = g.score < 0, c = neg ? "#EF4444" : "#22C55E", w = Math.min(100, Math.abs(g.score) * 1.3); return `<div class="cd-gen-row"><div class="cd-gen-head"><b>${E(g.gen)}</b><span style="color:${c}">${g.score > 0 ? "+" : ""}${g.score}</span></div><div class="cd-gen-track"><div class="cd-gen-fill" style="width:${w}%;background:${c};${neg ? "" : "margin-left:auto"}"></div></div><div class="cd-gen-note">This ${neg ? "may hurt" : "may help"} ${E(g.gen)} because they are ${E(g.reason)}.</div></div>`; }).join("")}</div>`;
    }
    const stPill = `<span class="gimp-status gimp-${status.toLowerCase()}">${E(status)}</span>`;
    const affected = `
      <div class="cd-affect" style="max-width:680px;margin:14px auto 0;">
        ${secs.length ? `<div class="cd-affect-row"><span class="cd-affect-l">Sectors affected</span><div class="iw-chips">${secs.map((s) => `<span class="iw-chip">${E(s)}</span>`).join("")}</div></div>` : ""}
        ${cos.length ? `<div class="cd-affect-row"><span class="cd-affect-l">Companies affected</span><div class="iw-chips">${cos.map((c) => `<span class="iw-chip" data-dc="stock" data-tk="${E(c)}">${E(c)}</span>`).join("")}</div></div>` : ""}
        ${pols.length ? `<div class="cd-affect-row"><span class="cd-affect-l">Politicians involved</span><div class="iw-chips">${pols.map((p) => `<span class="iw-chip" data-dc="pol" data-name="${E(p)}">${E(p)}</span>`).join("")}</div></div>` : ""}
      </div>`;
    show(`
      <button class="iw-drill-close" data-dc="x">&times;</button>
      <div class="cd-head"><div class="iw-back" data-dc="modules">&lsaquo; Back to Congress</div>
        <h2>Generation Impact ${stPill}</h2>
        <p class="cd-sub"><b>${E(bill ? bill.bill_id : "")}</b> · ${E((bill && bill.title || "").slice(0, 90))}</p></div>
      <div class="cd-gen-pick">${bills.slice(0, 8).map((b) => `<span class="iw-chip ${b === bill ? "sel" : ""}" data-dc="gen" data-bill="${E(b.bill_id)}">${E(b.bill_id)}</span>`).join("")}</div>
      ${impactHtml}
      ${affected}
      <div class="cd-foot">Estimates of likely exposure by generation, based on the bill's sectors. Plain-English, non-partisan; does not imply wrongdoing.</div>`);
  }

  // Derive generational impact from state-level economic indicators
  // (cost pressure, affordability index, inflation rate) rather than bill sectors.
  // Younger cohorts are weighted more heavily because they have less financial cushion.
  function genImpactFromState(s) {
    const pressure = s.pressure_score || 0, afford = s.affordability || 50, infl = s.inflation || 2.5;
    const base = -(pressure - 40) * 0.6 - (60 - afford) * 0.3 - (infl - 2) * 4;
    const tilt = { "Gen Z": 1.2, "Millennials": 1.4, "Gen X": 0.9, "Baby Boomers": 0.5, "Retirees": 0.6 };
    return GENS.map((g) => ({ gen: g, score: Math.round(Math.max(-90, Math.min(40, base * tilt[g]))) }));
  }

  // Render compact horizontal bar rows for each generation's impact score.
  // Used in the state detail panel when window.GenImpact is unavailable.
  function genBars(impacts) {
    return impacts.map((g) => {
      const neg = g.score < 0, c = neg ? "#EF4444" : "#22C55E", w = Math.min(100, Math.abs(g.score) * 1.3);
      return `<div class="cd-gen-mini"><span>${E(g.gen)}</span>
        <div class="cd-gen-track"><div class="cd-gen-fill" style="width:${w}%;background:${c};${neg ? "" : "margin-left:auto"}"></div></div>
        <b style="color:${c}">${g.score > 0 ? "+" : ""}${g.score}</b></div>`;
    }).join("");
  }

  // Full state detail panel: governor info, Census economics, generation impact,
  // and a chip list of federal bills in play for the user to drill into.
  function stateDetail(st) {
    const g = GOVERNORS[st] || ["Unknown", "I"];
    const s = STATES[st] || {};
    const m0 = (v, suf = "") => v == null ? "Data unavailable" : v + suf;
    const inc = s.median_household_income ? "$" + Math.round(s.median_household_income).toLocaleString() : "Data unavailable";
    const bills = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])].slice(0, 5);
    show(`
      <button class="iw-drill-close" data-dc="x">&times;</button>
      <div class="cd-head"><div class="iw-back" data-dc="gov">&lsaquo; Back to Governors</div>
        <h2>${E(s.name || st)}</h2>
        <p class="cd-sub">Governor ${E(g[0])} · ${E(PARTY_NAME(g[1]))}</p></div>
      <div class="cd-detail">
        <div class="cd-card">
          <div class="iw-eyebrow">State Economy</div>
          <div class="cd-hc-grid">
            <div><span>Cost of Living</span><b style="color:${(s.cost_of_living||0)>110?"var(--danger)":(s.cost_of_living||0)>100?"var(--warning)":(s.cost_of_living||0)>90?"var(--info)":"var(--success)"}">${m0(Math.min(100, Math.round(s.cost_of_living||0)))}</b></div>
            <div><span>Median Income</span><b>${inc}</b></div>
            <div><span>Poverty</span><b>${m0(s.poverty_rate, "%")}</b></div>
            <div><span>Unemployment</span><b>${m0(s.unemployment, "%")}</b></div>
            <div><span>Inflation</span><b>${m0(s.inflation, "%")}</b></div>
            <div><span>Affordability</span><b>${m0(s.affordability)}</b></div>
          </div>
        </div>
        <div class="cd-card">
          <div class="iw-eyebrow">Pressure Snapshot</div>
          <div class="cd-press"><span>Housing / Cost Pressure</span><b class="${(s.pressure_score || 0) >= 50 ? "bad" : "ok"}">${(s.pressure_score || 0) >= 50 ? "High" : "Moderate"}</b></div>
          <div class="cd-press"><span>Prosperity</span><b>${s.prosperity_score || 0}/100</b></div>
          <div class="cd-press"><span>Real Purchasing Power</span><b>${s.real_purchasing_power ? "$" + Math.round(s.real_purchasing_power).toLocaleString() : "Data unavailable"}</b></div>
        </div>
      </div>
      <div style="max-width:640px;margin:14px auto 0;">
        ${window.GenImpact ? window.GenImpact.panel(window.GenImpact.forState(s), { reasons: true, title: "Generation Impact: " + E(s.name || st) + " cost conditions" })
          : `<div class="cd-card"><div class="iw-eyebrow">Generation Impact (state cost conditions)</div><div class="cd-gen-minis">${genBars(genImpactFromState(s))}</div></div>`}
      </div>
      <div class="cd-card" style="max-width:640px;margin:14px auto 0;">
        <div class="iw-eyebrow">Federal Bills In Play</div>
        <div class="iw-chips">${bills.map((b) => `<span class="iw-chip" data-dc="gen" data-bill="${E(b.bill_id)}">${E(b.bill_id)}</span>`).join("")}</div>
        <div class="cd-gen-note">Click a bill to see its generation impact.</div>
      </div>`);
  }

  // Inline SVG icon set for the four module cards on the Congress landing view.
  const ICON = {
    house: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 21h18M4 10h16M5 10V8l7-4 7 4v2M7 10v8m4-8v8m6-8v8"/></svg>',
    senate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 21h18M5 21V11m14 10V11M4 11l8-6 8 6M9 21v-6h6v6"/></svg>',
    gov: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 4 5.7 4 9s-1.5 6.4-4 9c-2.5-2.6-4-5.7-4-9s1.5-6.4 4-9Z"/></svg>',
    gen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="8" r="2.5"/><circle cx="16" cy="7" r="2"/><circle cx="17" cy="15" r="2.5"/><path d="M3 20c0-2.5 1.8-4.5 4-4.5M12 20c0-2 1.5-3.7 3.3-4M13 9c1-.6 2-.7 3 0"/></svg>',
  };

  // Event binding: wired once to the drill host element via a sentinel flag (_bound).
  // A single delegated listener on the host handles all click and mousemove routing.
  // Separate window-level listeners manage the map drag gesture.
  function bind() {
    const h = ensureHost(); if (!h || h._bound) return; h._bound = true;
    h.addEventListener("click", (e) => {
      const t = e.target.closest("[data-dc]"); if (!t) return;
      const a = t.dataset.dc;
      // Map zoom/pan buttons.
      if (a === "zin") { mapTf.s = Math.min(6, mapTf.s * 1.25); return applyMapTf(); }
      if (a === "zout") { mapTf.s = Math.max(0.6, mapTf.s * 0.8); return applyMapTf(); }
      if (a === "zfit") { mapTf = { x: 0, y: 0, s: 1 }; return applyMapTf(); }
      // Navigation and view switches.
      if (a === "x") return close();
      if (a === "modules") return modulesView();
      if (a === "house") return constellation("house");
      if (a === "senate") return constellation("senate");
      if (a === "gov") return governorsView();
      if (a === "gen") return generationView(t.dataset.bill);
      // Politician dot and hover card controls.
      if (a === "poldot") { const dot = t.closest(".cd-dot") || t; return hoverCard(t.dataset.name, dot, false); }
      if (a === "hexpand") return hoverCard(t.dataset.name || curPolName, curDotEl, true);
      if (a === "hcollapse") return hoverCard(curPolName, curDotEl, false);
      if (a === "hclose") return hideHover();
      // Open profile / company OVER the drill (modal z-index 100 > drill 20) so closing returns here.
      if (a === "pol") { if (window.politicianProfile) window.politicianProfile(t.dataset.name); return; }
      if (a === "stock") { if (window.stockDetail) window.stockDetail(t.dataset.tk); return; }
      // State click: skip if the user just finished dragging the map.
      if (a === "state") { if (mapMoved) { mapMoved = false; return; } return stateDetail(t.dataset.st); }
    });
    h.addEventListener("mousemove", (e) => {
      const dot = e.target.closest(".cd-dot");
      if (dot) { if (dot.dataset.name !== curPolName) hoverCard(dot.dataset.name, dot, false); return; }
      if (e.target.closest(".cd-hovercard")) return;        // moving onto the card: keep it open
      const st = e.target.closest(".cd-state-path") || e.target.closest(".cd-state");
      if (st) { curPolName = null; return stateHover(st.dataset.st, e); }
      if (curPolName) return;                                 // pinned politician card stays put
      hideHover();                                            // only the ephemeral state card hides
    });

    // Governors map: mouse drag for panning the SVG.
    let drag = null;
    h.addEventListener("mousedown", (e) => {
      const w = e.target.closest("#cd-map-wrap");
      if (!w || e.target.closest("button")) return;
      drag = { x: e.clientX, y: e.clientY, ox: mapTf.x, oy: mapTf.y }; mapMoved = false;
      w.style.cursor = "grabbing";
    });
    window.addEventListener("mousemove", (e) => {
      if (!drag) return;
      mapTf.x = drag.ox + (e.clientX - drag.x); mapTf.y = drag.oy + (e.clientY - drag.y);
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) mapMoved = true;
      applyMapTf();
    });
    window.addEventListener("mouseup", () => { if (drag) { drag = null; const w = document.getElementById("cd-map-wrap"); if (w) w.style.cursor = "grab"; } });
    // Wheel zoom on the map wrapper only; preventDefault stops page scroll.
    h.addEventListener("wheel", (e) => {
      if (!e.target.closest("#cd-map-wrap")) return;
      e.preventDefault();
      mapTf.s = Math.max(0.6, Math.min(6, mapTf.s * (e.deltaY < 0 ? 1.15 : 0.87)));
      applyMapTf();
    }, { passive: false });
  }

  // Public API: CongressDrill.open() launches the module selector.
  // CongressDrill.generation(billId) jumps directly to the generation-impact overlay.
  window.CongressDrill = {
    open() { bind(); modulesView(); },
    generation(billId) { bind(); generationView(billId); },
  };
})();
