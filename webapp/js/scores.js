/* ============================================================
   ThinkFree Scores Engine
   Computes ThinkFree-specific scores entirely from already-loaded
   public data (no new fetch): Influence Score, Government Dependency
   Score, Corporate Political Exposure. Plain-English, transparent.
   Exposes window.TFScores.
   ============================================================ */
"use strict";

(function () {
  const D = window.TF_DATA || {};
  const IWD = (window.IW_DATA || { companies: {} }).companies || {};
  const NPD = (window.NP_DATA || {}).byName || {};
  const SECB = (window.SECBULK_DATA || {}).byTicker || {};
  const USAD = (window.USA_DATA || {}).byTicker || {};
  const FEC = (window.FEC_DATA || {}).byName || {};

  // ---- per-company raw signals ----
  const tradeCount = {}, polsByTicker = {}, billsByTicker = {};
  (function index() {
    const all = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])];
    const seen = new Set();
    all.forEach((b) => {
      if (seen.has(b.bill_id)) return; seen.add(b.bill_id);
      (b.tickers || []).forEach((tk) => { (billsByTicker[tk] = billsByTicker[tk] || new Set()).add(b.bill_id); });
    });
    (D.recent_trades || []).forEach((t) => {
      if (!t.ticker) return;
      tradeCount[t.ticker] = (tradeCount[t.ticker] || 0) + 1;
      (polsByTicker[t.ticker] = polsByTicker[t.ticker] || new Set()).add(t.politician);
    });
  })();

  const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));
  const log10 = (n) => (n > 0 ? Math.log10(n) : 0);

  /* ---------- INFLUENCE SCORE (0-100) ----------
     How much a company is entangled with government activity.
     Inputs: federal contracts, bill mentions, congressional trading,
     lobbying presence, board size (governance footprint). */
  function influenceScore(tk) {
    const contracts = (USAD[tk] && USAD[tk].total_contracts) || 0;
    const bills = (billsByTicker[tk] ? billsByTicker[tk].size : 0);
    const trades = tradeCount[tk] || 0;
    const pols = (polsByTicker[tk] ? polsByTicker[tk].size : 0);
    const lis = IWD[tk] || {};
    const lobby = lis.lda_registrant_id ? 1 : 0;
    const board = ((window.SEC_DATA || {}).byTicker || {})[tk];
    const boardN = (board && board.board ? board.board.length : 0) + ((lis.board || []).length + (lis.executives || []).length);

    // each component capped, then weighted
    const cContract = clamp(log10(contracts) * 9, 0, 40);   // $1B -> ~81*?  log10(1e9)=9 ->81 capped 40
    const cBills = clamp(bills * 3, 0, 18);
    const cTrades = clamp(trades * 0.4, 0, 18);
    const cPols = clamp(pols * 1.4, 0, 12);
    const cLobby = lobby * 7;
    const cBoard = clamp(boardN * 0.4, 0, 5);
    const raw = cContract + cBills + cTrades + cPols + cLobby + cBoard;
    return Math.round(clamp(raw));
  }

  /* ---------- GOVERNMENT DEPENDENCY SCORE (0-100) ----------
     How dependent a company is on government money: federal contract
     dollars relative to its own revenue (the cleaner the ratio, the
     more of its business comes from the taxpayer). */
  function dependencyScore(tk) {
    const contracts = (USAD[tk] && USAD[tk].total_contracts) || 0;
    const rev5 = ((SECB[tk] && SECB[tk].revenue) || 0) * 5; // ~5yr revenue vs ~5yr contracts
    if (!contracts) return 0;
    if (!rev5) return Math.round(clamp(log10(contracts) * 8)); // no revenue: scale by raw size
    const ratio = contracts / rev5;                // 0..1+ share of revenue from federal awards
    return Math.round(clamp(ratio * 140));         // 70% gov revenue -> ~98
  }

  function label(v) { return v >= 70 ? "High" : v >= 40 ? "Medium" : v >= 15 ? "Low" : "Minimal"; }

  /* ---------- CORPORATE POLITICAL EXPOSURE (breakdown) ---------- */
  function politicalExposure(tk) {
    const lis = IWD[tk] || {};
    return {
      contracts: (USAD[tk] && USAD[tk].total_contracts_fmt) || "None",
      contracts_raw: (USAD[tk] && USAD[tk].total_contracts) || 0,
      bills: (billsByTicker[tk] ? billsByTicker[tk].size : 0),
      congressional_traders: (polsByTicker[tk] ? polsByTicker[tk].size : 0),
      trades: tradeCount[tk] || 0,
      lobbying: lis.lda_registrant_id ? "Registered (LDA " + lis.lda_registrant_id + ")" : "Sector-level",
      influence: influenceScore(tk),
      dependency: dependencyScore(tk),
    };
  }

  /* ---------- SECTOR / INDUSTRY ROLLUPS ---------- */
  function industryRollup(tickers) {
    let contracts = 0, bills = new Set(), trades = 0, infl = 0, dep = 0, n = 0;
    tickers.forEach((tk) => {
      contracts += (USAD[tk] && USAD[tk].total_contracts) || 0;
      (billsByTicker[tk] || new Set()).forEach((b) => bills.add(b));
      trades += tradeCount[tk] || 0;
      infl += influenceScore(tk); dep += dependencyScore(tk); n++;
    });
    return {
      companies: n,
      contracts, contracts_fmt: money(contracts),
      bills: bills.size, trades,
      influence: n ? Math.round(infl / n) : 0,
      dependency: n ? Math.round(dep / n) : 0,
    };
  }

  function money(n) {
    if (!n) return "$0";
    const a = Math.abs(n);
    if (a >= 1e12) return `$${(a / 1e12).toFixed(2)}T`;
    if (a >= 1e9) return `$${(a / 1e9).toFixed(1)}B`;
    if (a >= 1e6) return `$${(a / 1e6).toFixed(1)}M`;
    if (a >= 1e3) return `$${(a / 1e3).toFixed(0)}K`;
    return `$${a.toFixed(0)}`;
  }

  window.TFScores = {
    influenceScore, dependencyScore, politicalExposure, industryRollup, label, money,
    raw: { tradeCount, polsByTicker, billsByTicker },
  };
})();
