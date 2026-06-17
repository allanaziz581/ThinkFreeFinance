/* ============================================================
   ThinkFree - Plain-English Glossary (window.Glossary)
   Hover (or tap) any flagged finance term to see a one-line, jargon-free
   explanation. Used to demystify QuantLib / technical-analysis language like
   "death cross", "RSI", "VaR" so the average person is never confused.
   ============================================================ */
"use strict";
(function () {
  const TERMS = {
    "golden cross": "A sign the stock's price trend has recently turned upward and is gaining strength. Often seen as a good sign.",
    "death cross": "A sign the stock's price trend has recently turned downward and is losing strength. Often seen as a warning sign.",
    "rsi": "A 0-to-100 speed gauge. Near 70+ the price shot up fast (may be overdue for a dip); near 30- it dropped fast (may be due for a bounce).",
    "oversold": "The price dropped fast and may be due for a bounce back up.",
    "overbought": "The price ran up fast and may be due to cool off.",
    "macd": "A momentum gauge. 'Bullish' means upward push is building; 'bearish' means downward push is building.",
    "moving average": "The average price over recent weeks or months. It smooths out the daily ups and downs to show the overall direction.",
    "volatility": "How much the price jumps around. Higher means bigger, less predictable swings, so more risk.",
    "var": "A rough estimate of the worst loss to expect on a normal day (about 19 days out of 20).",
    "sharpe ratio": "Whether the gains were worth the risk taken. Higher is better; above 1 is good.",
    "kelly": "A math suggestion for how big a position could be, based on the odds. Shown for context only, not advice.",
    "black-scholes": "A well-known finance formula, used here to estimate the chance of a price move.",
    "bullish": "Leaning positive: the signs point toward the price possibly going up.",
    "bearish": "Leaning negative: the signs point toward the price possibly going down.",
    "drift": "The model's best guess at which way the price tends to lean over time.",
    "beta": "How much a stock usually moves compared with the overall market.",
  };

  const E = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const escRe = (s) => s.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");

  // wrap known terms (first occurrence each) in already-HTML-escaped text
  function annotate(s) {
    if (!s) return s;
    const keys = Object.keys(TERMS).sort((a, b) => b.length - a.length);
    let out = s; const used = {};
    keys.forEach((k) => {
      if (used[k]) return;
      const re = new RegExp("\\b(" + escRe(k) + ")\\b", "i");
      out = out.replace(re, (m) => { used[k] = 1; return `<span class="term" data-term="${E(k)}" tabindex="0">${m}</span>`; });
    });
    return out;
  }

  let tip;
  function ensure() { if (tip) return; tip = document.createElement("div"); tip.className = "term-tip"; document.body.appendChild(tip); }
  function show(key, x, y) {
    ensure(); const def = TERMS[(key || "").toLowerCase()]; if (!def) return;
    tip.textContent = def; tip.classList.add("open");
    const w = tip.offsetWidth, h = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    let lx = x + 14, ly = y + 14;
    if (lx + w > vw - 8) lx = x - w - 14;
    if (ly + h > vh - 8) ly = vh - h - 8;
    tip.style.left = Math.max(8, lx) + "px"; tip.style.top = Math.max(8, ly) + "px";
  }
  function hide() { if (tip) tip.classList.remove("open"); }

  function bind() {
    if (document._termBound) return; document._termBound = true;
    document.addEventListener("mouseover", (e) => { const el = e.target.closest(".term"); if (el) show(el.dataset.term, e.clientX, e.clientY); });
    document.addEventListener("mousemove", (e) => { if (tip && tip.classList.contains("open")) { const el = e.target.closest(".term"); if (el) show(el.dataset.term, e.clientX, e.clientY); else hide(); } });
    document.addEventListener("mouseout", (e) => { const el = e.target.closest(".term"); if (el && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest(".term"))) hide(); });
    // tap (mobile): show briefly
    document.addEventListener("click", (e) => { const el = e.target.closest(".term"); if (el) { show(el.dataset.term, e.clientX || 60, e.clientY || 60); setTimeout(hide, 3800); } });
  }
  bind();

  window.Glossary = { annotate, TERMS };
})();
