// influenceweb.js
// What it does: Renders the interactive "InfluenceWeb" graph. Draws nodes for sectors,
//   companies, and politicians; handles zoom/pan (including zoom-to-Congress), hover
//   panels, zig-zag staggered child layout, cross-company relationship links
//   (shared lobby firm/owner/board member), and the US governors map.
// How it fits: Loaded via <script defer> in index.html. Exposes window.IW so the
//   router (app.js) can call IW.activate() / IW.deactivate() when switching tabs.
//   Reads window.TF_DATA, window.IW_DATA, and several other data bundles injected
//   by separate <script> tags before this file runs.
"use strict";

(function () {
  // --- external data bundles (populated by other <script> tags before this runs) ---
  const D = window.TF_DATA || {};
  const IWD = (window.IW_DATA || { companies: {} }).companies || {};
  const NPD = (window.NP_DATA || {}).byName || {};   // ProPublica nonprofit financials
  const SECD = (window.SEC_DATA || {}).byTicker || {};   // SEC current boards + filings
  const SECB = (window.SECBULK_DATA || {}).byTicker || {};   // SEC EDGAR bulk financials
  const FECD = (window.FEC_DATA || {}).byName || {};     // OpenFEC campaign finance
  const USAD = (window.USA_DATA || {}).byTicker || {};   // USASpending federal contracts
  const REL = (window.RELATIONSHIPS || {}).byTicker || {};   // Senate LDA lobbying relationships

  // Prefer current SEC director records; fall back to LittleSis historical data.
  // Normalises the shape so callers always get {name, title, independent, ...}.
  function boardOf(tk) {
    const s = SECD[tk];
    if (s && s.board && s.board.length) {
      return s.board.map((m) => {
        const pos = m.position || "Director";
        const indep = m.independent === true || /independent/i.test(pos);
        const title = pos.replace(/independent\s*/i, "").trim() || "Director";
        return { name: m.name, title: title.charAt(0).toUpperCase() + title.slice(1), age: m.age,
                 committees: m.committees || [], independent: indep, since: m.since, source: "SEC" };
      });
    }
    const l = IWD[tk] || {};
    return [...(l.board || []), ...(l.executives || [])].map((m) => ({ name: m.name, title: m.title || "Director", current: m.current, source: "LittleSis" }));
  }

  // Sector-level lobbying groups: used to surface "who lobbies for this sector"
  // when a company has no direct registration of its own.
  const SECTOR_LOBBY = {
    "Technology": ["Information Technology Industry Council", "Semiconductor Industry Assn"],
    "Healthcare": ["American Hospital Assn"],
    "Pharmaceuticals": ["PhRMA"],
    "Financial Services": ["American Bankers Assn", "Securities Industry & Fin. Markets Assn"],
    "Energy": ["Edison Electric Institute"],
    "Oil & Gas": ["American Petroleum Institute"],
    "Telecommunications": ["Internet & Television Assn"],
    "Real Estate": ["Natl Assn of Realtors", "Real Estate Roundtable"],
    "Consumer Goods": ["Natl Retail Federation", "Grocery Manufacturers Assn"],
    "Defense": ["Natl Assn of Manufacturers"],
    "Transportation": ["Natl Assn of Manufacturers"],
  };

  // Groups that lobby across every sector (always included in political-ties output).
  const CROSS_LOBBY = ["US Chamber of Commerce", "Business Roundtable"];

  // HTML-escape helper: used whenever dynamic data is inserted into innerHTML.
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Returns up to 2 uppercase initials from a display name (fallback "?").
  const initials = (n) => String(n || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  // Visual fill colour for each logical node type (bubble background / orbit dots).
  const TYPE_COLOR = { company: "#E5E9F0", government: "#38BDF8", political: "#EF4444", financial: "#E9C46A", other: "#14B8A6" };

  // Inline SVG path data for each icon class.
  // stroke=currentColor so the node's colorType drives the visible colour.
  const I = {
    congress: '<path d="M3 21h18M5 21V10m14 11V10M4 10l8-5 8 5M9 21v-6h6v6M8 10v4m4-4v4m4-4v4"/>',
    defense: '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z"/>',
    technology: '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M9 20h6M12 16v4"/>',
    healthcare: '<path d="M12 4v16M4 12h16" stroke-width="2.4"/>',
    pharmaceuticals: '<rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(45 12 12)"/><path d="M9 9l6 6"/>',
    financial: '<path d="M3 21h18M4 10h16M5 10V8l7-4 7 4v2M7 10v8m4-8v8m6-8v8"/>',
    energy: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
    oil: '<path d="M12 3c3 4 6 7 6 11a6 6 0 0 1-12 0c0-4 3-7 6-11Z"/>',
    telecom: '<path d="M5 18a10 10 0 0 1 14 0M8 15a6 6 0 0 1 8 0M11 12a2 2 0 0 1 2 0M12 18h.01"/>',
    realestate: '<path d="M3 11l9-7 9 7M5 10v10h14V10M10 20v-6h4v6"/>',
    transportation: '<rect x="1" y="6" width="14" height="10" rx="1"/><path d="M15 9h4l3 3v4h-7M5.5 19a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6Zm12 0a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6Z"/>',
    consumer: '<path d="M5 7h15l-2 9H7L5 7ZM5 7 4 4H2M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"/>',
    board: '<circle cx="9" cy="9" r="2.4"/><circle cx="16" cy="10" r="2"/><path d="M4 19c0-2.8 2.2-5 5-5s5 2.2 5 5M14 17c.4-1.8 1.9-3 3.7-3 1.6 0 3 1 3.3 2.6"/>',
    contracts: '<path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    lobbying: '<path d="M4 21h16M6 21V8h12v13M9 21v-5h6v5M9 8V5l3-2 3 2v3"/>',
    pac: '<circle cx="12" cy="12" r="8"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.4 0-2.5 1-2.5 2.2 0 2.6 5 1.6 5 4.2 0 1.2-1.1 2.1-2.5 2.1-1 0-2-.5-2.5-1.5M12 6.5v1.5m0 8v1.5"/>',
    shareholders: '<path d="M12 12V3a9 9 0 1 0 9 9h-9Z"/><path d="M14 4a9 9 0 0 1 6 6h-6V4Z"/>',
    political: '<circle cx="9" cy="8" r="2.4"/><circle cx="16" cy="9" r="2"/><path d="M3 19c0-3 2.5-5.5 6-5.5s6 2.5 6 5.5M14 18c.3-2 2-3.5 4-3.5"/>',
    bills: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6"/>',
    foreign: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 4 5.7 4 9s-1.5 6.4-4 9c-2.5-2.6-4-5.7-4-9s1.5-6.4 4-9Z"/>',
    subsidiaries: '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="19" r="2.2"/><circle cx="19" cy="19" r="2.2"/><path d="M12 7v4M12 11l-6 6M12 11l6 6"/>',
  };

  // Curated first-tier company list per sector. These always appear before the
  // rest of the S&P 500 membership (which gets merged in by mergeSP500 below).
  const SECTORS = [
    { name: "Defense", icon: "defense", t: ["LMT","RTX","NOC","BA","GD","LHX","HII","BWXT","LDOS","TXT","HWM"] },
    { name: "Technology", icon: "technology", t: ["AAPL","MSFT","NVDA","GOOGL","GOOG","AMZN","META","AMD","ADBE","CRM","ORCL","CSCO","ADI","CDW","APP","CIEN","INTC","QCOM","TXN","IBM","NOW","PLTR"] },
    { name: "Healthcare", icon: "healthcare", t: ["UNH","CI","HUM","ELV","CVS","ISRG","BSX","ABT","ALGN","BDX","SYK","MDT","DHR"] },
    { name: "Pharmaceuticals", icon: "pharmaceuticals", t: ["PFE","LLY","JNJ","MRK","ABBV","BMY","AMGN","BIIB","GILD","BBIO","ARQT","VRTX","REGN"] },
    { name: "Financial Services", icon: "financial", t: ["JPM","BAC","WFC","GS","MS","C","AXP","BLK","COF","SPGI","CB","BRK.B","BNPQF","AMP","SCHW","V","MA"] },
    { name: "Energy", icon: "energy", t: ["NEE","DUK","SO","D","CEG","BEP","DTE","AESI","EXC","AEP"] },
    { name: "Oil & Gas", icon: "oil", t: ["XOM","CVX","COP","SLB","VLO","ARLP","OXY","PSX","MPC","EOG"] },
    { name: "Telecommunications", icon: "telecom", t: ["VZ","T","CMCSA","TMUS","CHTR"] },
    { name: "Real Estate", icon: "realestate", t: ["AMT","PLD","SPG","O","CCI","EQIX"] },
    { name: "Transportation", icon: "transportation", t: ["UPS","FDX","DAL","UAL","CHRW","CAT","CARR","CSX","NSC"] },
    { name: "Consumer Goods", icon: "consumer", t: ["WMT","PG","KO","COST","CLX","CAG","AZO","CL","PEP","MDLZ","KHC"] },
  ];

  // Merge the full S&P 500 into the sectors. Curated names stay first; the rest
  // of each sector's real membership is appended (shown via "View More").
  const SP = (window.SP500 || {}).byTicker || {};
  const PX = (window.PRICES_DATA || {}).byTicker || {};
  (function mergeSP500() {
    const bySec = {};
    Object.keys(SP).forEach((tk) => { const s = SP[tk].sector; (bySec[s] = bySec[s] || []).push(tk); });
    const byName = {}; SECTORS.forEach((sec) => (byName[sec.name] = sec));
    const EXTRA_ICON = { Industrials: "transportation", Materials: "energy" };
    Object.keys(bySec).forEach((name) => {
      if (!byName[name]) { const sec = { name, icon: EXTRA_ICON[name] || "subsidiaries", t: [] }; SECTORS.push(sec); byName[name] = sec; }
    });
    SECTORS.forEach((sec) => {
      const have = new Set(sec.t);
      (bySec[sec.name] || []).forEach((tk) => { if (!have.has(tk)) { have.add(tk); sec.t.push(tk); } });
    });
  })();

  // Quick market-cap lookup used for sorting companies within a sector ring.
  const marketCap = (tk) => (PX[tk] && PX[tk].market_cap) || 0;

  // --- index structures built once from the data bundles ---
  const tradeCount = {}, billsByTicker = {}, polsByTicker = {}, lobbyBySector = {};

  // personIndex: person name -> [{ticker, company, title, current, role}]
  // Used to find all companies a board member touches (revolving-door detection).
  const personIndex = {};

  // Walk every company's board and populate personIndex so we can reverse-lookup
  // "which other companies does this person sit on?" in O(1).
  function buildPersonIndex() {
    // SEC current boards (preferred) + LittleSis history -> person connections
    const allTk = new Set([...Object.keys(IWD), ...Object.keys(SECD)]);
    allTk.forEach((tk) => {
      const co = IWD[tk] || {};
      const name = (SECD[tk] && SECD[tk].entityName) || co.name || tk;
      boardOf(tk).forEach((m) => pushPerson({ name: m.name, title: m.title, current: m.current }, tk, name, m.source === "SEC" ? "Board" : (m.title || "Board")));
    });
  }

  // Append a single person-company entry to personIndex.
  function pushPerson(m, tk, company, role) {
    (personIndex[m.name] = personIndex[m.name] || []).push({ ticker: tk, company, title: m.title, current: m.current, role });
  }

  // Build all secondary indexes from TF_DATA on first activate.
  function indexData() {
    buildPersonIndex();
    const all = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])];
    const seen = new Set();
    all.forEach((b) => {
      if (seen.has(b.bill_id)) return; seen.add(b.bill_id);
      (b.sectors || []).forEach((s) => { (lobbyBySector[s] = lobbyBySector[s] || new Set()); (b.lobbying || []).forEach((l) => lobbyBySector[s].add(l.org)); });
      (b.tickers || []).forEach((tk) => { (billsByTicker[tk] = billsByTicker[tk] || []); if (!billsByTicker[tk].some((x) => x.bill_id === b.bill_id)) billsByTicker[tk].push(b); });
    });
    (D.recent_trades || []).forEach((t) => { if (!t.ticker) return; tradeCount[t.ticker] = (tradeCount[t.ticker] || 0) + 1; (polsByTicker[t.ticker] = polsByTicker[t.ticker] || new Set()).add(t.politician); });
  }

  // Best available display name for a ticker (tries multiple sources in priority order).
  const compName = (tk) => (IWD[tk] && IWD[tk].name) || (SECD[tk] && SECD[tk].entityName) || (PX[tk] && PX[tk].name) || (SP[tk] && SP[tk].name) || tk;

  // True when we have at least some relationship data for this company.
  function companyHasData(tk) { return IWD[tk] || SECD[tk] || tradeCount[tk] || (billsByTicker[tk] || []).length; }

  // Full sector membership, most important first (market cap, then influence).
  // The graph shows the top SHOW_LIMIT and reveals the rest via the "More" node.
  function sectorCompanies(sec) {
    return (sec.t || []).slice().sort((a, b) => (marketCap(b) - marketCap(a)) || (companyInfluence(b) - companyInfluence(a)) || a.localeCompare(b));
  }

  // Composite influence score: each signal type is weighted to reflect how
  // entangled the company is with the government and its own industry peers.
  function companyInfluence(tk) {
    const lis = IWD[tk] || {};
    const board = boardOf(tk).length;
    const owners = (lis.owners || []).length;
    const bills = (billsByTicker[tk] || []).length;
    const trades = tradeCount[tk] || 0;
    return 18 + board * 1.4 + owners * 2.2 + bills * 2.2 + Math.min(trades, 60) * 0.5;
  }

  // Sector-level influence aggregates its companies' scores but caps per-company
  // contribution so a massive sector doesn't dwarf a focused one.
  function sectorInfluence(sec) {
    const comps = sectorCompanies(sec);
    // count contribution is bounded so density reflects real activity, not raw S&P size
    let s = Math.min(comps.length, 14) * 3.2;
    comps.forEach((tk) => { s += companyInfluence(tk) * 0.18; });
    s += (lobbyBySector[sec.name] ? lobbyBySector[sec.name].size : 0) * 4;
    return s;
  }

  // Human-readable influence tier label shown in the bubble subtitle.
  function influenceLabel(tk) {
    const v = companyInfluence(tk);
    return v > 55 ? "High" : v > 35 ? "Medium" : "Moderate";
  }

  // cross-company links: a clear shared connection between two companies.
  // Returns a short label describing HOW they connect, or "" if unrelated.
  function sharedOwner(a, b) {
    const oa = new Set((IWD[a] && IWD[a].owners || []).map((o) => o.name));
    return (IWD[b] && IWD[b].owners || []).some((o) => oa.has(o.name));
  }

  // Finds the strongest verifiable link between two companies (for xlink edges).
  // Priority: shared lobby firm > shared institutional owner > shared board member.
  function sharedLink(a, b) {
    // shared lobbying firm (strongest, most concrete connection)
    const fa = new Set((REL[a] && REL[a].firms) || []);
    const firm = ((REL[b] && REL[b].firms) || []).find((f) => fa.has(f));
    if (firm) return "Both lobby via " + firm;
    // shared major owner / institutional holder
    if (sharedOwner(a, b)) {
      const oa = new Set((IWD[a] && IWD[a].owners || []).map((o) => o.name));
      const own = (IWD[b] && IWD[b].owners || []).find((o) => oa.has(o.name));
      if (own) return "Shared owner: " + own.name;
    }
    // shared board member
    const ba = new Set(boardOf(a).map((m) => m.name));
    const dir = boardOf(b).map((m) => m.name).find((nm) => ba.has(nm));
    if (dir) return "Shared board member: " + dir;
    return "";
  }

  // --- graph state (mutated by expand/collapse, reset, etc.) ---
  let nodes = [], edges = [], nodeById = {}, seq = 0;
  let scene, edgesSvg, canvas, panel, tip, hud, W = 0, H = 0;
  let cam = { x: 0, y: 0, zoom: 1 }, camT = null, preZoomCam = null;
  let drag = null, started = false, active = false, selectedId = null, settle = 0;
  let leaving = [], sweepTimer = null, showXlinks = true, focusedSector = null;
  const ZOOM_MIN = 0.3, ZOOM_MAX = 3.2;   // hard bounds so the user can't lose the map
  const FIT_MAX = 1.5;                     // never auto-fit closer than this

  // Add a node to the graph, assign a unique id, and initialise velocity.
  function addNode(o) {
    o.id = "n" + seq++;
    o.vx = 0; o.vy = 0; o.fresh = true;   // fade-in on first render
    nodes.push(o); nodeById[o.id] = o; return o;
  }

  // Add a directed edge between two nodes (guard against null inputs).
  function addEdge(a, b, kind) { if (a && b) edges.push({ a: a.id, b: b.id, kind }); }

  // Skill-tree sizing: bubbles get smaller the further out you go.
  const NODE_SIZE = 72;
  function sizeForType(o) {
    switch (o.type) {
      case "congress": return 118;
      case "sector": return 94;
      case "company": case "more": return 72;
      case "category": return 56;
      default: return 50;
    }
  }

  // --- expansion ---
  // Dynamic radius: more (or larger) children => larger ring so slots never overlap.
  function dynRadius(parent, count, childSize) {
    const pr = (parent.size || sizeForType(parent)) / 2;
    const cs = childSize || NODE_SIZE;
    const childFoot = cs + 78;                         // bubble + label + gap per slot
    const byCirc = (count * childFoot) / (2 * Math.PI);
    return Math.max(pr + cs / 2 + 120, byCirc, 260);
  }

  // Maximum companies shown per sector before a "See More" node appears.
  const SHOW_LIMIT = 12;

  // Expand the Congress hub: one sector node per entry in SECTORS arranged in a full circle.
  function expandCongress(cn) {
    if (cn.expanded) return; cn.expanded = true;
    const n = SECTORS.length;
    const radius = dynRadius(cn, n, 94);
    SECTORS.forEach((sec, i) => {
      const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
      const node = addNode({ type: "sector", colorType: "company", label: sec.name, sec, icon: sec.icon, parent: cn.id });
      node.tx = cn.x + Math.cos(a) * radius; node.ty = cn.y + Math.sin(a) * radius;
      node.x = cn.x; node.y = cn.y;        // start at hub, spring outward
      node.angle = a; node.size = sizeForType(node); node.targetDist = radius;
      addEdge(cn, node, "main");
    });
  }

  // Create a single company bubble and link it to its parent sector node.
  function makeCompanyNode(sn, tk) {
    const node = addNode({ type: "company", colorType: "company", label: tk, ticker: tk, icon: sn.sec.icon, parent: sn.id, sensitive: !!(tradeCount[tk] && (billsByTicker[tk] || []).length && (lobbyBySector[sn.sec.name] || new Set()).size) });
    node.size = sizeForType(node);
    addEdge(sn, node, "main");
    return node;
  }

  // Create the "+N More" overflow node that lets the user reveal the next batch.
  function makeMoreNode(sn) {
    const node = addNode({ type: "more", colorType: "other", label: `+${sn._all.length - sn._shown} More`, icon: "subsidiaries", moreOf: sn.id, parent: sn.id });
    node.size = NODE_SIZE;
    addEdge(sn, node, "main");
    return node;
  }

  // Expand a sector: add the top-SHOW_LIMIT company nodes and a "More" node if needed.
  function expandSector(sn) {
    if (sn.expanded) return; sn.expanded = true;
    sn._all = sectorCompanies(sn.sec);
    sn._shown = Math.min(SHOW_LIMIT, sn._all.length);
    sn._all.slice(0, sn._shown).forEach((tk) => makeCompanyNode(sn, tk));
    if (sn._all.length > sn._shown) makeMoreNode(sn);
    layoutChildren(sn);
    linkSharedOwners();
  }

  // Reveal the next batch of companies when the user clicks the "+N More" node.
  function revealMore(moreNode) {
    const sn = nodeById[moreNode.moreOf]; if (!sn) return;
    nodes = nodes.filter((x) => x.id !== moreNode.id);
    edges = edges.filter((e) => e.a !== moreNode.id && e.b !== moreNode.id);
    delete nodeById[moreNode.id];
    sn._all.slice(sn._shown, sn._shown + SHOW_LIMIT).forEach((tk) => makeCompanyNode(sn, tk));
    sn._shown = Math.min(sn._shown + SHOW_LIMIT, sn._all.length);
    if (sn._all.length > sn._shown) makeMoreNode(sn);
    layoutChildren(sn);
    linkSharedOwners();
    rebuild();
    // re-fit to the now-larger ring so the newly revealed companies stay on-page
    fitSubtree(sn, 0.74);
  }

  // Evenly distribute all of a parent's children around it (dynamic radius).
  // Tree-style branching: children fan out in an OUTWARD arc away from the
  // grandparent, so each level grows further out instead of folding back inward.
  function layoutChildren(parent) {
    const kids = nodes.filter((n) => n.parent === parent.id);
    const n = kids.length || 1;
    const cs = (kids[0] && kids[0].size) || NODE_SIZE;
    const childFoot = cs + 66;                          // footprint per child
    const hasGrand = parent.parent != null && nodeById[parent.parent];
    let center, span;
    if (!hasGrand) {                                    // root (Congress): full circle, single ring
      center = -Math.PI / 2; span = Math.PI * 2 * (1 - 1 / n);
    } else {                                            // outward fan (points away from grandparent, never sideways into neighbors)
      center = parent.angle != null ? parent.angle : 0;
      span = Math.min(Math.PI * 0.9, 0.6 + (n - 1) * 0.2);
    }
    // Staggered zig-zag: when a branch gets crowded, alternate children between an
    // inner and outer radius so the ring stays compact instead of sprawling out.
    const zig = hasGrand && n > 5;
    const rows = zig ? 2 : 1;
    const stagger = zig ? childFoot * 0.6 : 0;          // radial offset (>= bubble: no overlap)
    // radius from arc length of the busiest row, so the fan never crowds
    const arcR = n > 1 ? (Math.ceil(n / rows) * childFoot) / (span || 1) : 0;
    // hard clearance: keep the whole cluster well outside the parent so it never
    // crowds the sector ring, even after "See More" pushes the fan further out
    const clearance = hasGrand ? 230 : 140;
    const radius = Math.max((parent.size || 80) / 2 + cs / 2 + clearance, arcR, 260);
    const start = hasGrand ? center - span / 2 : center;
    kids.forEach((node, i) => {
      const a = n === 1 ? center : start + (i / (n - 1)) * span;
      const r = radius + (i % rows) * stagger;          // zig-zag: even=inner, odd=outer
      node.tx = parent.x + Math.cos(a) * r; node.ty = parent.y + Math.sin(a) * r;
      // start AT the parent so the spring glides them outward (fluid expand)
      if (node.fresh) { node.x = parent.x; node.y = parent.y; node.vx = 0; node.vy = 0; }
      node.angle = a; node.targetDist = r;
    });
    return radius + stagger;
  }

  // Scan all visible company nodes and add xlink edges wherever two companies share
  // an owner, lobby firm, or board member. Skips pairs already connected.
  function linkSharedOwners() {
    const comps = nodes.filter((n) => n.type === "company");
    for (let i = 0; i < comps.length; i++)
      for (let j = i + 1; j < comps.length; j++) {
        const exists = edges.some((e) => e.kind === "xlink" && ((e.a === comps[i].id && e.b === comps[j].id) || (e.a === comps[j].id && e.b === comps[i].id)));
        if (exists) continue;
        const label = sharedLink(comps[i].ticker, comps[j].ticker);
        if (label) edges.push({ a: comps[i].id, b: comps[j].id, kind: "xlink", label });
      }
  }

  // A company's full political footprint: members who traded it + the lobbying
  // groups that represent its industry (every company is covered by the cross-
  // sector business lobbies) + federal contracts + registered-lobbyist status.
  function politicalTies(tk) {
    const traders = [...(polsByTicker[tk] || [])];
    const sec = SECTORS.find((s) => (s.t || []).includes(tk));
    const industry = [...new Set([...(SECTOR_LOBBY[sec && sec.name] || []), ...CROSS_LOBBY])];
    const r = REL[tk] || {};
    const firms = r.firms || [], lobbyists = r.lobbyists || [], issues = r.issues || [], bills = r.bills || [];
    const contracts = !!((USAD[tk] && USAD[tk].total_contracts) || (IWD[tk] && IWD[tk].fedspending_id));
    const registered = !!((IWD[tk] && IWD[tk].lda_registrant_id) || r.filings);
    const count = traders.length + industry.length + firms.length + lobbyists.length + bills.length + (contracts ? 1 : 0);
    return { traders, industry, firms, lobbyists, issues, bills, contracts, registered, spend: r.spend_fmt, filings: r.filings, sec, count };
  }

  // Category child nodes that appear under each company (board, shareholders, etc.).
  // The "contracts" category is hidden when there is no USASpending data.
  const CATEGORIES = [
    { key: "board", label: "Board of Directors", icon: "board", color: "other", sub: (tk) => boardOf(tk).length + " Members" },
    { key: "shareholders", label: "Major Shareholders", icon: "shareholders", color: "financial", sub: (tk) => (IWD[tk] && IWD[tk].owners || []).slice(0, 2).map((o) => o.name.split(" ")[0]).join(", ") || "Institutional" },
    { key: "political", label: "Political Connections", icon: "political", color: "political", sub: (tk) => politicalTies(tk).count + " Connections" },
    { key: "bills", label: "Related Legislation", icon: "bills", color: "government", sub: (tk) => (billsByTicker[tk] || []).length + " Bills" },
    { key: "lobbying", label: "Lobbying", icon: "lobbying", color: "financial", sub: (tk) => (IWD[tk] && IWD[tk].lda_registrant_id) ? "Registered" : "Sector-level" },
    { key: "contracts", label: "Govt Contracts", icon: "contracts", color: "government", sub: (tk) => (IWD[tk] && IWD[tk].fedspending_id) ? "Federal contractor" : "n/a" },
  ];

  // Expand a company: add one category bubble per CATEGORIES entry (skip "contracts"
  // when there is no USASpending record for this ticker).
  function expandCompany(cn) {
    if (cn.expanded) return; cn.expanded = true;
    const cats = CATEGORIES.filter((c) => c.key !== "contracts" || (USAD[cn.ticker] && USAD[cn.ticker].total_contracts) || (IWD[cn.ticker] && IWD[cn.ticker].fedspending_id));
    cats.forEach((cat) => {
      const node = addNode({ type: "category", colorType: cat.color, label: cat.label, sub: cat.sub(cn.ticker), icon: cat.icon, cat: cat.key, ticker: cn.ticker, parent: cn.id });
      node.size = sizeForType(node);
      addEdge(cn, node, "main");
    });
    layoutChildren(cn);
  }

  // Dispatch to the correct expand function based on node type.
  function expandNode(n) {
    if (n.type === "congress") expandCongress(n);
    else if (n.type === "sector") expandSector(n);
    else if (n.type === "company") expandCompany(n);
  }

  // True when node d is anywhere in the subtree rooted at p.
  function isDescendant(d, p) {
    let cur = d;
    while (cur && cur.parent != null) { if (cur.parent === p.id) return true; cur = nodeById[cur.parent]; }
    return false;
  }

  // Retract a branch: glide descendants inward toward the node, then remove them.
  function collapse(node) {
    node.expanded = false;
    if (node.type === "sector") { node._shown = 0; node._all = null; }
    const rm = nodes.filter((x) => isDescendant(x, node) && !x.collapsing);
    if (!rm.length) return;
    rm.forEach((x) => { x.collapsing = true; x.tx = node.x; x.ty = node.y; });
    leaving.push(...rm);
    settle = 30;
    scheduleSweep();
  }

  // Deferred DOM cleanup: wait for the CSS collapse animation to finish, then
  // remove the nodes and edges from the live arrays and rebuild the SVG layer.
  function scheduleSweep() {
    if (sweepTimer) return;
    sweepTimer = setTimeout(() => {
      sweepTimer = null;
      if (!leaving.length) return;
      const ids = new Set(leaving.map((x) => x.id));
      nodes = nodes.filter((x) => !ids.has(x.id));
      edges = edges.filter((e) => !ids.has(e.a) && !ids.has(e.b));
      leaving.forEach((x) => delete nodeById[x.id]);
      leaving = [];
      rebuild();
    }, 300);
  }

  // When focusing N, retract any sibling branch at the same level (no overlap).
  function collapseSiblings(n) {
    nodes.filter((x) => x.parent === n.parent && x.id !== n.id && x.expanded).forEach(collapse);
  }

  // --- camera helpers ---
  // Convert screen coordinates to world (unzoomed) coordinates.
  function s2w(sx, sy) { return { x: (sx - cam.x) / cam.zoom, y: (sy - cam.y) / cam.zoom }; }

  // Apply the current camera transform to the scene container.
  function applyCam() { scene.style.transform = `translate(${cam.x}px,${cam.y}px) scale(${cam.zoom})`; }

  // Rebuild the full DOM: remove all iw-node divs and SVG lines, then re-create
  // them from the current nodes/edges arrays. Called after structural graph changes.
  function rebuild() {
    // remove old node divs (keep svg)
    [...scene.querySelectorAll(".iw-node")].forEach((el) => el.remove());
    edgesSvg.innerHTML = "";

    edges.forEach((e) => {
      if (e.kind === "xlink" && !showXlinks) return;
      const a = nodeById[e.a], b = nodeById[e.b]; if (!a || !b) return;
      const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
      ln.setAttribute("x1", a.x); ln.setAttribute("y1", a.y);
      ln.setAttribute("x2", b.x); ln.setAttribute("y2", b.y);
      ln.setAttribute("class", e.kind === "xlink" ? "iw-line iw-xlink" : "iw-line");
      ln.dataset.a = e.a; ln.dataset.b = e.b;
      if (e.label) {   // native tooltip describing HOW the two companies connect
        const ttl = document.createElementNS("http://www.w3.org/2000/svg", "title");
        ttl.textContent = e.label; ln.appendChild(ttl);
      }
      e.el = ln;
      edgesSvg.appendChild(ln);
    });

    nodes.forEach((n) => {
      const el = document.createElement("div");
      el.className = `iw-node iw-${n.type}`;
      // focus mode: when inside a sector, fade the other sectors so the active branch owns the space
      if (focusedSector && n.type === "sector" && n.id !== focusedSector) el.classList.add("iw-faded");
      el.dataset.id = n.id;
      el.style.left = n.x + "px"; el.style.top = n.y + "px";
      const sz = n.size || sizeForType(n);
      const col = TYPE_COLOR[n.colorType] || "#E5E9F0";
      const dots = orbitDots(n);
      // Company nodes: show Clearbit logo if a domain is known; otherwise SVG icon.
      const center = (n.type === "company" && IWD[n.ticker] && IWD[n.ticker].domain)
        ? `<img class="iw-logo" alt="${E(n.ticker)} logo" src="https://logo.clearbit.com/${E(IWD[n.ticker].domain)}" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'iw-ini',textContent:'${E(n.ticker)}'}))"/>`
        : `<span class="iw-ico" style="color:${col}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[n.icon] || I.subsidiaries}</svg></span>`;
      const name = n.type === "congress" ? "U.S. CONGRESS" : (n.type === "company" ? n.ticker : n.label);
      const sub = n.type === "sector" ? `${sectorCompanies(n.sec).length} companies`
        : n.type === "company" ? `Influence: ${influenceLabel(n.ticker)}`
        : n.type === "category" ? (n.sub || "") : "Hub";
      el.innerHTML = `
        <div class="iw-bubble" style="width:${sz}px;height:${sz}px;--ring:${n.sensitive ? "#EF4444" : col};--orad:${Math.round(sz / 2 + 9)}px;animation-delay:${(parseInt(n.id.slice(1)) % 10) * -0.7}s">
          <div class="iw-orbit">${dots}</div>
          ${center}
        </div>
        <div class="iw-cap"><div class="iw-name">${E(name)}</div><div class="iw-sub">${E(sub)}</div></div>`;
      // fresh nodes start hidden (fade in); leaving nodes start visible (fade out)
      el.style.opacity = (n.fresh && !n.collapsing) ? "0.001" : "1";
      n.el = el;
      scene.appendChild(el);
    });
    syncDOM();
    // next frame: trigger the opacity transition (fade-in for new, fade-out for leaving)
    requestAnimationFrame(() => {
      nodes.forEach((n) => {
        if (!n.el) return;
        if (n.collapsing) n.el.style.opacity = "0";
        else if (n.fresh) { n.el.style.opacity = "1"; n.fresh = false; }
      });
    });
  }

  // Stable layout: each node is anchored to a fixed target SLOT.
  // Forces = spring toward slot + collision-only repulsion. No free orbiting.
  function physics() {
    const vis = nodes;
    for (const n of vis) { n._fx = 0; n._fy = 0; }
    // collision-only repulsion (acts solely when bubbles overlap)
    for (let i = 0; i < vis.length; i++) {
      const a = vis[i], ar = (a.size || NODE_SIZE) / 2;
      for (let j = i + 1; j < vis.length; j++) {
        const b = vis[j], br = (b.size || NODE_SIZE) / 2;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const minD = ar + br + 34;               // never touch + label room
        if (d < minD) {
          const push = (minD - d) * 0.5;
          const ux = dx / d, uy = dy / d;
          a._fx -= ux * push; a._fy -= uy * push;
          b._fx += ux * push; b._fy += uy * push;
        }
      }
    }
    // spring toward fixed slot (this kills the orbiting)
    for (const n of vis) {
      if (n.type === "congress" || n.tx == null) continue;
      n._fx += (n.tx - n.x) * 0.14;
      n._fy += (n.ty - n.y) * 0.14;
    }
    // integrate with strong damping; congress pinned at origin
    let moving = 0;
    for (const n of vis) {
      if (n.type === "congress") { n.x = 0; n.y = 0; n.vx = n.vy = 0; continue; }
      n.vx = (n.vx + n._fx) * 0.55;
      n.vy = (n.vy + n._fy) * 0.55;
      n.x += n.vx; n.y += n.vy;
      moving += Math.abs(n.vx) + Math.abs(n.vy);
    }
    return moving;
  }

  // Push the current node and edge positions into the DOM (cheap, no full rebuild).
  function syncDOM() {
    for (const n of nodes) if (n.el) { n.el.style.left = n.x + "px"; n.el.style.top = n.y + "px"; }
    for (const e of edges) if (e.el) {
      const a = nodeById[e.a], b = nodeById[e.b]; if (!a || !b) continue;
      e.el.setAttribute("x1", a.x); e.el.setAttribute("y1", a.y);
      e.el.setAttribute("x2", b.x); e.el.setAttribute("y2", b.y);
    }
  }

  // Camera auto-fit to a node and all its children (uses target positions).
  // pad < 1 leaves margin around the bbox: lower pad = more zoomed-out / more room.
  function fitSubtree(parent, pad) {
    const group = nodes.filter((n) => (n.id === parent.id || n.parent === parent.id) && !n.collapsing);
    if (!group.length) return;
    pad = pad || 0.85;
    let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    group.forEach((n) => {
      const px = n.tx != null ? n.tx : n.x, py = n.ty != null ? n.ty : n.y;
      const r = (n.size || 60) / 2 + 70;
      minX = Math.min(minX, px - r); maxX = Math.max(maxX, px + r);
      minY = Math.min(minY, py - r); maxY = Math.max(maxY, py + r);
    });
    const bw = maxX - minX, bh = maxY - minY;
    // fit the whole bbox inside the viewport with margin, bounded by hard zoom limits
    const z = Math.max(ZOOM_MIN, Math.min(FIT_MAX, Math.min(W / bw, H / bh) * pad));
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    camT = { x: W / 2 - cx * z, y: H / 2 - cy * z, zoom: z };
  }

  // Generate the coloured orbit-dot HTML for a node's activity indicator ring.
  // The dot count reflects how much relationship data the node has.
  function orbitDots(n) {
    let count = 0, palette = ["#38BDF8", "#E9C46A", "#EF4444", "#14B8A6"];
    if (n.type === "sector") count = Math.min(10, sectorCompanies(n.sec).length);
    else if (n.type === "company") count = Math.min(8, ((IWD[n.ticker] && IWD[n.ticker].board || []).length ? 4 : 0) + ((polsByTicker[n.ticker] ? polsByTicker[n.ticker].size : 0) ? 3 : 0) + ((billsByTicker[n.ticker] || []).length ? 2 : 0));
    else if (n.type === "congress") count = 10;
    let out = "";
    for (let i = 0; i < count; i++) {
      const a = (i / count) * 360;
      out += `<span class="iw-odot" style="transform:rotate(${a}deg) translateX(var(--orad));background:${palette[i % palette.length]};color:${palette[i % palette.length]}"></span>`;
    }
    return out;
  }

  // Render the breadcrumb trail above the graph to show the current focus path.
  function setBreadcrumb(n) {
    const bc = document.getElementById("iw-breadcrumb"); if (!bc) return;
    const chain = []; let cur = n;
    while (cur) { chain.unshift(cur); cur = cur.parent != null ? nodeById[cur.parent] : null; }
    bc.innerHTML = chain.map((c, i) => `<span class="iw-crumb${i === chain.length - 1 ? " cur" : ""}" data-cr="${c.id}">${E(c.type === "congress" ? "Congress" : c.label)}</span>`).join('<span class="iw-csep">&rsaquo;</span>');
  }

  // Focus a node: collapse its siblings, expand it, open the side panel, and
  // animate the camera to keep the newly revealed children on screen.
  function focus(n) {
    selectedId = n.id;
    collapseSiblings(n);   // retract the previously opened branch at this level
    // track the active sector branch so the other sectors fade out of the way
    let fs = null, cur = n;
    while (cur) { if (cur.type === "sector") { fs = cur.id; break; } cur = cur.parent != null ? nodeById[cur.parent] : null; }
    focusedSector = n.type === "congress" ? null : fs;
    expandNode(n);
    rebuild();
    setBreadcrumb(n);
    openPanel(n);
    // mark focus emphasis
    scene.querySelectorAll(".iw-focus").forEach((el) => el.classList.remove("iw-focus"));
    if (n.el) n.el.classList.add("iw-focus");
    // auto-fit camera to the node + its revealed children. Sectors fit slightly
    // zoomed-out (more margin) so the whole ring sits comfortably on the page.
    if (n.expanded && nodes.some((x) => x.parent === n.id)) fitSubtree(n, n.type === "sector" ? 0.78 : 0.85);
    else { const z = Math.max(cam.zoom, 1.1); camT = { x: W / 2 - n.x * z, y: H / 2 - n.y * z, zoom: z }; }
    if (hud) hud.style.opacity = "0";
    settle = 90; // let physics actively run after a change
  }

  // --- side panel ---

  // Coloured inline badge for the influence tier label.
  function influenceBadge(tk) { const l = influenceLabel(tk); const c = l === "High" ? "#EF4444" : l === "Medium" ? "#E9C46A" : "#14B8A6"; return `<span style="color:${c};font-weight:800">${l}</span>`; }

  // ThinkFree computed scores (Influence + Government Dependency).
  // Renders two meter bars if the TFScores module is loaded.
  function scoreBlock(tk) {
    if (!window.TFScores) return "";
    const inf = TFScores.influenceScore(tk), dep = TFScores.dependencyScore(tk);
    const meter = (label, v, hint, kind) => {
      const c = v >= 70 ? "#EF4444" : v >= 40 ? "#E9C46A" : "#14B8A6";
      return `<div class="iw-meter si" data-si-kind="${kind}" data-si-key="${E(tk)}" data-si-val="${v}"><div class="iw-meter-top"><span>${label} <span class="iw-dim" style="text-transform:none;letter-spacing:0;">${E(TFScores.label(v))}</span><i class="si-i">&#9432;</i></span><span>${v}/100</span></div>
        <div class="iw-meter-track"><div class="iw-meter-fill" style="width:${v}%;background:${c}"></div></div>
        <div class="iw-dim" style="font-size:10.5px;margin-top:3px;">${E(hint)}</div></div>`;
    };
    return `<div class="iw-sec">ThinkFree Scores</div>
      ${meter("Influence Score", inf, "Entanglement with government: contracts, bills, lobbying, congressional trading.", "company-influence")}
      ${meter("Government Dependency", dep, "Federal contract dollars relative to company revenue.", "company-dependency")}`;
  }

  // Real SEC EDGAR financials block (from bulk companyfacts), shown when available.
  function secFinancials(tk) {
    const f = SECB[tk];
    if (!f || (!f.revenue && !f.assets)) return "";
    return `<div class="iw-sec">Financials <span class="iw-dim" style="text-transform:none;letter-spacing:0;">SEC EDGAR${f.fy ? " FY" + f.fy : ""}</span></div>
      <div class="iw-grid3">
        <div class="iw-cell"><div class="l">Revenue</div><div class="v">${E(f.revenue_fmt || "n/a")}</div></div>
        <div class="iw-cell"><div class="l">Net Income</div><div class="v">${E(f.net_income_fmt || "n/a")}</div></div>
        <div class="iw-cell"><div class="l">Assets</div><div class="v">${E(f.assets_fmt || "n/a")}</div></div>
        <div class="iw-cell"><div class="l">Liabilities</div><div class="v">${E(f.liabilities_fmt || "n/a")}</div></div>
        <div class="iw-cell"><div class="l">SEC Filings</div><div class="v">${E(f.filings_total || "n/a")}</div></div>
        <div class="iw-cell"><div class="l">Industry</div><div class="v" style="font-size:11px;">${E((f.sic || "").slice(0, 22) || "n/a")}</div></div>
      </div>`;
  }

  // Populate the side panel HTML for whichever node was just focused.
  function openPanel(n) {
    let body = "";
    if (n.type === "congress") {
      body = `<div class="iw-eyebrow">Hub</div><h3>U.S. Congress</h3>
        <p class="iw-p">The root of the influence network. Legislation, regulation, spending, contracts, and oversight all trace back here.</p>
        <div class="iw-grid3"><div class="iw-cell"><div class="l">Sectors</div><div class="v">${SECTORS.length}</div></div><div class="iw-cell"><div class="l">Companies</div><div class="v">${Object.keys(IWD).length}</div></div><div class="iw-cell"><div class="l">Bills</div><div class="v">${(D.bills || []).length}</div></div></div>
        <p class="iw-hint">Click a sector to dive in.</p>`;
    } else if (n.type === "sector") {
      const comps = sectorCompanies(n.sec);
      body = `<div class="iw-eyebrow">Sector</div><h3>${E(n.sec.name)}</h3>
        <div class="iw-sec">Companies (${comps.length})</div>
        <div class="iw-cc">${comps.slice(0, 12).map((tk) => `<div class="iw-cc-item" data-co="${E(tk)}">${logo(tk)}<span>${E(tk)}</span></div>`).join("")}</div>
        <p class="iw-hint">Click the sector node to expand its companies on the graph.</p>`;
    } else if (n.type === "company") {
      const lis = IWD[n.ticker] || {};
      const sec = SECD[n.ticker] || {};
      const board = boardOf(n.ticker);
      const bills = billsByTicker[n.ticker] || [];
      const peers = currentSectorPeers(n.ticker);
      const k10 = sec.latest_10k;
      body = `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div>
        <div class="iw-eyebrow">${n.sensitive ? '<span style="color:#EF4444">High-Sensitivity</span>' : "Company"}</div>
        <h3>${E(compName(n.ticker))} <span class="iw-dim">${E(n.ticker)}</span></h3>
        <p class="iw-p">${E(lis.blurb || "Public company.")}</p>
        ${scoreBlock(n.ticker)}
        <div class="iw-grid3">
          <div class="iw-cell"><div class="l">Bills Tracked</div><div class="v">${bills.length}</div></div>
          <div class="iw-cell"><div class="l">Board (SEC)</div><div class="v">${board.length}</div></div>
          <div class="iw-cell"><div class="l">Congress Trades</div><div class="v">${tradeCount[n.ticker] || 0}</div></div>
          <div class="iw-cell"><div class="l">Shareholders</div><div class="v">${(lis.owners || []).length}</div></div>
          <div class="iw-cell"><div class="l">Fed Contracts</div><div class="v" style="font-size:13px;">${(USAD[n.ticker] && USAD[n.ticker].total_contracts_fmt) || "n/a"}</div></div>
          <div class="iw-cell"><div class="l">Employees</div><div class="v">${lis.employees ? Number(lis.employees).toLocaleString() : "n/a"}</div></div>
        </div>
        ${secFinancials(n.ticker)}
        <div class="iw-sec">Connected To Congress Through</div>
        <div class="iw-conn">
          <div class="iw-conn-row"><span class="iw-cdot" style="background:#E9C46A"></span><div><b>Lobbying</b><small>${lis.lda_registrant_id ? "Registered federal lobbyist (LDA " + E(lis.lda_registrant_id) + ")" : "Sector-level lobbying"}</small></div></div>
          <div class="iw-conn-row"><span class="iw-cdot" style="background:#E9C46A"></span><div><b>Campaign Contributions</b><small>Industry PAC and political spending</small></div></div>
          <div class="iw-conn-row"><span class="iw-cdot" style="background:#38BDF8"></span><div><b>Government Contracts</b><small>${(USAD[n.ticker] && USAD[n.ticker].total_contracts) ? E(USAD[n.ticker].total_contracts_fmt) + " in federal awards (2020-25)" : (lis.fedspending_id ? "Federal contractor" : "Indirect exposure")}</small></div></div>
          <div class="iw-conn-row"><span class="iw-cdot" style="background:#F59E0B"></span><div><b>Revolving Door</b><small>Board ties to former officials</small></div></div>
        </div>
        ${board.length ? `<div class="iw-sec">Board of Directors (${board.length}) ${sec.board ? '<span class="iw-dim" style="text-transform:none;letter-spacing:0;">via SEC ' + E(sec.filedAt || "") + "</span>" : ""}</div>
          <div class="iw-members">${board.slice(0, 6).map((m) => memberRow(m, n.ticker)).join("")}</div>
          ${board.length > 6 ? `<button class="iw-viewall" data-board="${E(n.ticker)}">View All ${board.length} Members</button>` : ""}` : ""}
        ${peers.length ? `<div class="iw-sec">Top Connected Companies</div><div class="iw-cc">${peers.slice(0, 6).map((tk) => `<div class="iw-cc-item" data-co="${E(tk)}">${logo(tk)}<span>${E(tk)}</span></div>`).join("")}</div>` : ""}
        ${k10 && k10.url ? `<div class="sample-note">Latest 10-K: <a class="bill-link" href="${E(k10.url)}" target="_blank" rel="noopener">${E(k10.filedAt)} ↗</a> (SEC EDGAR)</div>` : ""}`;
    } else if (n.type === "category") {
      body = categoryPanel(n);
    }
    panel.querySelector(".iw-panel-body").innerHTML = body;
    panel.classList.add("open");
  }

  // Returns all other companies in the same sector (for the "Top Connected" list).
  function currentSectorPeers(tk) {
    const sec = SECTORS.find((s) => (s.t || []).includes(tk));
    return sec ? sectorCompanies(sec).filter((x) => x !== tk) : [];
  }

  // A clickable board/exec member row that opens their person profile panel.
  function memberRow(m, fromTk) {
    const others = (personIndex[m.name] || []).length;
    const extra = [];
    if (m.independent) extra.push("Independent");
    if (m.age) extra.push("age " + m.age);
    if (m.committees && m.committees.length) extra.push(m.committees.slice(0, 2).join(", "));
    if (m.current === false) extra.push("former");
    if (others > 1) extra.push(others + " connections");
    return `<div class="iw-member iw-clickable" data-exec="${E(m.name)}" data-from="${E(fromTk)}">
      <span class="iw-av">${E(initials(m.name))}</span>
      <div><div class="iw-mname">${E(m.name)}</div><div class="iw-mtitle">${E(m.title || "Director")}${extra.length ? " · " + E(extra.join(" · ")) : ""}</div></div>
      <span class="iw-chev">&rsaquo;</span>
    </div>`;
  }

  // Full Board of Directors list panel (does NOT navigate the graph).
  // Used by the "View All N Members" button on the company panel.
  function boardListPanel(tk) {
    const board = boardOf(tk);
    const src = (SECD[tk] && SECD[tk].board) ? "SEC EDGAR (current)" : "LittleSis";
    panel.querySelector(".iw-panel-body").innerHTML = `
      <div class="iw-back" data-copanel="${E(tk)}">&lsaquo; Back to ${E(compName(tk))}</div>
      <div class="iw-eyebrow">${E(compName(tk))}</div><h3>Board of Directors</h3>
      <p class="iw-p">${board.length} members. Click a name to view their background and history. Source: ${E(src)}.</p>
      <div class="iw-members">${board.map((m) => memberRow(m, tk)).join("") || "<p class='iw-hint'>No board data.</p>"}</div>`;
    panel.classList.add("open");
  }

  // Person profile panel: background + current + previous history.
  // Back button returns to the Board of Directors list (not out to the company).
  function personPanel(name, fromTk) {
    const entries = personIndex[name] || [];
    const cur = entries.filter((e) => e.current !== false);
    const prev = entries.filter((e) => e.current === false);
    // pull title/age/committees from the SEC board record we came from
    let meta = null;
    if (fromTk) meta = boardOf(fromTk).find((m) => m.name === name);
    const homeCo = fromTk ? compName(fromTk) : (entries[0] && entries[0].company) || "";
    const homeTitle = (meta && meta.title) || (entries[0] && (entries[0].title || entries[0].role)) || "Director";
    const bgBits = [];
    if (meta) {
      if (meta.title) bgBits.push(meta.title);
      if (meta.independent) bgBits.push("Independent director");
      if (meta.age) bgBits.push("age " + meta.age);
      if (meta.committees && meta.committees.length) bgBits.push("Committees: " + meta.committees.join(", "));
    }
    const background = `${E(name)} serves as ${E(homeTitle)} at ${E(homeCo)}.` +
      (bgBits.length ? " " + E(bgBits.join(" · ")) + "." : "") +
      ` This profile maps ${entries.length} disclosed affiliation${entries.length === 1 ? "" : "s"} across companies tracked in InfluenceWeb.`;
    const item = (e, isPrev) => `<div class="iw-member iw-clickable" data-conn="1" data-cn="${E(name)}" data-ct="${E(e.ticker)}" data-ctitle="${E(e.title || e.role)}" data-ccur="${isPrev ? "0" : "1"}" data-cfrom="${E(fromTk || "")}">
      <span class="iw-av" style="${isPrev ? "background:rgba(245,158,11,.18);color:#F59E0B" : ""}">${E(initials(name))}</span>
      <div><div class="iw-mname">${E(e.company)} <span class="iw-dim">${E(e.ticker)}</span></div>
      <div class="iw-mtitle">${E(e.title || e.role)}${isPrev ? ' <span class="iw-rd">Revolving Door</span>' : ""}</div></div>
      <span class="iw-chev">&rsaquo;</span></div>`;
    panel.querySelector(".iw-panel-body").innerHTML = `
      ${fromTk ? `<div class="iw-back" data-boardback="${E(fromTk)}">&lsaquo; Back to Board of Directors</div>` : ""}
      <div class="profile-head" style="align-items:center;gap:14px;">
        <span class="iw-av" style="width:54px;height:54px;font-size:18px;">${E(initials(name))}</span>
        <div><div class="iw-eyebrow">Board Member</div><h3 style="margin:2px 0 0;">${E(name)}</h3></div>
      </div>
      <div class="iw-sec">Background</div>
      <p class="iw-p">${background}</p>
      <div class="iw-sec">Current Positions (${cur.length})</div>
      <div class="iw-members">${cur.map((e) => item(e, false)).join("") || "<p class='iw-hint'>None on record.</p>"}</div>
      ${prev.length ? `<div class="iw-sec">Previous History (${prev.length})</div><div class="iw-members">${prev.map((e) => item(e, true)).join("")}</div>` : `<div class="iw-sec">Previous History</div><p class="iw-hint">No prior affiliations on record in our data.</p>`}`;
    panel.classList.add("open");
  }

  // Explain a single person-company connection.
  // "Previous" connections get the revolving-door framing (career transition, no wrongdoing implied).
  function connectionDetail(name, tk, title, isCurrent, fromTk) {
    const co = compName(tk);
    const explain = isCurrent
      ? `${name} currently serves as ${title} at ${co} (${tk}). This is an active position: the individual sits on the leadership of the company while it engages with government through lobbying, contracts, and related legislation.`
      : `${name} previously served as ${title} at ${co} (${tk}). This is a revolving-door relationship: the individual has moved between organizations, carrying relationships, knowledge, and influence with them. It describes a career transition only and does not imply wrongdoing.`;
    panel.querySelector(".iw-panel-body").innerHTML = `
      <div class="iw-back" data-exec="${E(name)}" data-from="${E(fromTk || "")}">&lsaquo; Back to ${E(name)}</div>
      <div class="iw-eyebrow" style="${isCurrent ? "" : "color:#F59E0B"}">${isCurrent ? "Active Connection" : "Revolving Door"}</div>
      <h3>${E(name)} · ${E(co)}</h3>
      <div class="iw-conn-row" style="border:none;padding-top:0;"><span class="iw-cdot" style="background:${isCurrent ? "#6B7A90" : "#F59E0B"}"></span><div><b>${E(title)}</b><small>${isCurrent ? "Current role" : "Former role"}</small></div></div>
      <p class="iw-p">${E(explain)}</p>
      <div class="iw-cc"><div class="iw-cc-item" data-co="${E(tk)}">${logo(tk)}<span>Open ${E(tk)} on the map</span></div></div>`;
    panel.classList.add("open");
  }

  // Static "How InfluenceWeb Works" guide panel triggered by the ? button.
  function howtoPanel() {
    panel.querySelector(".iw-panel-body").innerHTML = `
      <div class="iw-eyebrow">Guide</div><h3>How InfluenceWeb Works</h3>
      <p class="iw-p">A living map of how money, policy, and power connect, all tracing back to Congress.</p>
      <div class="iw-sec">Navigate</div>
      <ul class="iw-list">
        <li><b>Click</b> a node to expand it outward into the next level.</li>
        <li><b>Click again</b> to retract that branch.</li>
        <li><b>Scroll</b> to zoom, <b>drag</b> to pan. Use the breadcrumb to jump back.</li>
      </ul>
      <div class="iw-sec">Levels</div>
      <ul class="iw-list">
        <li>Congress &rsaquo; Sector &rsaquo; Company &rsaquo; Board / Shareholders / Politics / Bills</li>
        <li>Click a board member to see their other connections.</li>
      </ul>
      <div class="iw-sec">Colors</div>
      <ul class="iw-list">
        <li><span class="iw-cdot" style="background:#E5E9F0"></span> Company &nbsp; <span class="iw-cdot" style="background:#38BDF8"></span> Government</li>
        <li><span class="iw-cdot" style="background:#EF4444"></span> Political &nbsp; <span class="iw-cdot" style="background:#E9C46A"></span> Financial &nbsp; <span class="iw-cdot" style="background:#14B8A6"></span> Other</li>
      </ul>
      <p class="iw-hint">This tool shows verified public relationships. It does not imply or allege wrongdoing.</p>`;
    panel.classList.add("open");
  }

  // Filters panel: toggle cross-links on/off and display the legend.
  function filtersPanel() {
    panel.querySelector(".iw-panel-body").innerHTML = `
      <div class="iw-eyebrow">Filters</div><h3>Graph Filters</h3>
      <p class="iw-p">Control what relationships appear on the map.</p>
      <label class="iw-toggle"><input type="checkbox" id="iw-tg-xlinks" ${showXlinks ? "checked" : ""}/> <span>Cross-links (companies sharing major shareholders)</span></label>
      <div class="iw-sec">Relationship Legend</div>
      <div class="iw-conn">
        <div class="iw-conn-row"><span class="iw-cdot" style="background:#6B7A90"></span><div><b>Structural</b><small>Belongs to / sits on board / regulates</small></div></div>
        <div class="iw-conn-row"><span class="iw-cdot" style="background:#14B8A6"></span><div><b>Financial</b><small>PAC, donations, contracts, lobbying</small></div></div>
        <div class="iw-conn-row"><span class="iw-cdot" style="background:#8B5CF6"></span><div><b>Legislative</b><small>Bills, committees, agencies</small></div></div>
        <div class="iw-conn-row"><span class="iw-cdot" style="background:#EF4444"></span><div><b>High-Sensitivity</b><small>Multiple public relationships overlap</small></div></div>
      </div>`;
    panel.classList.add("open");
    const tg = document.getElementById("iw-tg-xlinks");
    if (tg) tg.addEventListener("change", () => { showXlinks = tg.checked; rebuild(); });
  }

  // Build and return the HTML for a category panel (board, shareholders, political, etc.).
  function categoryPanel(n) {
    const tk = n.ticker, lis = IWD[tk] || {};
    if (n.cat === "board") {
      const board = boardOf(tk);
      const src = (SECD[tk] && SECD[tk].board) ? "SEC EDGAR (current)" : "LittleSis";
      return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back to ${E(compName(tk))}</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>Board of Directors</h3>
        <p class="iw-p">${board.length} members. Click a name to see their other connections. Source: ${E(src)}.</p>
        <div class="iw-members">${board.map((m) => memberRow(m, tk)).join("") || "<p class='iw-hint'>No board data.</p>"}</div>`;
    }
    if (n.cat === "shareholders") {
      const ow = lis.owners || [];
      return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>Major Shareholders</h3>
        <div class="iw-members">${ow.map((o) => `<div class="iw-member"><span class="iw-av" style="background:rgba(233,196,106,.18);color:#E9C46A">${E(initials(o.name))}</span><div><div class="iw-mname">${E(o.name)}</div><div class="iw-mtitle">${E(o.title || "Shareholder")}</div></div></div>`).join("") || "<p class='iw-hint'>No shareholder data.</p>"}</div>`;
    }
    if (n.cat === "political") {
      const t = politicalTies(tk); const co = compName(tk);
      const usa = USAD[tk] || {};
      const chips = (arr, cls) => `<div class="iw-cc">${arr.map((x) => `<div class="iw-cc-item"><span class="iw-av sm" ${cls || ""}>${E(initials(x))}</span><span>${E(x)}</span></div>`).join("")}</div>`;
      let html = `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(co)}</div><h3>Political Connections (${t.count})</h3>`;
      // each section explains HOW the company is connected
      if (t.filings) html += `<p class="iw-p">${E(co)} filed <b>${t.filings}</b> federal lobbying disclosures${t.spend ? ", spending about <b>" + E(t.spend) + "</b>" : ""}.</p>`;
      if (t.firms.length) {
        html += `<div class="iw-sec">Lobbying firms it hires (${t.firms.length})</div><p class="iw-hint">Outside firms ${E(co)} pays to lobby Congress on its behalf.</p>${chips(t.firms, 'style="background:rgba(233,196,106,.16);color:#E9C46A"')}`;
      }
      if (t.bills.length) {
        html += `<div class="iw-sec">Bills it lobbies on (${t.bills.length})</div><p class="iw-hint">Specific legislation ${E(co)}'s lobbyists worked on.</p><div class="iw-chips">${t.bills.map((b) => `<span class="iw-chip">${E(b)}</span>`).join("")}</div>`;
      }
      if (t.issues.length) {
        html += `<div class="iw-sec">Issues it lobbies on (${t.issues.length})</div><div class="iw-chips">${t.issues.map((i) => `<span class="iw-chip">${E(i)}</span>`).join("")}</div>`;
      }
      if (t.lobbyists.length) {
        html += `<div class="iw-sec">Registered lobbyists (${t.lobbyists.length})</div><p class="iw-hint">People who lobbied the federal government for ${E(co)}.</p>${chips(t.lobbyists)}`;
      }
      // congressional trades
      html += `<div class="iw-sec">Members of Congress${t.traders.length ? " (" + t.traders.length + ")" : ""}</div>`;
      html += t.traders.length
        ? `<p class="iw-hint">Have disclosed personal trades in ${E(tk)} stock.</p><div class="iw-cc">${t.traders.map((p) => `<div class="iw-cc-item" data-person="${E(p)}"><span class="iw-av sm">${E(initials(p))}</span><span>${E(p)}</span></div>`).join("")}</div>`
        : `<p class="iw-hint">No disclosed congressional trades.</p>`;
      // industry / business associations
      html += `<div class="iw-sec">Industry &amp; business groups (${t.industry.length})</div><p class="iw-hint">Associations that lobby on behalf of ${E(co)}'s industry.</p>`;
      html += `<div class="iw-cc">${t.industry.map((nm) => { const np = NPD[nm]; return `<div class="iw-cc-item"><span class="iw-av sm" style="background:rgba(20,184,166,.16);color:#14B8A6">${E(initials((np && np.name) || nm))}</span><span>${E((np && np.name) || nm)}</span></div>`; }).join("")}</div>`;
      if (t.contracts) html += `<div class="iw-sec">Government contracts</div><p class="iw-p">Holds ${usa.total_contracts_fmt ? E(usa.total_contracts_fmt) + " in federal contracts" : "federal contracts"}${(usa.top_agencies && usa.top_agencies[0]) ? ", mostly from the " + E(usa.top_agencies[0].agency) : ""}.</p>`;
      html += `<p class="iw-hint" style="margin-top:10px;">Public lobbying, trading, and contracting relationships. Does not imply wrongdoing.</p>`;
      return html;
    }
    if (n.cat === "bills") {
      const bills = billsByTicker[tk] || [];
      return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>Related Legislation (${bills.length})</h3>
        <div class="iw-cc">${bills.map((b) => `<div class="iw-cc-item" data-bill="${E(b.bill_id)}"><span class="iw-av sm" style="background:rgba(129,140,248,.18);color:#818CF8">B</span><span>${E(b.bill_id)}</span></div>`).join("") || "<p class='iw-hint'>None.</p>"}</div>`;
    }
    if (n.cat === "lobbying") {
      const sec = SECTORS.find((s) => (s.t || []).includes(tk));
      const names = [...new Set([...(SECTOR_LOBBY[sec && sec.name] || []), ...CROSS_LOBBY])];
      const rows = names.map((nm) => {
        const np = NPD[nm]; if (!np) return "";
        return `<div class="iw-member"><span class="iw-av" style="background:rgba(20,184,166,.16);color:#14B8A6">${E(initials(np.name || nm))}</span>
          <div style="flex:1;"><div class="iw-mname">${E(np.name || nm)}</div>
          <div class="iw-mtitle">Revenue ${E(np.revenue_fmt || "n/a")}${np.year ? " (" + E(np.year) + ")" : ""} · EIN ${E(np.ein)}</div></div>
          <a class="iw-chev" href="${E(np.url)}" target="_blank" rel="noopener" title="ProPublica 990">&rsaquo;</a></div>`;
      }).join("");
      return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>Lobbying &amp; Industry Groups</h3>
        <p class="iw-p">${lis.lda_registrant_id ? "Registered federal lobbyist (Senate LDA id " + E(lis.lda_registrant_id) + ")." : "Lobbies through these industry groups."} Group financials are real IRS Form 990 filings.</p>
        <div class="iw-members">${rows || "<p class='iw-hint'>No industry-group financials mapped.</p>"}</div>
        <div class="sample-note">Source: ProPublica Nonprofit Explorer (IRS 990).</div>`;
    }
    // Government Contracts (real USASpending dollars)
    const usa = USAD[tk];
    if (usa && usa.total_contracts) {
      const ag = (usa.top_agencies || []).map((a) => `<div class="iw-member"><span class="iw-av" style="background:rgba(56,189,248,.16);color:#38BDF8">${E(initials(a.agency || "?"))}</span>
        <div style="flex:1;"><div class="iw-mname">${E(a.agency)}</div><div class="iw-mtitle">${E(a.amount_fmt)}</div></div></div>`).join("");
      return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>Federal Contracts</h3>
        <div class="iw-meter"><div class="iw-meter-top"><span>Total Awards (2020-2025)</span><span>${E(usa.total_contracts_fmt)}</span></div></div>
        <div class="iw-sec">Top Awarding Agencies</div>
        <div class="iw-members">${ag || "<p class='iw-hint'>No agency breakdown.</p>"}</div>
        <div class="sample-note">Source: USASpending.gov. <a class="bill-link" href="${E(usa.url)}" target="_blank" rel="noopener">View all awards ↗</a></div>`;
    }
    return `<div class="iw-back" data-up="${n.parent}">&lsaquo; Back</div><div class="iw-eyebrow">${E(compName(tk))}</div><h3>${E(n.label)}</h3>
      <p class="iw-p">${lis.fedspending_id ? "Registered federal contractor (USASpending id " + E(lis.fedspending_id) + ")." : "No significant federal contracts on record (2020-2025)."}</p>`;
  }

  // Render a small company logo or 3-letter initials fallback for panel chip lists.
  function logo(tk) {
    const d = IWD[tk] && IWD[tk].domain;
    return d ? `<img class="iw-cc-logo" alt="${E(tk)} logo" src="https://logo.clearbit.com/${E(d)}" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'iw-av sm',textContent:'${E(tk).slice(0,3)}'}))"/>` : `<span class="iw-av sm">${E(tk).slice(0, 3)}</span>`;
  }

  // Hide the side panel.
  function closePanel() { panel.classList.remove("open"); }

  // --- interaction ---

  // Attach all mouse/wheel/click event listeners to the canvas and panel.
  function bind() {
    // Scroll to zoom, anchored at the cursor position so the point under the
    // cursor stays stationary (standard map-zoom UX).
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const w = s2w(mx, my);
      cam.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, cam.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
      cam.x = mx - w.x * cam.zoom; cam.y = my - w.y * cam.zoom; camT = null;
    }, { passive: false });

    // Drag to pan: record start position and camera offset so we can compute delta.
    canvas.addEventListener("mousedown", (e) => {
      const r = canvas.getBoundingClientRect();
      drag = { sx: e.clientX, sy: e.clientY, cx: cam.x, cy: cam.y, moved: false };
    });
    window.addEventListener("mousemove", (e) => {
      if (drag) {
        const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
        if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
        if (drag.moved) { cam.x = drag.cx + dx; cam.y = drag.cy + dy; camT = null; canvas.style.cursor = "grabbing"; }
      }
    });
    window.addEventListener("mouseup", () => { drag = null; canvas.style.cursor = "grab"; });

    // Click on a node: delegate expansion/collapse and panel logic through focus().
    scene.addEventListener("click", (e) => {
      if (drag && drag.moved) return;
      const el = e.target.closest(".iw-node");
      if (!el) return;
      const n = nodeById[el.dataset.id]; if (!n) return;
      if (n.type === "more") { revealMore(n); return; }
      // Congress -> animated zoom into the node, then open the branches-of-power drill-down
      if (n.type === "congress" && window.CongressDrill) {
        if (window.IW && window.IW.zoomToCongress) window.IW.zoomToCongress(() => window.CongressDrill.open());
        else window.CongressDrill.open();
        return;
      }
      // toggle: if already expanded, clicking retracts its branch (root stays open)
      if (n.type !== "congress" && n.expanded && nodes.some((x) => x.parent === n.id)) {
        collapse(n);
        if (n.type === "sector") focusedSector = null;   // un-fade the other sectors
        rebuild();
        selectedId = n.id;
        if (n.el) n.el.classList.add("iw-focus");
        setBreadcrumb(n);
        const p = n.parent != null ? nodeById[n.parent] : null;
        fitSubtree(p && p.expanded ? p : n);
        settle = 80;
        return;
      }
      focus(n);
    });

    // Hover: highlight the node and its direct neighbours; dim everything else.
    scene.addEventListener("mouseover", (e) => {
      const el = e.target.closest(".iw-node"); if (!el) return;
      const n = nodeById[el.dataset.id]; if (!n) return;
      highlight(n.id, true); showTip(n, e);
    });
    scene.addEventListener("mouseout", (e) => {
      const el = e.target.closest(".iw-node"); if (!el) return;
      highlight(null); tip.classList.remove("open");
    });

    // Panel delegated click handler: handles back buttons, board links, person links, etc.
    panel.addEventListener("click", (e) => {
      const cn = e.target.closest("[data-conn]"); if (cn) return connectionDetail(cn.dataset.cn, cn.dataset.ct, cn.dataset.ctitle, cn.dataset.ccur === "1", cn.dataset.cfrom);
      const bb = e.target.closest("[data-boardback]"); if (bb) return boardListPanel(bb.dataset.boardback);   // person -> back to board list
      const cp = e.target.closest("[data-copanel]"); if (cp) { const node = nodes.find((x) => x.type === "company" && x.ticker === cp.dataset.copanel); if (node) return openPanel(node); }  // board list -> back to company panel (no graph nav)
      const ex = e.target.closest("[data-exec]"); if (ex) return personPanel(ex.dataset.exec, ex.dataset.from);
      const co = e.target.closest("[data-co]"); if (co) { const node = nodes.find((x) => x.type === "company" && x.ticker === co.dataset.co); if (node) return focus(node); const sn = nodes.find((x) => x.type === "sector" && (x.sec.t || []).includes(co.dataset.co)); if (sn) { focus(sn); } return; }
      const pr = e.target.closest("[data-person]"); if (pr && window.politicianProfile) return window.politicianProfile(pr.dataset.person);
      const bl = e.target.closest("[data-bill]"); if (bl && window.billDetail) return window.billDetail(bl.dataset.bill);
      const up = e.target.closest("[data-up]"); if (up && nodeById[up.dataset.up]) return focus(nodeById[up.dataset.up]);
      const ba = e.target.closest("[data-board]"); if (ba) return boardListPanel(ba.dataset.board);   // View All -> board list panel
    });
    panel.querySelector(".iw-panel-close").addEventListener("click", closePanel);

    document.getElementById("iw-breadcrumb").addEventListener("click", (e) => { const c = e.target.closest("[data-cr]"); if (c && nodeById[c.dataset.cr]) focus(nodeById[c.dataset.cr]); });
    document.getElementById("iw-zin").addEventListener("click", () => zoomBtn(1.25));
    document.getElementById("iw-zout").addEventListener("click", () => zoomBtn(0.8));
    document.getElementById("iw-fit").addEventListener("click", reset);
    const ht = document.getElementById("iw-howto"); if (ht) ht.addEventListener("click", howtoPanel);
    const ff = document.getElementById("iw-filters"); if (ff) ff.addEventListener("click", filtersPanel);
  }

  // Zoom in or out centered on the viewport midpoint (used by the +/- buttons).
  function zoomBtn(f) {
    const w = s2w(W / 2, H / 2);
    cam.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, cam.zoom * f));
    cam.x = W / 2 - w.x * cam.zoom; cam.y = H / 2 - w.y * cam.zoom; camT = null;
  }

  // Apply hover emphasis: dim all nodes/edges except the focused node and its neighbours.
  function highlight(id) {
    if (!id) { scene.querySelectorAll(".iw-node,.iw-line").forEach((el) => el.classList.remove("iw-dim", "iw-hot")); return; }
    const conn = new Set([id]);
    edges.forEach((e) => { if (e.a === id) conn.add(e.b); if (e.b === id) conn.add(e.a); });
    scene.querySelectorAll(".iw-node").forEach((el) => el.classList.toggle("iw-dim", !conn.has(el.dataset.id)));
    edgesSvg.querySelectorAll(".iw-line").forEach((el) => {
      const on = el.dataset.a === id || el.dataset.b === id;
      el.classList.toggle("iw-hot", on); el.classList.toggle("iw-dim", !on);
    });
  }

  // Show the floating tooltip near the cursor with a brief summary of the node.
  function showTip(n, e) {
    const r = canvas.getBoundingClientRect();
    let sub = "";
    if (n.type === "sector") sub = `${sectorCompanies(n.sec).length} companies`;
    else if (n.type === "company") sub = `${compName(n.ticker)} · Influence: ${influenceLabel(n.ticker)}${n.sensitive ? " · High-sensitivity" : ""}`;
    else if (n.type === "category") sub = n.sub || "";
    else sub = "The influence hub";
    tip.innerHTML = `<div class="iw-tip-t">${E(n.type === "company" ? n.ticker : (n.type === "congress" ? "U.S. Congress" : n.label))}</div><div class="iw-tip-s">${E(sub)}</div>`;
    tip.style.left = (e.clientX - r.left + 16) + "px"; tip.style.top = (e.clientY - r.top + 16) + "px";
    tip.classList.add("open");
  }

  // Reset the graph to its initial state: one Congress hub surrounded by sector nodes.
  function reset() {
    nodes = []; edges = []; nodeById = {}; seq = 0; selectedId = null; focusedSector = null;
    const c = addNode({ type: "congress", colorType: "government", label: "Congress", icon: "congress", x: 0, y: 0, angle: -Math.PI / 2 });
    c.size = sizeForType(c);
    // set parents for breadcrumb
    expandCongress(c);
    nodes.filter((n) => n.type === "sector").forEach((s) => (s.parent = c.id));
    rebuild();
    cam = { x: W / 2, y: H / 2, zoom: 0.45 };
    fitSubtree(c);
    settle = 140;
    setBreadcrumb(c);
    closePanel();
    if (hud) hud.style.opacity = "1";
  }

  // Main animation loop: advances physics, interpolates the camera, and syncs the DOM.
  function loop() {
    requestAnimationFrame(loop);
    if (!active) return;
    // physics: run while settling (after a change) or if anything still moving
    if (nodes.length) {
      const moving = physics();
      syncDOM();
      if (settle > 0) settle--;
      else if (moving < 0.6) { /* settled, idle */ }
    }
    if (camT) {
      cam.x += (camT.x - cam.x) * 0.1; cam.y += (camT.y - cam.y) * 0.1; cam.zoom += (camT.zoom - cam.zoom) * 0.1;
      if (Math.abs(camT.x - cam.x) < 0.5 && Math.abs(camT.zoom - cam.zoom) < 0.004) camT = null;
    }
    applyCam();
  }

  // Update W/H to the current canvas size (called on init and window resize).
  function size() { const r = canvas.getBoundingClientRect(); W = r.width; H = r.height; edgesSvg.setAttribute("width", 1); edgesSvg.setAttribute("height", 1); }

  // Public API exposed as window.IW so app.js can activate/deactivate this module
  // as the user switches between tabs.
  window.IW = {
    activate() {
      scene = document.getElementById("iw-scene");
      edgesSvg = document.getElementById("iw-edges");
      canvas = document.getElementById("iw-canvas");
      panel = document.getElementById("iw-panel");
      tip = document.getElementById("iw-tip");
      hud = document.getElementById("iw-hud");
      if (!scene) return;
      if (!started) { indexData(); size(); bind(); reset(); window.addEventListener("resize", () => { if (active) size(); }); started = true; requestAnimationFrame(loop); }
      active = true; size();
      if (!nodes.length) reset(); else applyCam();
    },
    deactivate() { active = false; if (tip) tip.classList.remove("open"); },
    // Animated zoom toward the Congress hub: sectors fade back, camera pushes in,
    // then the callback (open the drill overlay) fires once the push completes.
    zoomToCongress(cb) {
      const c = nodes.find((n) => n.type === "congress");
      if (!c || !scene) { cb && cb(); return; }
      if (!preZoomCam) preZoomCam = { x: cam.x, y: cam.y, zoom: cam.zoom };
      nodes.forEach((n) => { if (n.el) { n.el.style.transition = "opacity .45s ease"; n.el.style.opacity = n.type === "congress" ? "1" : "0.06"; } });
      if (edgesSvg) edgesSvg.querySelectorAll(".iw-line").forEach((el) => { el.style.transition = "opacity .45s ease"; el.style.opacity = "0.04"; });
      const z = 2.4;
      camT = { x: W / 2 - c.x * z, y: H / 2 - c.y * z, zoom: z };
      if (hud) hud.style.opacity = "0";
      setTimeout(() => { cb && cb(); }, 540);
    },
    // Reverse the Congress zoom (called when the drill overlay closes).
    zoomOut() {
      nodes.forEach((n) => { if (n.el) n.el.style.opacity = "1"; });
      if (edgesSvg) edgesSvg.querySelectorAll(".iw-line").forEach((el) => { el.style.opacity = ""; });
      if (preZoomCam) { camT = preZoomCam; preZoomCam = null; }
      if (hud) hud.style.opacity = "1";
    },
    // Hard reset back to the default graph (close drill, clear zoom, rebuild).
    // Used when closing the drill and when re-entering the InfluenceWeb page.
    resetView() {
      const d = document.getElementById("iw-drill"); if (d) d.classList.remove("open");
      preZoomCam = null;
      if (scene) reset();
    },
    // Open a specific company: find its sector, expand to it, then focus the company node.
    openCompany(tk) {
      this.activate();
      const sec = SECTORS.find((s) => (s.t || []).includes(tk));
      if (!sec) return;
      const congress = nodes.find((n) => n.type === "congress");
      const sn = nodes.find((n) => n.type === "sector" && n.sec === sec);
      if (sn) {
        focus(sn);
        // after the sector expands, focus the company node
        setTimeout(() => {
          const cn = nodes.find((n) => n.type === "company" && n.ticker === tk);
          if (cn) focus(cn);
          else { // company beyond the top-12; reveal more then focus
            const more = nodes.find((n) => n.type === "more" && nodeById[n.moreOf] === sn);
            if (more) { revealMore(more); setTimeout(() => { const c2 = nodes.find((n) => n.type === "company" && n.ticker === tk); if (c2) focus(c2); }, 120); }
          }
        }, 120);
      }
    },
  };
})();
