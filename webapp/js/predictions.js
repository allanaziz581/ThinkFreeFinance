/* ============================================================
   ThinkFree - Predictive Market Signals (window.Predictions)
   A market-intelligence / forecasting layer (NOT a trading bot).
   Blends real signals already in the app -- news sentiment, congressional
   buy/sell flow, government contracts, sector peer moves, VIX, macro indices,
   policy/legislation exposure -- into a weighted probability + plain-English
   reasoning. Progressive disclosure runs through window.ScoreInfo.

   Language is probabilistic by design: bias / probability / forecast, never
   "guaranteed", "will", "buy", or "sell".
   ============================================================ */
"use strict";
(function () {
  const D = window.TF_DATA || {};
  const PX = (window.PRICES_DATA || {}).byTicker || {};
  const USA = (window.USA_DATA || {}).byTicker || {};
  const SP = (window.SP500 || {}).byTicker || {};
  const Q = (window.QUANT_DATA || {}).byTicker || {};   // real QuantLib + TA metrics (the quant core)
  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const MT = {}; (D.market_ticker || []).forEach((m) => (MT[m.label] = m));
  const num = (s) => parseFloat(String(s == null ? "" : s).replace(/[^0-9.\-]/g, "")) || 0;
  const VIX = num((MT["VIX"] || {}).value) || 18;
  const SPCHG = num((MT["S&P 500"] || {}).change);
  const NDCHG = num((MT["NASDAQ"] || {}).change);
  const YLDCHG = num((MT["10Y Yield"] || {}).change);

  // ---- per-ticker raw signals ----
  const newsByTk = {}, tradeByTk = {};
  (D.news || []).forEach((n) => { if (n.symbol) (newsByTk[n.symbol] = newsByTk[n.symbol] || []).push(n); });
  (D.recent_trades || []).forEach((t) => { if (t.ticker) (tradeByTk[t.ticker] = tradeByTk[t.ticker] || []).push(t); });

  // sector peer momentum (avg daily change of S&P peers in the same sector)
  const sectorChg = {};
  (function () {
    const acc = {};
    Object.keys(SP).forEach((tk) => {
      const s = SP[tk].sector, c = PX[tk] && PX[tk].change_pct;
      if (c == null) return; (acc[s] = acc[s] || []).push(c);
    });
    Object.keys(acc).forEach((s) => { sectorChg[s] = acc[s].reduce((a, b) => a + b, 0) / acc[s].length; });
  })();

  function name(tk) { return (PX[tk] && PX[tk].name) || (SP[tk] && SP[tk].name) || tk; }

  // each factor returns a 0-100 score (50 = neutral) + a short note
  function factors(tk) {
    const news = newsByTk[tk] || [], trades = tradeByTk[tk] || [];
    const chg = (PX[tk] && PX[tk].change_pct) || 0;
    const sec = SP[tk] && SP[tk].sector;
    const q = Q[tk];   // QuantLib + TA metrics for this ticker (if computed)

    // News sentiment
    let pos = 0, neg = 0;
    news.forEach((n) => { if (n.sentiment === "positive") pos++; else if (n.sentiment === "negative") neg++; });
    const newsScore = clamp(50 + (news.length ? (pos - neg) / news.length * 45 : 0), 5, 95);

    // Social / smart-money proxy: congressional buy vs sell flow
    let buys = 0, sells = 0;
    trades.forEach((t) => { if (/sale/i.test(t.transaction)) sells++; else if (/purchase|buy/i.test(t.transaction)) buys++; });
    const socialScore = clamp(50 + (buys + sells ? (buys - sells) / (buys + sells) * 40 : 0), 8, 92);

    // Quant forecast: QuantLib Black-Scholes expected return + 1-month probability
    // of a 5% move. Falls back to a momentum proxy only when QuantLib has no data.
    const patternScore = q
      ? clamp(50 + q.exp_return_1mo * 9 + (q.prob_up - q.prob_down) * 1.2, 8, 92)
      : clamp(50 + chg * 3 + (sec && sectorChg[sec] ? sectorChg[sec] * 2 : 0), 10, 92);

    // Technical momentum: real RSI + MACD + SMA-50/200 composite (ta library),
    // proxied by daily price change only when indicators are unavailable.
    const techScore = q && q.ta_score != null ? q.ta_score : clamp(50 + chg * 4, 8, 94);

    // VIX / fear: market-wide VIX, adjusted down by the stock's own QuantLib volatility
    const ownVolPen = q && q.volatility ? clamp((q.volatility - 25) * 0.6, -8, 24) : 0;
    const vixScore = clamp(100 - (VIX - 12) * 3.5 - ownVolPen, 8, 95);

    // Sector strength: peer momentum
    const sectorScore = clamp(50 + (sec && sectorChg[sec] != null ? sectorChg[sec] * 6 : 0), 12, 92);

    // Macro: index breadth minus rate pressure (market-wide)
    const macroScore = clamp(50 + (SPCHG + NDCHG) * 6 - YLDCHG * 30, 15, 88);

    // Policy / political: contracts + legislation + congressional flow
    const ex = window.TFScores ? window.TFScores.politicalExposure(tk) : {};
    let policy = 50;
    if (buys + sells) policy += (buys - sells) / (buys + sells) * 22;
    if (ex.contracts_raw) policy += 6;
    if (ex.bills) policy += Math.min(10, ex.bills);
    const policyScore = clamp(policy, 15, 90);

    return [
      { key: "news", label: "News Sentiment", w: 0.20, v: newsScore, vol: news.length, ex },
      { key: "social", label: "Social Sentiment", w: 0.15, v: socialScore, buys, sells },
      { key: "pattern", label: q ? "QuantLib Forecast" : "Historical Pattern Match", w: 0.15, v: patternScore, q },
      { key: "technical", label: q ? "Technical (RSI/MACD)" : "Technical Momentum", w: 0.15, v: techScore, chg, q },
      { key: "vix", label: "VIX / Fear", w: 0.10, v: vixScore },
      { key: "sector", label: "Sector Strength", w: 0.10, v: sectorScore, sec },
      { key: "macro", label: "Macro Environment", w: 0.10, v: macroScore },
      { key: "policy", label: "Policy Impact", w: 0.05, v: policyScore, ex },
    ];
  }

  const DIR = (s) => s >= 75 ? ["Bullish", "bull"] : s >= 56 ? ["Moderately Bullish", "modbull"]
    : s >= 45 ? ["Neutral", "neutral"] : s >= 35 ? ["Moderately Bearish", "modbear"] : ["Bearish", "bear"];
  const wordFor = (v) => v >= 66 ? "Positive" : v >= 56 ? "Mildly positive" : v > 44 ? "Neutral" : v > 34 ? "Mildly negative" : "Negative";
  const strongWord = (v) => v >= 66 ? "Strong" : v >= 54 ? "Moderate" : v > 44 ? "Neutral" : "Weak";

  function compute(tk) {
    const fs = factors(tk);
    const score = Math.round(fs.reduce((a, f) => a + f.v * f.w, 0));
    const [dirLabel, dirClass] = DIR(score);
    const bull = score >= 50;
    // confidence (separate from probability): real-data depth + factor agreement
    const news = newsByTk[tk] || [], trades = tradeByTk[tk] || [];
    const ex = window.TFScores ? window.TFScores.politicalExposure(tk) : {};
    let depth = 0;
    if (news.length >= 3) depth++; if (trades.length >= 2) depth++; if (PX[tk]) depth++;
    if (ex.contracts_raw) depth++; if (ex.bills) depth++;
    if (Q[tk]) depth += 2;   // real QuantLib + TA backing weighs heavily on confidence
    const agree = fs.filter((f) => (f.v >= 50) === bull).length;
    const confScore = Math.min(depth, 7) / 7 * 50 + agree / fs.length * 50;
    const confidence = confScore >= 66 ? "High" : confScore >= 45 ? "Medium" : "Low";
    // horizon derived from live volatility (VIX): calmer market = longer reliable window
    const horizon = VIX >= 25 ? "1-7 Days" : VIX >= 16 ? "7 Days" : "30 Days";
    return { ticker: tk, name: name(tk), score, dirLabel, dirClass, confidence, confScore, horizon, factors: fs, bull };
  }

  // plain-English drivers
  function drivers(p) {
    const up = [], down = [];
    p.factors.forEach((f) => {
      const phr = {
        news: ["Positive news sentiment", "Negative news flow"],
        social: ["Congressional buying activity", "Congressional selling pressure"],
        pattern: ["Recent momentum pattern is constructive", "Recent momentum pattern is weak"],
        technical: ["Upward price momentum", "Downward price momentum"],
        vix: ["Lower market fear (VIX)", "Elevated market fear (VIX)"],
        sector: ["Sector outperforming the market", "Sector lagging the market"],
        macro: ["Supportive macro backdrop", "Macro headwinds (rates / breadth)"],
        policy: ["Favorable policy and contract activity", "Unfavorable policy signals"],
      }[f.key];
      if (f.v >= 56) up.push(phr[0]); else if (f.v <= 44) down.push(phr[1]);
    });
    const q = Q[p.ticker];
    if (q) {
      if (q.exp_return_1mo > 0.3) up.push("QuantLib model projects positive 1-month drift");
      else if (q.exp_return_1mo < -0.3) down.push("QuantLib model projects negative drift");
      if (q.rsi_signal === "oversold") up.push("Oversold RSI (potential rebound)");
      else if (q.rsi_signal === "overbought") down.push("Overbought RSI");
      if (q.trend === "golden") up.push("Golden cross (uptrend strengthening)");
      else if (q.trend === "death") down.push("Death cross (downtrend strengthening)");
      if (q.volatility >= 45) down.push(`High volatility (${q.volatility}%/yr)`);
    }
    if (YLDCHG > 0) down.push("Rising interest rates");
    if (VIX >= 22) down.push("Elevated volatility");
    return { up, down };
  }

  // ScoreInfo explainer payload (tooltip bullets + full breakdown modal)
  function explain(tk) {
    const p = compute(tk);
    const { up, down } = drivers(p);
    const f = {}; p.factors.forEach((x) => (f[x.key] = x));
    const bullets = (p.bull ? up : down.length ? down : up).slice(0, 4);
    const why = `The model leans ${p.dirLabel.toLowerCase()} for ${p.name}. ` + (
      p.bull
        ? `Recent signals such as ${up.slice(0, 3).join(", ").toLowerCase() || "mixed inputs"} outweigh the risks, though confidence is ${p.confidence.toLowerCase()}.`
        : `Risks such as ${down.slice(0, 3).join(", ").toLowerCase() || "mixed inputs"} currently outweigh the positives, though confidence is ${p.confidence.toLowerCase()}.`);
    const q = Q[tk];
    const quantInputs = q ? [
      { label: "QuantLib Volatility", value: q.volatility + "%/yr" },
      { label: "1-Mo Upside Prob (Black-Scholes)", value: q.prob_up + "%" },
      { label: "Daily VaR (95%)", value: q.var95 + "%" },
      { label: "Expected Return (1mo)", value: (q.exp_return_1mo > 0 ? "+" : "") + q.exp_return_1mo + "%" },
      { label: "Sharpe Ratio", value: q.sharpe },
      { label: "RSI", value: q.rsi != null ? q.rsi + " (" + q.rsi_signal + ")" : "n/a" },
      { label: "MACD", value: q.macd_cross || "n/a" },
      { label: "Trend (SMA 50/200)", value: q.trend === "golden" ? "Golden cross" : q.trend === "death" ? "Death cross" : "n/a" },
    ] : [];
    const inputs = quantInputs.concat([
      { label: "News Sentiment", value: wordFor(f.news.v) },
      { label: "Social Sentiment", value: f.social.buys + f.social.sells ? wordFor(f.social.v) : "Limited data" },
      { label: "Sector Strength", value: strongWord(f.sector.v) },
      { label: "Macro Environment", value: wordFor(f.macro.v) },
      { label: "Policy Impact", value: wordFor(f.policy.v) },
    ]);
    const rows = p.factors.map((x) => ({ factor: x.label, value: `${Math.round(x.v)} x ${x.w.toFixed(2)} = ${(x.v * x.w).toFixed(1)}` }));
    return {
      title: `${p.ticker} - ${p.name}`,
      value: `${p.score}% Bullish probability`,
      whyLabel: "Why this prediction",
      bullets,
      why,
      upside: up, downside: down, inputs,
      calc: {
        formula: "Prediction = News x0.20 + Social x0.15 + Pattern x0.15 + Technical x0.15 + VIX x0.10 + Sector x0.10 + Macro x0.10 + Policy x0.05",
        rows, total: `${p.score}/100`,
      },
      sources: [
        { label: "QuantLib - volatility, Black-Scholes probability, VaR, Kelly" },
        { label: "Technical indicators (RSI, MACD, SMA 50/200) via ta library" },
        { label: "Market data (Finnhub quotes, VIX, indices)" },
        { label: "News sentiment analysis" },
        { label: "Congressional trade disclosures (STOCK Act)" },
        { label: "USASpending.gov federal contracts" },
        { label: "Congress.gov legislation" },
        { label: "SEC filings" },
      ],
      foot: "This forecast is an analytical estimate generated from historical market behavior, quantitative signals, sentiment analysis, economic indicators, volatility measures, policy activity, and public data. It is not financial advice and does not guarantee future performance.",
    };
  }

  // ---- forecast cone (uncertainty visual; never a guaranteed line) ----
  function cone(p) {
    const W = 230, H = 64, x0 = 10, y0 = H / 2;
    const slope = (p.score - 50) / 50;                 // -1..1 directional bias
    const conf = clamp(p.confScore / 100, 0.3, 0.9);
    const endY = y0 - slope * (H * 0.30);              // bias the midline up/down
    // band half-width = real uncertainty: QuantLib annualized volatility when we
    // have it, otherwise inverse-confidence. Higher vol = wider forecast cone.
    const q = Q[p.ticker];
    const half = q && q.volatility ? clamp((q.volatility / 100) * (H * 0.55) + 5, 6, H * 0.46)
      : (1 - conf) * (H * 0.42) + 6;
    const col = p.score >= 55 ? "#00C46A" : p.score <= 45 ? "#EF4444" : "#94A3B8";
    return `<svg class="pm-cone-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <defs><linearGradient id="pmg-${p.ticker}" x1="0" x2="1"><stop offset="0" stop-color="${col}" stop-opacity="0.32"/><stop offset="1" stop-color="${col}" stop-opacity="0.06"/></linearGradient></defs>
      <path d="M${x0},${y0} L${W - 6},${(endY - half).toFixed(1)} L${W - 6},${(endY + half).toFixed(1)} Z" fill="url(#pmg-${p.ticker})"/>
      <path d="M${x0},${y0} L${W - 6},${endY.toFixed(1)}" stroke="${col}" stroke-width="1.6" stroke-dasharray="4 3" fill="none"/>
      <circle cx="${x0}" cy="${y0}" r="3.2" fill="${col}"/>
    </svg>`;
  }

  function card(p) {
    const si = (cls, inner) => `<span class="si ${cls}" data-si-kind="prediction" data-si-key="${E(p.ticker)}" data-si-val="${p.score}" tabindex="0">${inner}</span>`;
    return `<div class="pm-card">
      <div class="pm-top">
        <div class="pm-id"><div class="pm-tk">${E(p.ticker)}</div><div class="pm-name">${E(p.name)}</div></div>
      </div>
      <div class="pm-dirrow">${si("pm-dir pm-" + p.dirClass, E(p.dirLabel) + '<i class="si-i">&#9432;</i>')}</div>
      <div class="pm-prob">${si("", `<b>${p.score}%</b>`)} <span class="pm-prob-l">Bullish probability</span></div>
      <div class="pm-cone">${cone(p)}</div>
      <div class="pm-meta">
        <span>Horizon <b>${E(p.horizon)}</b></span>
        <span>Confidence ${si("pm-conf-" + p.confidence.toLowerCase(), `<b>${p.confidence}</b>`)}</span>
      </div>
      <button class="pm-why si" data-si-kind="prediction" data-si-key="${E(p.ticker)}">Why? <span class="si-i">&#9432;</span></button>
    </div>`;
  }

  function candidates() {
    const set = new Set([...Object.keys(newsByTk), ...Object.keys(tradeByTk)]);
    const list = [...set].filter((tk) => PX[tk] && /^[A-Z]{1,5}$/.test(tk));
    const act = (tk) => (newsByTk[tk] || []).length + (tradeByTk[tk] || []).length * 0.5 + (USA[tk] ? 1 : 0);
    return list.sort((a, b) => act(b) - act(a)).slice(0, 8);
  }

  function render() {
    const cs = candidates();
    if (!cs.length) return "";
    const cards = cs.map((tk) => card(compute(tk))).join("");
    return `<section class="pm-wrap">
      <div class="pm-head">
        <div><h2>Predictive Market Signals</h2>
          <p>AI-assisted forecasts generated from market data, news sentiment, economic indicators, policy activity, and historical market behavior.</p></div>
      </div>
      <div class="pm-grid">${cards}</div>
      <div class="pm-disclaimer">This forecast is an analytical estimate generated from historical market behavior, quantitative models, sentiment analysis, economic indicators, volatility measures, policy activity, and public data sources. It is not financial advice and does not guarantee future performance.</div>
    </section>`;
  }

  // register the prediction explainer with the progressive-disclosure system
  if (window.ScoreInfo) window.ScoreInfo.register("prediction", (tk) => explain(tk));

  window.Predictions = { compute, explain, render };
})();
