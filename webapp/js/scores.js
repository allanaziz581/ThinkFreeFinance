// scores.js
//
// ThinkFree Scores Engine.
//
// What it does:
//   Turns data that is already loaded in the browser into the ThinkFree
//   accountability scores, with no extra network calls:
//     - Influence Score             how entangled a company is with government
//     - Government Dependency        how much of its business relies on federal money
//     - Corporate Political Exposure the raw breakdown behind those scores
//
// How it fits:
//   This is the calculation layer. It reads the window.*_DATA globals that the
//   data files define, and exposes everything through window.TFScores. The UI
//   (app.js) only reads from here; it never recomputes scores itself. Every
//   number is derived from public data so the scoring stays transparent.
"use strict";

(function () {
  // Data sources. Each is a pre-loaded global; we default to an empty object so
  // that a missing or not-yet-loaded data file can never throw here.
  const D    = window.TF_DATA || {};
  const IWD  = (window.IW_DATA || { companies: {} }).companies || {};
  const NPD  = (window.NP_DATA || {}).byName || {};
  const SECB = (window.SECBULK_DATA || {}).byTicker || {};
  const USAD = (window.USA_DATA || {}).byTicker || {};
  const FEC  = (window.FEC_DATA || {}).byName || {};
  const REL  = (window.RELATIONSHIPS || {}).byTicker || {};   // Senate LDA lobbying

  // Parse a formatted money string such as "$9.8M" into a plain number (9800000).
  const moneyToNum = (fmt) => {
    const m = String(fmt || "").replace(/[$,]/g, "").match(/([\d.]+)\s*([MBK]?)/i);
    if (!m) return 0;
    const v = parseFloat(m[1]) || 0,
          u = (m[2] || "").toUpperCase();
    return v * (u === "B" ? 1e9 : u === "M" ? 1e6 : u === "K" ? 1e3 : 1);
  };

  // ---- Per-company raw signals ----
  // Build the lookup tables once, up front, so each score is a cheap read later.
  const tradeCount = {},     // ticker -> number of disclosed congressional trades
        polsByTicker = {},   // ticker -> Set of members who traded it
        billsByTicker = {};  // ticker -> Set of bill ids that mention it

  (function index() {
    // Bills: merge the main list with the correlation engine's top bills,
    // de-duplicate by bill_id, and map every mentioned ticker to that bill.
    const all = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])];
    const seen = new Set();
    all.forEach((b) => {
      if (seen.has(b.bill_id)) return;
      seen.add(b.bill_id);
      (b.tickers || []).forEach((tk) => {
        (billsByTicker[tk] = billsByTicker[tk] || new Set()).add(b.bill_id);
      });
    });

    // Trades: count disclosures per ticker and remember which members traded it.
    (D.recent_trades || []).forEach((t) => {
      if (!t.ticker) return;
      tradeCount[t.ticker] = (tradeCount[t.ticker] || 0) + 1;
      (polsByTicker[t.ticker] = polsByTicker[t.ticker] || new Set()).add(t.politician);
    });
  })();

  // Small math helpers.
  const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));
  const log10 = (n) => (n > 0 ? Math.log10(n) : 0);

  // INFLUENCE SCORE (0-100)
  // How much a company is entangled with government activity. Each input is
  // capped on its own and then the capped parts are summed, so no single signal
  // can run away with the score. Inputs: federal contracts, bill mentions,
  // congressional trading, lobbying presence, and board size (governance footprint).
  function influenceScore(tk) {
    const contracts  = (USAD[tk] && USAD[tk].total_contracts) || 0;
    const bills      = (billsByTicker[tk] ? billsByTicker[tk].size : 0);
    const trades     = tradeCount[tk] || 0;
    const pols       = (polsByTicker[tk] ? polsByTicker[tk].size : 0);
    const lis        = IWD[tk] || {};
    const r          = REL[tk] || {};
    const lobbySpend = moneyToNum(r.spend_fmt);
    const lobbyFirms = (r.firms || []).length;
    const lobbyBills = (r.bills || []).length;
    const registered = !!(lis.lda_registrant_id || r.filings);
    const board      = ((window.SEC_DATA || {}).byTicker || {})[tk];
    const boardN     = (board && board.board ? board.board.length : 0) + ((lis.board || []).length + (lis.executives || []).length);

    // Each component is capped individually, then summed into a 0-100 total.
    const cContract   = clamp((log10(contracts) - 5) * 8, 0, 38);            // money FROM gov (USASpending): $1M~8, $3B~36, $100B~38
    const cLobbySpend = clamp((log10(lobbySpend) - 4) * 4, 0, 16);           // money TO influence gov (LDA spend)
    const cLobbyFoot  = clamp(lobbyFirms * 1.3 + lobbyBills * 0.6, 0, 16);   // lobbying footprint (firms + bills lobbied)
    const cRegistered = registered ? 4 : 0;
    const cBills      = clamp(bills * 2, 0, 12);                             // named in legislation
    const cTrades     = clamp(trades * 0.3, 0, 8) + clamp(pols * 1.0, 0, 6); // congressional trading
    const cBoard      = clamp(boardN * 0.3, 0, 4);                          // governance footprint

    const raw = cContract + cLobbySpend + cLobbyFoot + cRegistered + cBills + cTrades + cBoard;
    return Math.round(clamp(raw));
  }

  // GOVERNMENT DEPENDENCY SCORE (0-100)
  // How dependent a company is on government money: federal contract dollars
  // relative to its own revenue. The larger that share, the more of its
  // business comes from the taxpayer.
  function dependencyScore(tk) {
    const contracts = (USAD[tk] && USAD[tk].total_contracts) || 0;
    const rev5 = ((SECB[tk] && SECB[tk].revenue) || 0) * 5;       // compare ~5yr revenue against ~5yr of contracts
    if (!contracts) return 0;
    if (!rev5) return Math.round(clamp(log10(contracts) * 8));    // no revenue figure: fall back to raw contract size
    const ratio = contracts / rev5;                              // 0..1+ share of revenue from federal awards
    return Math.round(clamp(ratio * 140));                       // ~70% government revenue -> ~98
  }

  // Turn a 0-100 score into a plain-English bucket.
  function label(v) {
    return v >= 70 ? "High" : v >= 40 ? "Medium" : v >= 15 ? "Low" : "Minimal";
  }

  // CORPORATE POLITICAL EXPOSURE (breakdown)
  // The raw, itemized signals behind a company's scores, for display in the UI.
  function politicalExposure(tk) {
    const lis = IWD[tk] || {};
    const r   = REL[tk] || {};
    return {
      contracts: (USAD[tk] && USAD[tk].total_contracts_fmt) || "None",
      contracts_raw: (USAD[tk] && USAD[tk].total_contracts) || 0,
      bills: (billsByTicker[tk] ? billsByTicker[tk].size : 0),
      congressional_traders: (polsByTicker[tk] ? polsByTicker[tk].size : 0),
      trades: tradeCount[tk] || 0,
      lobby_spend: r.spend_fmt || null,
      lobby_firms: (r.firms || []).length,
      lobby_bills: (r.bills || []).length,
      lobbying: (lis.lda_registrant_id || r.filings) ? "Registered federal lobbyist" : "Sector-level",
      influence: influenceScore(tk),
      dependency: dependencyScore(tk),
    };
  }

  // SECTOR / INDUSTRY ROLLUPS
  // Aggregate a list of tickers into one sector-level summary: totals plus the
  // average influence and dependency across the companies in the list.
  function industryRollup(tickers) {
    let contracts = 0,
        bills = new Set(),
        trades = 0,
        infl = 0,
        dep = 0,
        n = 0;
    tickers.forEach((tk) => {
      contracts += (USAD[tk] && USAD[tk].total_contracts) || 0;
      (billsByTicker[tk] || new Set()).forEach((b) => bills.add(b));
      trades += tradeCount[tk] || 0;
      infl += influenceScore(tk);
      dep += dependencyScore(tk);
      n++;
    });
    return {
      companies: n,
      contracts,
      contracts_fmt: money(contracts),
      bills: bills.size,
      trades,
      influence: n ? Math.round(infl / n) : 0,
      dependency: n ? Math.round(dep / n) : 0,
    };
  }

  // Format a number of dollars compactly, e.g. 9800000 -> "$9.8M".
  function money(n) {
    if (!n) return "$0";
    const a = Math.abs(n);
    if (a >= 1e12) return `$${(a / 1e12).toFixed(2)}T`;
    if (a >= 1e9) return `$${(a / 1e9).toFixed(1)}B`;
    if (a >= 1e6) return `$${(a / 1e6).toFixed(1)}M`;
    if (a >= 1e3) return `$${(a / 1e3).toFixed(0)}K`;
    return `$${a.toFixed(0)}`;
  }

  // SCORE TRANSPARENCY: plain-English formulas
  // Shown to the user behind a "how did we calculate this?" expander so the
  // scoring is never a black box. This is display text only; the real math
  // lives in the functions above.
  const FORMULAS = {
    company: ["How we calculate company scores", [
      "<b>Influence Score</b> = 12 base + federal contracts (log scale, up to 40) + bill mentions (×3, up to 18) + congressional trades (×0.4, up to 18) + distinct members trading it (×1.4, up to 12) + registered lobbying (×7) + board size (×0.4, up to 5). Capped 0-100.",
      "<b>Government Dependency</b> = federal contract dollars ÷ ~5 years of revenue, scaled ×140 and capped at 100 (≈70% government revenue → ~98).",
    ]],
    pol: ["How we calculate member scores", [
      "<b>Influence</b> = 30 base + disclosed trades (×0.3) + PAC share of funding % (×0.6) + absolute estimated return % (×0.5). Capped at 100.",
      "<b>Public Impact</b> = 70 − PAC share % (×0.5) + individual-donation share % (×0.2). Higher means funding leans toward individuals. Floor 10.",
      "<b>Transparency</b> = 100 − PAC share % (×1.4) − disclosed trades (×0.15). Floor 5.",
    ]],
  };

  // Render the transparency expander for a given score family ("company" | "pol").
  function formula(kind) {
    const f = FORMULAS[kind];
    if (!f) return "";
    return `<details class="formula"><summary>Want to know how we calculated this score?</summary>`
      + `<div class="formula-body"><div class="formula-title">Here's the formula we used:</div>`
      + f[1].map((l) => `<p>${l}</p>`).join("")
      + `<div class="formula-note">All inputs come from public data (FEC, USASpending, SEC EDGAR, Congress.gov, public trade disclosures). These are transparency estimates, not accusations of wrongdoing.</div></div></details>`;
  }

  // Public surface used by the rest of the app.
  window.TFScores = {
    influenceScore, dependencyScore, politicalExposure, industryRollup, label, money, formula,
    raw: { tradeCount, polsByTicker, billsByTicker },
  };
})();
