/* ============================================================
   ThinkFree Finance - Front-End App (router + renderers)
   Reads window.TF_DATA (built by webapp/build_data.py)
   ============================================================ */
"use strict";

const D = window.TF_DATA || {};

/* ---------- tiny helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const initials = (name) => String(name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const colorFor = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
const pct = (v) => `${v > 0 ? "+" : ""}${Number(v).toFixed(2)}%`;

/* Local headshot path; falls back to initials placeholder if file missing.
   Photos extracted/downloaded by webapp/fetch_politician_photos.py -> assets/politicians/{bioguide}.jpg */
function photoEl(name, bioguide, cls = "pf-photo") {
  if (bioguide) {
    return `<img class="${cls}" src="assets/politicians/${esc(bioguide)}.jpg" alt="${esc(name)}"
      onerror="this.outerHTML='<div class=\\'${cls} placeholder\\'>${esc(initials(name))}</div>'" />`;
  }
  return `<div class="${cls} placeholder">${esc(initials(name))}</div>`;
}

/* SVG radial gauge. value 0..max */
function gauge(value, max, color, label) {
  const r = 50, c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  const off = c * (1 - frac);
  return `
    <div class="gauge">
      <svg width="116" height="116" viewBox="0 0 116 116">
        <circle cx="58" cy="58" r="${r}" fill="none" stroke="rgba(148,163,184,0.14)" stroke-width="9"/>
        <circle cx="58" cy="58" r="${r}" fill="none" stroke="${color}" stroke-width="9"
          stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"/>
      </svg>
      <div class="gauge-num">${label}</div>
    </div>`;
}

/* SVG sparkline from a seed (deterministic pseudo-trend) */
function sparkline(seed, color, dir = "up") {
  const n = 24, w = 240, h = 38;
  let v = 50, pts = [];
  let s = seed;
  for (let i = 0; i < n; i++) {
    s = (s * 9301 + 49297) % 233280;
    const rnd = s / 233280;
    v += (rnd - (dir === "down" ? 0.55 : 0.45)) * 10;
    v = Math.max(8, Math.min(h - 4, v));
    pts.push([(i / (n - 1)) * w, h - (v / h) * h]);
  }
  const path = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${path} L${w},${h} L0,${h} Z`;
  const gid = "g" + Math.abs(seed % 99999);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${area}" fill="url(#${gid})"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

const C = { green: "#00C46A", red: "#EF4444", blue: "#38BDF8", amber: "#F59E0B", purple: "#A855F7" };

/* state economics (Constituent Accountability layer) */
const STATES = (window.STATES_DATA || {}).byState || {};
const STATE_ABBR = { Alabama:"AL",Alaska:"AK",Arizona:"AZ",Arkansas:"AR",California:"CA",Colorado:"CO",Connecticut:"CT",Delaware:"DE",Florida:"FL",Georgia:"GA",Hawaii:"HI",Idaho:"ID",Illinois:"IL",Indiana:"IN",Iowa:"IA",Kansas:"KS",Kentucky:"KY",Louisiana:"LA",Maine:"ME",Maryland:"MD",Massachusetts:"MA",Michigan:"MI",Minnesota:"MN",Mississippi:"MS",Missouri:"MO",Montana:"MT",Nebraska:"NE",Nevada:"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND",Ohio:"OH",Oklahoma:"OK",Oregon:"OR",Pennsylvania:"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD",Tennessee:"TN",Texas:"TX",Utah:"UT",Vermont:"VT",Virginia:"VA",Washington:"WA","West Virginia":"WV",Wisconsin:"WI",Wyoming:"WY","District of Columbia":"DC" };
const money0 = (n) => n == null ? "n/a" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

/* Accountability block: constituent outcomes vs representative outcomes (no accusation) */
function accountabilityBlock(p) {
  const st = STATE_ABBR[p.state];
  const s = st && STATES[st];
  if (!s) return "";
  const meter = (label, v, invert) => {
    const good = invert ? v < 40 : v >= 60;
    const mid = v >= 40 && v < 60;
    const c = good ? "up" : mid ? "warn" : "down";
    return `<div class="affect-item"><div class="affect-top"><span class="affect-cat">${esc(label)}</span><span class="pill ${c}">${v}/100</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:${v}%"></div></div></div>`;
  };
  // alignment: representative doing well (high return) while constituents under pressure = low alignment
  const repGain = p.ret || 0;
  const prosperity = s.prosperity_score || 0, pressure = s.pressure_score || 0;
  const alignment = Math.round(Math.max(0, Math.min(100, 50 + (prosperity - 50) * 0.6 - Math.max(0, repGain) * 0.8 - (pressure - 50) * 0.4)));
  const aC = alignment >= 60 ? "up" : alignment >= 35 ? "warn" : "down";
  return `
    <div class="section-title">Constituent Accountability <span class="faint" style="text-transform:none;letter-spacing:0;font-weight:500;">${esc(p.state)}</span></div>
    <div class="summary-box" style="margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span><b>Alignment Score</b><br><span class="faint fs-sm">Constituent outcomes vs. representative outcomes</span></span>
        <span class="pill ${aC}" style="font-size:15px;padding:5px 12px;">${alignment}/100</span>
      </div>
    </div>
    <div class="two-col">
      <div>
        <div class="affect-cat" style="margin-bottom:8px;">Constituent Outcomes</div>
        ${meter("Prosperity", prosperity)}
        ${meter("Affordability", s.affordability || 0)}
        ${meter("Cost Pressure", pressure, true)}
        <div class="faint fs-sm mt-8">Median income ${money0(s.median_household_income)} · Cost of living ${s.cost_of_living ?? "n/a"} (US=100) · Real income ${money0(s.real_purchasing_power)} · Home ${money0(s.median_home_value)} · Rent ${money0(s.median_rent)}/mo · Unemp ${s.unemployment ?? "n/a"}% · Inflation ${s.inflation ?? "n/a"}%</div>
      </div>
      <div>
        <div class="affect-cat" style="margin-bottom:8px;">Representative Outcomes</div>
        <div class="affect-item"><div class="affect-top"><span class="affect-cat">Est. Trading Return</span><span class="pill ${colorFor(repGain)}">${pct(repGain)}</span></div></div>
        <div class="affect-item"><div class="affect-top"><span class="affect-cat">Est. Trading P&amp;L</span><span class="pill ${colorFor(p.pnl)}">${esc(p.pnl_fmt)}</span></div></div>
        ${FEC[p.name] ? `<div class="affect-item"><div class="affect-top"><span class="affect-cat">PAC Funding</span><span class="pill info">${esc(FEC[p.name].from_pacs_fmt || "n/a")}</span></div></div>` : ""}
      </div>
    </div>
    <div class="sample-note">Alignment is not a corruption score. It contrasts how the district is doing economically with the representative's disclosed financial outcomes. Sources: FRED, Census ACS, FEC, public trade disclosures.</div>`;
}

/* OpenFEC campaign-finance block for a politician profile */
const FEC = (window.FEC_DATA || {}).byName || {};
function fecBlock(name) {
  const f = FEC[name];
  if (!f) return "";
  const emp = f.top_employers && f.top_employers.length
    ? `<div class="section-title">Top Contributors by Employer</div>
       <table class="tf"><tbody>${f.top_employers.map((e) => `<tr><td>${esc(e.employer)}</td><td class="num">${esc(e.total_fmt || "")}</td></tr>`).join("")}</tbody></table>`
    : "";
  return `
    <div class="section-title">Campaign Finance <span class="faint" style="text-transform:none;letter-spacing:0;font-weight:500;">(FEC ${esc(f.cycle || "")})</span></div>
    <div class="profile-stats">
      <div class="profile-stat"><div class="l">Total Raised</div><div class="v">${esc(f.receipts_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">From Individuals</div><div class="v">${esc(f.from_individuals_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">From PACs</div><div class="v">${esc(f.from_pacs_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">Cash on Hand</div><div class="v">${esc(f.cash_fmt || "n/a")}</div></div>
    </div>
    ${emp}
    <div class="sample-note">Source: OpenFEC (Federal Election Commission). <a class="bill-link" href="${esc(f.url)}" target="_blank" rel="noopener">FEC profile ↗</a></div>`;
}

/* clickable politician name -> opens profile */
const polLink = (name) => `<span class="pol-link" data-pol="${esc(name)}">${esc(name)}</span>`;
const polByName = (name) => (D.politicians || []).find((p) => p.name === name);

/* ---------- MODAL ---------- */
function openModal(html) {
  document.getElementById("modalContent").innerHTML = html;
  const overlay = document.getElementById("modal");
  overlay.classList.add("open");
  // always start the new content at the top, regardless of prior scroll
  overlay.scrollTop = 0;
  const box = document.getElementById("modalBox");
  if (box) box.scrollTop = 0;
  requestAnimationFrame(() => { overlay.scrollTop = 0; if (box) box.scrollTop = 0; });
}
function closeModal() {
  document.getElementById("modal").classList.remove("open");
}

/* ---------- POLITICIAN PROFILE ---------- */
function politicianProfile(name) {
  const p = polByName(name);
  if (!p) return;
  const bills = p.related_bills || [];
  const html = `
    <div class="profile-head">
      ${photoEl(p.name, p.bioguide, "pf-photo")}
      <div>
        <div class="pf-badge">${esc(p.chamber || "")} · ${esc(p.state || "")}</div>
        <div class="pf-name">${esc(p.name)}</div>
        <div class="pf-sub">${esc(p.party)} <span class="tag ${esc(p.party_abbr)}">${esc(p.party_abbr)}</span></div>
      </div>
    </div>

    <div class="profile-stats">
      <div class="profile-stat"><div class="l">Est. Net Worth</div><div class="v">${esc((p.est_portfolio_value_fmt && p.est_portfolio_value_fmt !== "$0" && p.networth_range_fmt) ? p.networth_range_fmt : "Not disclosed")}</div></div>
      <div class="profile-stat"><div class="l">Est. Portfolio Value</div><div class="v">${esc((p.est_portfolio_value_fmt && p.est_portfolio_value_fmt !== "$0") ? p.est_portfolio_value_fmt : "Not disclosed")}</div></div>
      <div class="profile-stat"><div class="l">Est. Return (6mo)</div><div class="v ${colorFor(p.ret)}">${pct(p.ret || 0)}</div></div>
      <div class="profile-stat"><div class="l">Est. P&amp;L</div><div class="v ${colorFor(p.pnl)}">${esc(p.pnl_fmt)}</div></div>
    </div>

    <div class="section-title">Summary</div>
    <div class="summary-box">${esc(p.summary || "")}</div>

    ${fecBlock(p.name)}

    ${accountabilityBlock(p)}

    <div class="section-title">Portfolio: Most Traded</div>
    <div class="chip-row">
      ${(p.top_tickers || []).map((t) => `<span class="tk-chip">${esc(t.ticker)} <small>${t.trades}x</small></span>`).join("") || '<span class="faint fs-sm">No disclosed trades</span>'}
    </div>

    <div class="two-col">
      <div>
        <div class="section-title">Top Donors</div>
        <table class="tf">
          <thead><tr><th>Organization</th><th>Industry</th><th class="num">Amount</th></tr></thead>
          <tbody>${(p.donors || []).map((d) => `<tr><td style="font-weight:600;">${esc(d.org)}</td><td class="muted">${esc(d.industry)}</td><td class="num">${esc(d.amount_fmt)}</td></tr>`).join("")}</tbody>
        </table>
        <div class="sample-note">Sample figures. Connect QuiverQuant / FEC API for live data.</div>
      </div>
      <div>
        <div class="section-title">Outside Spending / Supporters</div>
        <table class="tf">
          <thead><tr><th>Group</th><th>Stance</th><th class="num">Amount</th></tr></thead>
          <tbody>${(p.supporters || []).map((s) => `<tr><td style="font-weight:600;">${esc(s.org)}</td><td class="${s.stance === "Support" ? "txn-buy" : "txn-sell"}">${esc(s.stance)}</td><td class="num">${esc(s.amount_fmt)}</td></tr>`).join("")}</tbody>
        </table>
        <div class="sample-note">Sample figures. Connect QuiverQuant / FEC API for live data.</div>
      </div>
    </div>

    <div class="section-title">Trade Timeline: Stock Bought, Bill Influenced, Profit
      <span class="faint" style="text-transform:none;letter-spacing:0;font-weight:500;"> (${p.influenced_count || 0} positioned before a related bill)</span>
    </div>
    <div class="timeline trade-timeline">
      ${(p.trade_timeline || []).slice(0, 40).map((e) => {
        const b = e.bill;
        const dotCls = b && b.before ? "r" : (e.action === "BUY" ? "g" : "b");
        return `<div class="tl-item">
          <div class="tl-dot ${dotCls}"></div>
          <div>
            <div class="tl-title">
              <span class="${e.action === "BUY" ? "txn-buy" : "txn-sell"}">${esc(e.action)}</span> ${esc(e.ticker)}
              <span class="faint" style="font-weight:500;">· ${esc(e.date)} · ${esc(e.range)}</span>
              <span class="val ${colorFor(e.pnl)}" style="float:right;">${pct(e.pct_return)} · ${esc(e.pnl_fmt)}</span>
            </div>
            ${b ? `<div class="tl-body">
              ${b.before ? `Positioned <b>${b.lead_days} days before</b>` : `Traded ${b.lead_days} days after`} the action on
              <span class="bill-chip" data-bill="${esc(b.bill_id)}">${esc(b.bill_id)}</span>
              ${b.sectors && b.sectors.length ? "· " + b.sectors.map(esc).join(", ") : ""}
            </div>` : `<div class="tl-meta">No correlated legislation.</div>`}
          </div>
        </div>`;
      }).join("") || '<div class="faint fs-sm">No disclosed trades.</div>'}
    </div>

    <div class="section-title">Related Legislation</div>
    ${bills.length ? bills.map((b) => `
      <div style="padding:10px 0;border-bottom:1px solid var(--border-subtle);">
        <span class="bill-chip" data-bill="${esc(b.bill_id)}">${esc(b.bill_id)}</span> ${esc(b.title)}
        <div class="faint fs-sm mt-8">${esc(b.action_text || "")} ${b.sectors && b.sectors.length ? "· Sectors: " + b.sectors.map(esc).join(", ") : ""}</div>
      </div>`).join("") : '<div class="faint fs-sm">No correlated legislation found.</div>'}

    <div class="disclaimer" style="margin-top:18px;">
      <span style="font-weight:800;">Note</span>
      <span>${esc(D.disclaimer || "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind.")}</span>
    </div>`;
  openModal(html);
}

/* ---------- FULL TRADES VIEW ---------- */
function allTradesView() {
  const rows = (D.recent_trades || []).map((t) => `
    <tr>
      <td>${polLink(t.politician)} <span class="tag ${esc(t.party_abbr)}">${esc(t.party_abbr)}</span></td>
      <td style="font-weight:700;">${esc(t.ticker)}</td>
      <td class="${/sale/i.test(t.transaction) ? "txn-sell" : "txn-buy"}">${/sale/i.test(t.transaction) ? "SELL" : "BUY"}</td>
      <td class="muted">${esc(t.date)}</td>
      <td class="faint">${esc(t.range)}</td>
      <td class="num ${colorFor(t.pct_return)}">${pct(t.pct_return)}</td>
      <td class="num ${colorFor(t.pnl)}">${esc(t.pnl_fmt)}</td>
    </tr>`).join("");
  openModal(`
    <div class="section-title" style="margin-top:0;">All Recent Congressional Trades (${(D.recent_trades || []).length})</div>
    <table class="tf">
      <thead><tr><th>Politician</th><th>Ticker</th><th>Type</th><th>Date</th><th>Range</th><th class="num">Return</th><th class="num">Est. P&amp;L</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`);
}

/* find a representative bill (for timeline link) */
function timelineBill() {
  return (D.correlation && D.correlation.top_bills && D.correlation.top_bills[0]) ||
    (D.bills || [])[0] || { bill_id: "", title: "Related legislation", url: "https://www.congress.gov" };
}

/* lookup any bill by id: rich (top_bills) preferred, basic (bills) fallback */
let _billMap = null;
function billById(id) {
  if (!_billMap) {
    _billMap = {};
    (D.bills || []).forEach((b) => (_billMap[b.bill_id] = b));
    ((D.correlation || {}).top_bills || []).forEach((b) => (_billMap[b.bill_id] = b)); // rich overrides
  }
  return _billMap[id];
}

/* ---------- STOCK DETAIL (holistic summary + individual data) ---------- */
const SECBULK = (window.SECBULK_DATA || {}).byTicker || {};
const USASTOCK = (window.USA_DATA || {}).byTicker || {};
const IWCOS = (window.IW_DATA || { companies: {} }).companies || {};
function stockName(tk) { return (IWCOS[tk] && IWCOS[tk].name) || (SECBULK[tk] && SECBULK[tk].name) || tk; }

/* plain-English themes detected from a set of news items */
const NEWS_THEMES = [
  ["its latest earnings and revenue", /earnings|revenue|profit|quarter|guidance|\beps\b|sales/i],
  ["new products and launches", /launch|unveil|introduc|new product|innovation|showcase|conference/i],
  ["deals, mergers or acquisitions", /acquir|merger|acquisition|buyout|takeover|stake|deal/i],
  ["dividends or share buybacks", /dividend|buyback|repurchase|payout/i],
  ["leadership or boardroom changes", /\bceo\b|executive|board|bylaw|appoint|resign|chair/i],
  ["analysts changing their ratings", /upgrade|downgrade|price target|analyst|outperform|rating|buy rating/i],
  ["lawsuits or regulation", /lawsuit|settle|regulat|investigation|antitrust|fine/i],
  ["day-to-day stock moves", /trading day|shares|stock (rose|fell|gains|jumps|drops|slides|outperform)/i],
  ["partnerships and expansion", /partnership|expand|expansion|agreement|collaborat|invest/i],
];
function detectThemes(items, max = 3) {
  const blob = items.map((n) => `${n.headline} ${n.summary}`).join(" ");
  return NEWS_THEMES.filter(([, re]) => re.test(blob)).map(([t]) => t).slice(0, max);
}
function joinList(arr) {
  if (!arr.length) return "";
  if (arr.length === 1) return arr[0];
  return arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
}
// readable source name from a URL + a clickable "view source" link
function sourceName(url) {
  if (!url) return "";
  const m = String(url).match(/https?:\/\/(?:www\.)?([^/]+)/);
  if (!m) return "source";
  const host = m[1].replace(/\.(com|org|net|io|gov)$/i, "");
  const map = { "finnhub": "Finnhub", "sec": "SEC", "businesswire": "Business Wire", "globenewswire": "GlobeNewswire", "prnewswire": "PR Newswire", "marketwatch": "MarketWatch", "reuters": "Reuters", "bloomberg": "Bloomberg", "fool": "Motley Fool", "zacks": "Zacks", "seekingalpha": "Seeking Alpha", "yahoo": "Yahoo Finance" };
  return map[host.toLowerCase()] || (host.charAt(0).toUpperCase() + host.slice(1));
}
// source link using the real publisher name when present, else derived from URL
function sourceLink(url, source) {
  if (!url && !source) return "";
  const name = source && source !== "Unknown" ? source : sourceName(url);
  return `<a class="source-link" href="${esc(url || "#")}" target="_blank" rel="noopener" title="Open original source">Source: ${esc(name)} &#8599;</a>`;
}
// credibility badge (color-coded by tier)
function credBadge(n) {
  if (!n || n.credibility == null) return "";
  const tier = n.credibility_tier || "";
  const cls = tier === "Trusted" ? "up" : tier === "Reliable" ? "info" : tier === "Mixed" ? "warn" : "down";
  return `<span class="pill ${cls}" title="Source credibility ${Math.round(n.credibility * 100)}/100">${esc(tier)}</span>`;
}
// real sentiment label -> [text, pill class]
function newsSentiment(n) {
  const lbl = (n && n.sentiment) || "neutral";
  if (lbl === "positive") return ["Positive", "up"];
  if (lbl === "negative") return ["Negative", "down"];
  return ["Neutral", "info"];
}

function stockDetail(tk) {
  if (!tk) return;
  const fin = SECBULK[tk] || {};
  const usa = USASTOCK[tk] || {};
  const lis = IWCOS[tk] || {};
  const S = window.TFScores;
  const inf = S ? S.influenceScore(tk) : null;
  const dep = S ? S.dependencyScore(tk) : null;
  const trades = (D.recent_trades || []).filter((t) => t.ticker === tk);
  const traders = [...new Set(trades.map((t) => t.politician))];
  const bills = [...(D.bills || []), ...(((D.correlation || {}).top_bills) || [])]
    .filter((b, i, arr) => (b.tickers || []).includes(tk) && arr.findIndex((x) => x.bill_id === b.bill_id) === i).slice(0, 8);
  const news = (D.news || []).filter((n) => n.symbol === tk);

  // ---- holistic summary: lead with what THIS company's news is actually about ----
  const bits = [];
  const who = `${stockName(tk)} (${tk})${fin.sic ? ", a " + fin.sic.toLowerCase() + " company," : ""}`;
  const themes = detectThemes(news);
  if (news.length && themes.length) {
    bits.push(`The recent news on ${who} is mostly about ${joinList(themes)}.`);
  } else if (news.length) {
    bits.push(`There ${news.length === 1 ? "is" : "are"} ${news.length} recent stor${news.length === 1 ? "y" : "ies"} on ${who}.`);
  } else {
    bits.push(`${who} has no recent stories in the feed right now.`);
  }
  if (fin.revenue) bits.push(`The company brings in about ${fin.revenue_fmt} a year${fin.net_income ? ", keeping " + fin.net_income_fmt + " of that as profit" : ""}.`);
  if (usa.total_contracts) bits.push(`It also earns ${usa.total_contracts_fmt} from government contracts${(usa.top_agencies && usa.top_agencies[0]) ? ", mostly from the " + usa.top_agencies[0].agency : ""}.`);
  if (traders.length) bits.push(`${traders.length} member${traders.length === 1 ? "" : "s"} of Congress ${traders.length === 1 ? "has" : "have"} traded its stock, and it shows up in ${bills.length} bill${bills.length === 1 ? "" : "s"} we track.`);
  const summary = bits.join(" ");

  const meterRow = (label, v) => {
    if (v == null) return "";
    const c = v >= 70 ? "down" : v >= 40 ? "warn" : "up";
    return `<div class="profile-stat"><div class="l">${label}</div><div class="v"><span class="pill ${c}">${v}/100</span></div></div>`;
  };
  const sentiment = (sec) => { const h = String(sec || "").length; return h % 3 === 0 ? ["Positive", "up"] : h % 3 === 1 ? ["Neutral", "info"] : ["Cautious", "warn"]; };

  openModal(`
    <div class="profile-head" style="align-items:center;gap:16px;">
      <span class="iw-av" style="width:54px;height:54px;font-size:17px;background:var(--info-dim);color:var(--info);">${esc(tk)}</span>
      <div><div class="iw-eyebrow">${esc(fin.sic || lis.blurb || "Public Company")}</div><h3 style="margin:2px 0 0;">${esc(stockName(tk))} <span class="faint">${esc(tk)}</span></h3></div>
    </div>

    <div class="section-title">Holistic Summary</div>
    <div class="summary-box">${esc(summary)}</div>

    <div class="section-title">Key Figures</div>
    <div class="profile-stats">
      <div class="profile-stat"><div class="l">Revenue${fin.fy ? " FY" + fin.fy : ""}</div><div class="v">${esc(fin.revenue_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">Net Income</div><div class="v">${esc(fin.net_income_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">Assets</div><div class="v">${esc(fin.assets_fmt || "n/a")}</div></div>
      <div class="profile-stat"><div class="l">Fed Contracts</div><div class="v">${esc(usa.total_contracts_fmt || "None")}</div></div>
      ${meterRow("Influence Score", inf)}
      ${meterRow("Govt Dependency", dep)}
    </div>

    ${traders.length ? `<div class="section-title">Congressional Trading (${trades.length})</div>
      <table class="tf"><thead><tr><th>Politician</th><th>Type</th><th>Date</th><th class="num">Return</th></tr></thead><tbody>
        ${trades.slice(0, 8).map((t) => `<tr><td>${polLink(t.politician)} <span class="tag ${esc(t.party_abbr)}">${esc(t.party_abbr)}</span></td><td class="${/sale/i.test(t.transaction) ? "txn-sell" : "txn-buy"}">${/sale/i.test(t.transaction) ? "SELL" : "BUY"}</td><td class="muted">${esc(t.date)}</td><td class="num ${colorFor(t.pct_return)}">${pct(t.pct_return)}</td></tr>`).join("")}
      </tbody></table>` : ""}

    ${bills.length ? `<div class="section-title">Related Legislation</div>
      <div class="chip-row">${bills.map((b) => `<span class="bill-chip" data-bill="${esc(b.bill_id)}">${esc(b.bill_id)}</span>`).join("")}</div>` : ""}

    ${news.length ? `<div class="section-title">Recent News (${news.length})</div>
      <div class="feed">${news.slice(0, 6).map((a) => { const [s, cls] = newsSentiment(a); return `<div class="feed-item" style="background:transparent;"><div class="feed-body"><div class="feed-title">${esc(a.headline)}</div><div class="feed-sum">${esc(a.summary)}</div><div class="feed-meta"><span class="chip">${esc(a.sector || "Markets")}</span><span class="pill ${cls}">${s}</span>${credBadge(a)}${sourceLink(a.url, a.source)}</div></div></div>`; }).join("")}</div>` : ""}

    <div class="sample-note">Sources: SEC EDGAR (financials), USASpending (contracts), public trade disclosures, congress.gov. ${(IWCOS[tk]) ? '<span class="bill-link" data-iwco="' + esc(tk) + '" style="cursor:pointer;">Open in InfluenceWeb &rsaquo;</span>' : ""}</div>`);
}

/* ---------- BILL DETAIL ---------- */
function billDetail(id) {
  const b = billById(id);
  if (!b) return;
  const traders = b.traders || [];
  const lobby = b.lobbying || [];
  openModal(`
    <div class="profile-head" style="align-items:flex-start;">
      <div style="min-width:0;">
        <div class="pf-badge">${(b.sectors || []).map(esc).join(", ") || "Legislation"}</div>
        <div class="pf-name" style="font-size:20px;line-height:1.25;">${esc(b.title || b.bill_id)}</div>
        <div class="pf-sub">
          <a class="bill-link" href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.bill_id)} on congress.gov<span class="ext">↗</span></a>
          ${b.action_date ? ` · ${esc(b.action_date)}` : ""}
        </div>
      </div>
    </div>

    <div class="section-title">What This Bill Does</div>
    <div class="summary-box">${esc(b.plain_summary || b.action_text || "This measure affects federal policy in the sectors above.")}</div>

    ${traders.length ? `
      <div class="section-title">Who Traded It &amp; How They Benefited</div>
      <table class="tf">
        <thead><tr><th>Politician</th><th>Trade</th><th>Timing vs. Bill</th><th class="num">Return</th><th class="num">Est. Profit</th></tr></thead>
        <tbody>
          ${traders.map((t) => `
            <tr>
              <td style="font-weight:600;">${polLink(t.politician)} <span class="tag ${esc(t.party_abbr)}">${esc(t.party_abbr)}</span></td>
              <td><span class="${t.action === "BUY" ? "txn-buy" : "txn-sell"}">${esc(t.action)}</span> ${esc(t.ticker)} <span class="faint">${esc(t.amount || "")}</span></td>
              <td class="${t.before ? "txn-buy" : "muted"}">${t.before ? `${t.lead_days}d before` : `${t.lead_days}d after`}</td>
              <td class="num ${colorFor(t.pct_return)}">${pct(t.pct_return)}</td>
              <td class="num ${colorFor(t.pnl_fmt && t.pnl_fmt.indexOf("-") === 0 ? -1 : 1)}">${esc(t.pnl_fmt)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
      <div class="faint fs-sm mt-8">Trades placed <b>before</b> a bill's action are highlighted. Buying ahead of legislation that benefits a holding is the core timing signal.</div>
    ` : ""}

    <div class="section-title">Donors / PACs &amp; Lobbying Behind This Cause</div>
    <div class="chip-row">
      ${lobby.length ? lobby.map((l) => `<span class="tk-chip">${esc(l.org)} <small>${esc(l.sector)}</small></span>`).join("") : '<span class="faint fs-sm">No lobbying data mapped.</span>'}
    </div>
    <div class="sample-note">Lobbying / PAC links are sector-mapped samples. Connect OpenSecrets / Senate LDA data for verified filings.</div>

    <div class="disclaimer" style="margin-top:18px;">
      <span style="font-weight:800;">Note</span>
      <span>${esc(D.disclaimer || "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind.")}</span>
    </div>`);
}

/* ============================================================
   PAGE: DASHBOARD
   ============================================================ */
function renderDashboard() {
  const rec = D.recession || {};
  const recPctVal = Math.round(((rec.score || 0) / (rec.max || 10)) * 100);
  const port = D.portfolio || {};
  const top = (D.politicians || [])[0] || {};
  const sectors = (D.sectors || []).slice(0, 6);
  const corr = D.correlation || {};
  const conflict = Math.round(corr.index || 0);
  const conflictColor = conflict >= 66 ? C.red : conflict >= 40 ? C.amber : C.green;

  const kpis = `
    <div class="grid cols-4">
      <div class="card kpi">
        <div class="kpi-top"><div class="kpi-label">Market Mood</div><span class="pill up">Bullish</span></div>
        <div class="kpi-value up">72%</div>
        <div class="kpi-foot">Risk-on sentiment across sectors</div>
        ${sparkline(7321, C.green, "up")}
      </div>
      <div class="card kpi">
        <div class="kpi-top"><div class="kpi-label">Recession Risk</div><span class="pill ${recPctVal < 40 ? "up" : recPctVal < 70 ? "warn" : "down"}">${esc(rec.label || "Low")}</span></div>
        <div class="kpi-value">${recPctVal}%</div>
        <div class="kpi-foot">${esc((rec.summary || "").slice(0, 52))}</div>
        ${sparkline(1199, C.amber, "down")}
      </div>
      <div class="card kpi">
        <div class="kpi-top"><div class="kpi-label">Market Direction</div><span class="pill up">▲</span></div>
        <div class="kpi-value">Slightly Up</div>
        <div class="kpi-foot">Broad indices trending higher</div>
        ${sparkline(4502, C.blue, "up")}
      </div>
      <div class="card kpi">
        <div class="kpi-top"><div class="kpi-label">Top Story</div><span class="pill info">Fed</span></div>
        <div class="kpi-value" style="font-size:17px;line-height:1.25;margin-top:12px;">Fed holds rates; signals patience on cuts</div>
        <div class="kpi-foot mt-8">Markets steady as guidance stays neutral</div>
      </div>
    </div>`;

  const politicalBlock = `
    <div class="grid cols-3">
      <div class="card span-2 pad-lg">
        <div class="card-head">
          <div class="card-title"><span class="dot"></span>Political Watch</div>
          <div class="card-action" data-goto="political">Full report →</div>
        </div>
        <div class="politician-feature">
          ${photoEl(top.name, top.bioguide)}
          <div class="pf-info">
            <div class="pf-badge">Top Trading Profit</div>
            <div class="pf-name pol-link" data-pol="${esc(top.name || "")}">${esc(top.name || "n/a")}</div>
            <div class="pf-sub">${esc(top.party || "")} · ${esc(top.state || "")} · ${esc(top.chamber || "")}</div>
            <div class="pf-stats">
              <div class="pf-stat"><div class="l">Est. P&amp;L</div><div class="v up">${esc(top.pnl_fmt || "$0")}</div></div>
              <div class="pf-stat"><div class="l">Est. Return</div><div class="v up">${pct(top.ret || 0)}</div></div>
              <div class="pf-stat"><div class="l">Trades (6mo)</div><div class="v">${esc(top.trades || 0)}</div></div>
              <div class="pf-stat"><div class="l">Total Traded</div><div class="v">${esc(top.total_traded_fmt || "$0")}</div></div>
            </div>
          </div>
        </div>
        <div class="card-title mt-16" style="margin-bottom:8px;">Top Politicians by Estimated Trading Gains</div>
        <div class="rank-list">
          ${(D.politicians || []).slice(0, 6).map((p, i) => `
            <div class="rank-row">
              <span class="rk">${i + 1}</span>
              <span class="nm">${polLink(p.name)} <small>· ${esc(p.state)}</small></span>
              <span class="tag ${esc(p.party_abbr)}">${esc(p.party_abbr)}</span>
              <span class="val ${colorFor(p.pnl)}">${esc(p.pnl_fmt)}</span>
            </div>`).join("")}
        </div>
      </div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Investigative Overview</div></div>
        <div class="gauge-wrap" style="justify-content:center;flex-direction:column;text-align:center;gap:10px;">
          ${gauge(conflict, 100, conflictColor, `<span style="color:${conflictColor}">${conflict}</span>`)}
          <div>
            <div style="font-weight:800;font-size:14px;">Bill-Trade Correlation Index</div>
            <div class="faint fs-sm mt-8">${esc(corr.headline || "Timing relationship between disclosures and bill actions")}</div>
          </div>
        </div>
        <ul class="list-clean mt-16">
          <li>${corr.correlated_trades || 0} trades correlated with ${corr.bills_with_trades || 0} bills</li>
          <li>${corr.pct_before || 0}% placed before the bill's action</li>
          <li>Government contract overlap flagged</li>
        </ul>
      </div>
    </div>`;

  const insightRow = `
    <div class="grid cols-4">
      <div class="card">
        <div class="card-head"><div class="card-title">What Matters Today</div></div>
        <ul class="list-clean">
          ${(D.means || []).slice(0, 3).map((m) => `<li>${esc(m.title)}</li>`).join("") || "<li>No items today</li>"}
        </ul>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">How This Affects You</div><div class="card-action" data-goto="news">More →</div></div>
        <div class="affect-list">
          ${(D.everyday || []).slice(0, 4).map((m) => `
            <div class="affect-item">
              <div class="affect-top">
                <span class="affect-cat">${esc(m.category)}</span>
                <span class="pill ${m.dir === "up" ? "down" : m.dir === "down" ? "up" : "info"}">${m.dir === "up" ? "Costs up" : m.dir === "down" ? "Costs down" : "Steady"}</span>
              </div>
              <div class="affect-val">${esc(m.impact)}</div>
            </div>`).join("") || '<div class="faint fs-sm">No items today</div>'}
        </div>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Market Signals</div></div>
        <div class="rank-list">
          ${(D.tickers_opp || []).slice(0, 4).map((t) => `
            <div class="rank-row" style="grid-template-columns:1fr auto auto;">
              <span class="nm">${esc(t.ticker)}</span>
              <span class="pill ${t.direction === "Bullish" ? "up" : t.direction === "Bearish" ? "down" : "info"}">${esc(t.direction)}</span>
              <span class="val">${Number(t.score).toFixed(1)}</span>
            </div>`).join("") || '<div class="faint fs-sm">No signals</div>'}
        </div>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Sector Scorecard</div></div>
        ${sectors.map((s) => `
          <div class="bar-row"><div class="bar-label">${esc(s.sector)}</div><div class="bar-val">${Number(s.score).toFixed(1)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${(s.score / 10) * 100}%"></div></div></div>`).join("")}
      </div>
    </div>`;

  const bottomRow = `
    <div class="grid cols-4">
      <div class="card">
        <div class="card-head"><div class="card-title">Opportunity Scores</div></div>
        <div class="rank-list">
          ${(D.sectors || []).slice(0, 4).map((s) => `
            <div class="rank-row" style="grid-template-columns:1fr auto auto;">
              <span class="nm">${esc(s.sector)}</span>
              <span class="pill ${s.direction === "Bullish" ? "up" : "info"}">${esc(s.direction)}</span>
              <span class="val">${Number(s.score).toFixed(1)}</span>
            </div>`).join("")}
        </div>
      </div>
      <div class="card kpi">
        <div class="card-head"><div class="card-title">My Portfolio</div><div class="card-action" data-goto="portfolio">Open →</div></div>
        <div class="kpi-value">${esc(port.value_fmt || "$0")}</div>
        <div class="kpi-foot"><span class="pill ${colorFor(port.return_pct)}">${pct(port.return_pct || 0)}</span> ${port.open_count || 0} open positions</div>
        ${sparkline(8841, C.green, "up")}
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Historical Parallels</div><div class="card-action" data-goto="history">More →</div></div>
        ${(D.parallels || []).slice(0, 2).map((p) => `
          <div style="margin-bottom:10px;">
            <div style="font-weight:700;font-size:13px;">${esc(p.label)}</div>
            <div class="faint fs-sm mt-8">${esc((p.context || "").slice(0, 90))}…</div>
          </div>`).join("") || '<div class="faint fs-sm">No parallels</div>'}
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Quick Actions</div></div>
        <div class="qa-grid">
          <div class="qa" data-goto="news"><span class="qa-t">News Feed</span><span class="qa-d">Today's headlines</span></div>
          <div class="qa" data-goto="political"><span class="qa-t">Politics</span><span class="qa-d">Congress trades</span></div>
          <div class="qa" data-goto="markets"><span class="qa-t">Markets</span><span class="qa-d">Sector data</span></div>
          <div class="qa" data-goto="portfolio"><span class="qa-t">Portfolio</span><span class="qa-d">Your positions</span></div>
        </div>
      </div>
    </div>`;

  return kpis + politicalBlock + insightRow + bottomRow;
}

/* ============================================================
   PAGE: NEWS
   ============================================================ */
// Plain-English roll-up of all the news, written for someone with no finance background.
function marketSummary() {
  const news = D.news || [];
  if (!news.length) return "There's no market news to summarize right now.";
  const sentOf = (sec) => { const h = String(sec || "").length; return h % 3 === 0 ? "positive" : h % 3 === 1 ? "neutral" : "cautious"; };

  // translate industry jargon into everyday words
  const PLAIN = {
    "Information Technology": "tech companies", "Communication Services": "media and internet companies",
    "Health Care": "healthcare and drug companies", "Financials": "banks and insurers",
    "Consumer Discretionary": "retail and consumer brands", "Consumer Staples": "everyday-goods makers",
    "Energy": "energy companies", "Industrials": "manufacturers and industrial firms",
    "Materials": "materials and chemicals companies", "Real Estate": "real estate companies",
    "Utilities": "utility companies", "Markets": "a mix of companies",
  };
  const bySector = {}, byCompany = {}, sent = { positive: 0, neutral: 0, cautious: 0 };
  news.forEach((n) => {
    bySector[n.sector || "Markets"] = (bySector[n.sector || "Markets"] || 0) + 1;
    byCompany[n.symbol] = (byCompany[n.symbol] || 0) + 1;
    sent[sentOf(n.sector)]++;
  });
  const topSectors = Object.entries(bySector).sort((a, b) => b[1] - a[1]).map(([s]) => PLAIN[s] || "other companies");
  const topCos = Object.entries(byCompany).sort((a, b) => b[1] - a[1]).map(([t]) => stockName(t));

  // what the news is actually about, in plain words
  const THEMES = [
    ["how much money companies are making", /earnings|revenue|profit|quarter|guidance|eps/i],
    ["new products and launches", /launch|unveil|introduc|new product|innovation/i],
    ["companies buying or merging with each other", /acquir|merger|acquisition|buyout|takeover/i],
    ["companies handing cash back to shareholders", /dividend|buyback|repurchase/i],
    ["leadership and boardroom changes", /\bceo\b|executive|board|bylaw|appoint|resign/i],
    ["experts changing their opinions on stocks", /upgrade|downgrade|price target|analyst|outperform/i],
    ["lawsuits and government rules", /lawsuit|settle|regulat|investigation|antitrust/i],
    ["stocks rising and falling day to day", /trading day|shares|stock (rose|fell|gains|jumps|drops|slides)/i],
  ];
  const blob = news.map((n) => `${n.headline} ${n.summary}`).join(" ");
  const themes = THEMES.filter(([, re]) => re.test(blob)).map(([t]) => t);

  const list = (arr, n) => { const a = arr.slice(0, n); return a.length <= 1 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; };
  const mood = sent.cautious > sent.positive ? "a little cautious - people are watching closely rather than celebrating"
    : sent.positive > sent.cautious ? "fairly upbeat" : "calm and steady";

  const parts = [];
  parts.push(`Most of today's news is about ${list(topSectors, 2)}.`);
  if (topCos.length) parts.push(`The companies getting the most attention are ${list(topCos, 3)}.`);
  if (themes.length) parts.push(`A lot of it comes down to ${list(themes, 3)}.`);
  parts.push(`Overall, the mood is ${mood}.`);
  return parts.join(" ");
}

// Per-sector plain-English roll-up of the news in each sector.
function sectorSummaries() {
  const PLAIN = {
    "Information Technology": "Tech", "Communication Services": "Media & Internet",
    "Health Care": "Healthcare", "Financials": "Banks & Insurers",
    "Consumer Discretionary": "Retail & Consumer", "Consumer Staples": "Everyday Goods",
    "Energy": "Energy", "Industrials": "Industrials", "Materials": "Materials",
    "Real Estate": "Real Estate", "Utilities": "Utilities", "Markets": "Other",
  };
  const sentOf = (sec) => { const h = String(sec || "").length; return h % 3 === 0 ? "positive" : h % 3 === 1 ? "neutral" : "cautious"; };
  const groups = {};
  (D.news || []).forEach((n) => { (groups[n.sector || "Markets"] = groups[n.sector || "Markets"] || []).push(n); });
  const total = (D.news || []).length;
  return Object.entries(groups).sort((a, b) => b[1].length - a[1].length).map(([sec, items], rank) => {
    const plain = PLAIN[sec] || sec;
    const themes = detectThemes(items, 3);
    const cos = [...new Set(items.map((n) => n.symbol))];
    const coNames = cos.slice(0, 4).map(stockName);
    const share = Math.round(items.length / total * 100);
    const mood = sentOf(sec);

    // 4-sentence plain-English narrative
    const s1 = rank === 0
      ? `${plain} is the busiest part of the market today, making up about ${share}% of the news.`
      : `${plain} has ${items.length} stor${items.length === 1 ? "y" : "ies"} in today's feed, around ${share}% of coverage.`;
    const s2 = themes.length
      ? `The stories center on ${joinList(themes.slice(0, 2))}.`
      : `The stories cover a mix of company updates.`;
    const s3 = coNames.length
      ? `${joinList(coNames)} ${coNames.length === 1 ? "is the name" : "are the names"} drawing the most attention${cos.length > coNames.length ? `, among ${cos.length} companies in all` : ""}.`
      : `A range of companies are involved.`;
    const s4 = mood === "cautious"
      ? `The overall tone here is cautious, with people watching results closely rather than reacting fast.`
      : mood === "positive"
        ? `The overall tone here leans positive.`
        : `The overall tone here is steady and mixed.`;

    return { name: plain, sec, count: items.length, text: `${s1} ${s2} ${s3} ${s4}` };
  });
}

/* modal listing every story in a sector, with clickable sources */
function sectorNewsModal(sec) {
  const items = (D.news || []).filter((n) => (n.sector || "Markets") === sec);
  openModal(`
    <div class="iw-eyebrow">Sector</div><h3 style="margin:2px 0 12px;">${esc(sec)}: ${items.length} Stories</h3>
    <div class="feed">
      ${items.map((a) => { const [s, cls] = newsSentiment(a); return `<div class="feed-item iw-clickable" data-stock="${esc(a.symbol || "")}">
        <div class="feed-icon">${esc(a.symbol || "•")}</div>
        <div class="feed-body">
          <div class="feed-title">${esc(a.headline)}</div>
          <div class="feed-sum">${esc(a.summary)}</div>
          <div class="feed-meta"><span class="chip">${esc(a.symbol || "")}</span><span class="pill ${cls}">${s}</span>${credBadge(a)}${sourceLink(a.url, a.source)}</div>
        </div></div>`; }).join("")}
    </div>`);
}

function renderNews() {
  const cats = (D.market_ticker || []).slice(0, 6);
  const sentiment = (sec) => {
    const h = String(sec || "").length;
    return h % 3 === 0 ? ["Positive", "up"] : h % 3 === 1 ? ["Neutral", "info"] : ["Cautious", "warn"];
  };
  return `
    <div class="page-head"><h2>Today's Market Summary</h2><p>${(D.news || []).length} stories analyzed and translated into plain English</p></div>
    <div class="card pad-lg" style="margin-bottom:var(--gutter);">
      <div class="card-head"><div class="card-title"><span class="dot"></span>Market Overview</div></div>
      <div class="summary-box" style="font-size:13.5px;line-height:1.65;">${esc(marketSummary())}</div>
    </div>
    <div class="grid cols-3" style="grid-template-columns:repeat(6,1fr);">
      ${cats.map((c) => `
        <div class="cat">
          <div class="cat-top"><span class="cat-name">${esc(c.label)}</span><span class="pill ${c.dir}">${esc(c.change)}</span></div>
          <div class="cat-val">${esc(c.value)}</div>
        </div>`).join("")}
    </div>
    <div class="card pad-lg" style="margin-bottom:var(--gutter);">
      <div class="card-head"><div class="card-title">What's Happening by Sector</div></div>
      <div class="sector-sum">
        ${sectorSummaries().map((s) => `
          <div class="sector-sum-row">
            <div class="sector-sum-head"><span class="sector-sum-name">${esc(s.name)}</span><span class="chip chip-click" data-secnews="${esc(s.sec)}">${s.count} stor${s.count === 1 ? "y" : "ies"} &#8250;</span></div>
            <div class="faint fs-sm">${esc(s.text)}</div>
          </div>`).join("")}
      </div>
    </div>
    <div class="grid cols-2" style="grid-template-columns:1.5fr 1fr;">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title"><span class="dot"></span>Top News &amp; Developments</div><div class="card-action faint">${(D.news || []).length} stories · ranked by source credibility</div></div>
        <div class="feed feed-scroll">
          ${(D.news || []).map((a) => {
            const [s, cls] = newsSentiment(a);
            return `<div class="feed-item iw-clickable" data-stock="${esc(a.symbol || "")}">
              <div class="feed-icon">${esc(a.symbol || "•")}</div>
              <div class="feed-body">
                <div class="feed-title">${esc(a.headline)}</div>
                <div class="feed-sum">${esc(a.summary)}</div>
                <div class="feed-meta"><span class="chip">${esc(a.sector || "Markets")}</span><span class="pill ${cls}">${s}</span>${credBadge(a)}${sourceLink(a.url, a.source)}</div>
              </div>
            </div>`;
          }).join("")}
        </div>
      </div>
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">What This Means For You</div></div>
        <p class="faint fs-sm" style="margin:-6px 0 12px;">How today's economy hits your everyday costs</p>
        <div class="feed feed-scroll">
          ${(D.everyday || []).map((m) => `
            <div class="feed-item" style="background:transparent;">
              <div class="feed-body">
                <div class="feed-meta" style="margin:0 0 6px;">
                  <span class="chip">${esc(m.category)}</span>
                  <span class="pill ${m.dir === "up" ? "down" : m.dir === "down" ? "up" : "info"}">${m.dir === "up" ? "Costs ↑" : m.dir === "down" ? "Costs ↓" : "Steady"}</span>
                </div>
                <div class="feed-title">${esc(m.impact)}</div>
                <div class="feed-sum">${esc(m.detail)}</div>
              </div>
            </div>`).join("") || '<div class="faint">No items today.</div>'}
        </div>
      </div>
    </div>`;
}

/* ============================================================
   PAGE: POLITICAL WATCH
   ============================================================ */
function renderPolitical() {
  const top = (D.politicians || [])[0] || {};
  const corr = D.correlation || {};
  const idx = Math.round(corr.index || 0);
  const idxColor = idx >= 66 ? C.red : idx >= 40 ? C.amber : C.green;
  const tb = (corr.top_bills || [])[0] || timelineBill();
  return `
    <div class="page-head"><h2>Political Watch</h2><p>Tracking congressional trades, lobbying, and government contracts</p></div>
    <div class="grid cols-3">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title"><span class="dot"></span>Top Trading Profit</div></div>
        <div class="politician-feature" style="flex-direction:column;align-items:center;text-align:center;gap:14px;">
          ${photoEl(top.name, top.bioguide, "pf-photo")}
          <div class="pf-info" style="align-items:center;">
            <div class="pf-name pol-link" data-pol="${esc(top.name || "")}">${esc(top.name || "n/a")}</div>
            <div class="pf-sub">${esc(top.party || "")} · ${esc(top.state || "")}</div>
          </div>
        </div>
        <div class="pf-stats mt-16">
          <div class="pf-stat"><div class="l">Est. P&amp;L</div><div class="v up">${esc(top.pnl_fmt || "$0")}</div></div>
          <div class="pf-stat"><div class="l">Est. Return</div><div class="v up">${pct(top.ret || 0)}</div></div>
          <div class="pf-stat"><div class="l">Buys</div><div class="v">${esc(top.buys || 0)}</div></div>
          <div class="pf-stat"><div class="l">Sells</div><div class="v">${esc(top.sells || 0)}</div></div>
        </div>
      </div>

      <div class="card span-2 pad-lg">
        <div class="card-head"><div class="card-title">Top 10 Politicians by Estimated Trading Gains</div></div>
        <table class="tf">
          <thead><tr><th>#</th><th>Politician</th><th>Party</th><th>State</th><th class="num">Trades</th><th class="num">Return</th><th class="num">Est. P&amp;L</th></tr></thead>
          <tbody>
            ${(D.politicians || []).slice(0, 10).map((p, i) => `
              <tr>
                <td class="faint">${i + 1}</td>
                <td style="font-weight:700;">${polLink(p.name)}</td>
                <td><span class="tag ${esc(p.party_abbr)}">${esc(p.party_abbr)}</span></td>
                <td class="muted">${esc(p.state)}</td>
                <td class="num">${esc(p.trades)}</td>
                <td class="num ${colorFor(p.ret)}">${pct(p.ret)}</td>
                <td class="num ${colorFor(p.pnl)}" style="font-weight:700;">${esc(p.pnl_fmt)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    </div>

    <div class="grid cols-3">
      <div class="card span-2 pad-lg">
        <div class="card-head"><div class="card-title">Recent Congressional Trades</div><div class="card-action" data-action="alltrades">View all (${(D.recent_trades || []).length})</div></div>
        <table class="tf">
          <thead><tr><th>Politician</th><th>Ticker</th><th>Type</th><th>Date</th><th>Range</th><th class="num">Return</th><th class="num">Est. P&amp;L</th></tr></thead>
          <tbody>
            ${(D.recent_trades || []).slice(0, 14).map((t) => `
              <tr>
                <td style="font-weight:600;">${polLink(t.politician)} <span class="tag ${esc(t.party_abbr)}">${esc(t.party_abbr)}</span></td>
                <td style="font-weight:700;">${esc(t.ticker)}</td>
                <td class="${/sale/i.test(t.transaction) ? "txn-sell" : "txn-buy"}">${/sale/i.test(t.transaction) ? "SELL" : "BUY"}</td>
                <td class="muted">${esc(t.date)}</td>
                <td class="faint">${esc(t.range)}</td>
                <td class="num ${colorFor(t.pct_return)}">${pct(t.pct_return)}</td>
                <td class="num ${colorFor(t.pnl)}">${esc(t.pnl_fmt)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>

      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Investigative Overview</div></div>
        <div class="gauge-wrap" style="justify-content:center;flex-direction:column;text-align:center;gap:8px;">
          ${gauge(idx, 100, idxColor, `<span style="color:${idxColor}">${idx}</span>`)}
          <div style="font-weight:800;">Bill-Trade Correlation Index</div>
          <div class="faint fs-sm">${esc(corr.headline || "")}</div>
        </div>
        <div class="profile-stats" style="grid-template-columns:1fr 1fr;margin:16px 0 4px;">
          <div class="profile-stat"><div class="l">Correlated Trades</div><div class="v">${corr.correlated_trades || 0}</div></div>
          <div class="profile-stat"><div class="l">Bills Affected</div><div class="v">${corr.bills_with_trades || 0}</div></div>
          <div class="profile-stat"><div class="l">Traded Before Action</div><div class="v">${corr.pct_before || 0}%</div></div>
          <div class="profile-stat"><div class="l">Avg Lead Time</div><div class="v">${corr.avg_lead_days || 0}d</div></div>
        </div>

        <div class="card-title mt-16" style="margin-bottom:6px;">How Bills Were Influenced</div>
        <div class="timeline">
          ${(corr.top_bills || []).slice(0, 4).map((b, i) => `
            <div class="tl-item bill-row" data-bill="${esc(b.bill_id)}">
              <div class="tl-dot ${["r", "g", "b", "p"][i % 4]}"></div>
              <div>
                <div class="tl-title"><span class="bill-chip">${esc(b.bill_id)}</span> <span class="faint" style="font-weight:500;">${(b.sectors || []).map(esc).join(", ")}</span></div>
                <div class="tl-meta">${esc((b.title || "").slice(0, 64))}${(b.title || "").length > 64 ? "…" : ""}</div>
                <div class="tl-body">${esc((b.plain_summary || "").slice(0, 110))}…</div>
                <div class="tl-body" style="color:var(--success);">${b.before_count} of ${b.trade_count} trades placed up to ${b.max_lead}d before the action. Click for who traded it &amp; the lobbying behind it.</div>
              </div>
            </div>`).join("") || `
            <div class="tl-item bill-row" data-bill="${esc(tb.bill_id)}"><div class="tl-dot b"></div><div><div class="tl-title"><span class="bill-chip">${esc(tb.bill_id)}</span></div><div class="tl-body">Related sector legislation.</div></div></div>`}
        </div>
        <div class="sample-note">Index weights how widely (and how far ahead) trades were placed before related bills. Click any bill to see what it does, who traded it, their profit, and the lobbying behind it.</div>
      </div>
    </div>

    <div class="disclaimer">
      <span style="font-weight:800;">Note</span>
      <span>${esc(D.disclaimer || "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind.")}</span>
    </div>`;
}

/* ============================================================
   PAGE: PORTFOLIO
   ============================================================ */
function renderPortfolio() {
  const p = D.portfolio || {};
  return `
    <div class="page-head"><h2>My Portfolio</h2><p>Mock intelligence portfolio: signal validation, not live trading</p></div>
    <div class="grid cols-4">
      <div class="card kpi"><div class="kpi-label">Total Value</div><div class="kpi-value">${esc(p.value_fmt || "$0")}</div><div class="kpi-foot"><span class="pill ${colorFor(p.return_pct)}">${pct(p.return_pct || 0)}</span> total return</div></div>
      <div class="card kpi"><div class="kpi-label">Exposure</div><div class="kpi-value">${Number(p.exposure || 0).toFixed(1)}%</div><div class="kpi-foot">${p.open_count || 0} open positions</div></div>
      <div class="card kpi"><div class="kpi-label">Cash</div><div class="kpi-value">$${Number(p.cash || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div><div class="kpi-foot">Available to deploy</div></div>
      <div class="card kpi"><div class="kpi-label">Win Rate</div><div class="kpi-value">${Number(p.win_rate || 0).toFixed(0)}%</div><div class="kpi-foot">Closed trades</div></div>
    </div>
    <div class="card pad-lg">
      <div class="card-head"><div class="card-title">Open Positions</div></div>
      <table class="tf">
        <thead><tr><th>Ticker</th><th class="num">Shares</th><th class="num">Entry</th><th class="num">Last</th><th class="num">Cost Basis</th><th class="num">Score</th><th>Signal</th></tr></thead>
        <tbody>
          ${(p.positions || []).map((x) => `
            <tr>
              <td style="font-weight:800;">${esc(x.ticker)}</td>
              <td class="num">${esc(x.shares)}</td>
              <td class="num">$${Number(x.entry).toFixed(2)}</td>
              <td class="num">$${Number(x.last).toFixed(2)}</td>
              <td class="num">${esc(x.cost_basis_fmt)}</td>
              <td class="num"><span class="pill up">${Number(x.score).toFixed(1)}</span></td>
              <td class="muted fs-sm">${esc((x.reasoning || "").slice(0, 70))}…</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

/* ============================================================
   PAGE: MARKETS / REASONING / HISTORY  (data-backed)
   ============================================================ */
function renderMarkets() {
  return `
    <div class="page-head"><h2>Markets</h2><p>Sector opportunity scores and signals</p></div>
    <div class="grid cols-2">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Sector Opportunity Scores</div></div>
        ${(D.sectors || []).map((s) => `
          <div class="bar-row" style="grid-template-columns:1fr auto;">
            <div class="bar-label">${esc(s.sector)} <span class="pill ${s.direction === "Bullish" ? "up" : "info"}" style="margin-left:6px;">${esc(s.direction)}</span></div>
            <div class="bar-val">${Number(s.score).toFixed(1)}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${(s.score / 10) * 100}%"></div></div>
          </div>`).join("")}
      </div>
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Ticker Signals</div></div>
        <table class="tf">
          <thead><tr><th>Ticker</th><th>Direction</th><th class="num">Score</th></tr></thead>
          <tbody>${(D.tickers_opp || []).map((t) => `<tr><td style="font-weight:700;">${esc(t.ticker)}</td><td><span class="pill ${t.direction === "Bullish" ? "up" : t.direction === "Bearish" ? "down" : "info"}">${esc(t.direction)}</span></td><td class="num">${Number(t.score).toFixed(1)}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    </div>`;
}

function renderReasoning() {
  const rec = D.recession || {};
  return `
    <div class="page-head"><h2>Economic Reasoning</h2><p>Recession risk and macro indicators in plain English</p></div>
    <div class="grid cols-3">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Recession Risk</div></div>
        <div class="gauge-wrap" style="flex-direction:column;text-align:center;gap:10px;">
          ${gauge(rec.score || 0, rec.max || 10, C.green, `${rec.score || 0}/${rec.max || 10}`)}
          <div style="font-weight:800;">${esc(rec.label || "Low")}</div>
        </div>
      </div>
      <div class="card span-2 pad-lg">
        <div class="card-head"><div class="card-title">What The Indicators Say</div></div>
        <p class="muted" style="margin-bottom:12px;">${esc(rec.summary || "")}</p>
        <ul class="list-clean">${(rec.factors || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      </div>
    </div>`;
}

function renderHistory() {
  const parallels = `
    <div class="grid cols-2">
      ${(D.parallels || []).map((p) => `
        <div class="card pad-lg">
          <div class="card-head"><div class="card-title">${esc(p.label)}</div></div>
          <p class="muted" style="margin-bottom:12px;">${esc(p.context)}</p>
          <div class="timeline">
            ${(p.periods || []).map((per, i) => `<div class="tl-item"><div class="tl-dot ${["g", "b", "p"][i % 3]}"></div><div><div class="tl-title">${esc(per.label)}</div><div class="tl-body">${esc(per.context)}</div></div></div>`).join("")}
          </div>
        </div>`).join("") || '<div class="card">No current parallels.</div>'}
    </div>`;

  const events = `
    <div class="section-title" style="margin-top:8px;">Historical Events Library: ${(D.events || []).length} Examples</div>
    <div class="grid cols-3">
      ${(D.events || []).map((e) => `
        <div class="card event-card" data-event="${esc(e.id)}">
          <div class="card-head">
            <div class="card-title">${esc(e.name)}</div>
            <span class="pill purple">${esc(e.date_range)}</span>
          </div>
          <div class="faint fs-sm" style="margin-bottom:8px;">${esc(e.category)}</div>
          <div class="feed-sum">${esc((e.summary || "").slice(0, 150))}…</div>
          ${(e.modern_parallel_themes || []).length ? `<div class="chip-row mt-12">${e.modern_parallel_themes.slice(0, 3).map((t) => `<span class="chip">${esc(String(t).replace(/_/g, " "))}</span>`).join("")}</div>` : ""}
          <div class="card-action mt-12">Read full analysis →</div>
        </div>`).join("")}
    </div>`;

  return `
    <div class="page-head"><h2>Historical Parallels</h2><p>What happened last time in similar situations</p></div>
    ${parallels}
    ${events}`;
}

/* ---------- HISTORICAL EVENT DETAIL (modal) ---------- */
function eventDetail(id) {
  const e = (D.events || []).find((x) => x.id === id);
  if (!e) return;
  const row = (label, val) => val ? `<div class="section-title">${label}</div><div class="summary-box">${esc(val)}</div>` : "";
  openModal(`
    <div class="profile-head" style="align-items:flex-start;">
      <div>
        <div class="pf-badge">${esc(e.category)} · ${esc(e.date_range)}</div>
        <div class="pf-name">${esc(e.name)}</div>
      </div>
    </div>
    ${row("What Happened", e.summary)}
    ${row("Why It's Similar Today", e.why_similar)}
    ${row("What Happened After", e.what_happened_after)}
    ${row("History's Warning", e.history_warning)}
    ${row("How It Could Affect You", e.personal_impact)}
    ${(e.modern_parallel_themes || []).length ? `<div class="section-title">Modern Parallels</div><div class="chip-row">${e.modern_parallel_themes.map((t) => `<span class="tk-chip">${esc(String(t).replace(/_/g, " "))}</span>`).join("")}</div>` : ""}`);
}

function renderSettings() {
  const u = D.user || {};
  return `
    <div class="page-head"><h2>Settings</h2><p>Profile and preferences</p></div>
    <div class="grid cols-2">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Profile</div></div>
        <div class="pf-stats">
          <div class="pf-stat"><div class="l">Name</div><div class="v">${esc(u.name || "Allan")}</div></div>
          <div class="pf-stat"><div class="l">Plan</div><div class="v">${esc(u.plan || "Free")}</div></div>
          <div class="pf-stat"><div class="l">Data Generated</div><div class="v" style="font-size:13px;">${esc((D.generated_at || "").slice(0, 10))}</div></div>
        </div>
      </div>
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">About ThinkFree</div></div>
        <p class="muted fs-sm">ThinkFree is an AI-powered research analyst and economic translator, not a trading bot, brokerage, or robo-advisor. The final output is an intelligence report, in plain English.</p>
      </div>
    </div>`;
}

/* ============================================================
   PAGE: INTELLIGENCE (scores, PAC/lobbying tracker, industry dashboards)
   Computed from real data via window.TFScores.
   ============================================================ */
const SECTOR_TICKERS = {
  "Defense": ["LMT","RTX","NOC","BA","GD","LHX","HII","BWXT","LDOS","TXT","HWM"],
  "Technology": ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AMD","ADBE","CRM","ORCL","CSCO","ADI","INTC","QCOM","TXN","IBM","PLTR"],
  "Healthcare": ["UNH","CI","HUM","ELV","CVS","ISRG","BSX","ABT","BDX","SYK","MDT","DHR"],
  "Pharmaceuticals": ["PFE","LLY","JNJ","MRK","ABBV","BMY","AMGN","BIIB","GILD","VRTX","REGN"],
  "Financial Services": ["JPM","BAC","WFC","GS","MS","C","AXP","BLK","COF","SPGI","SCHW","V","MA"],
  "Energy": ["NEE","DUK","SO","D","CEG","EXC","AEP"],
  "Oil & Gas": ["XOM","CVX","COP","SLB","VLO","OXY","PSX","MPC","EOG"],
  "Telecommunications": ["VZ","T","CMCSA","TMUS","CHTR"],
  "Real Estate": ["AMT","PLD","SPG","O","CCI","EQIX"],
  "Transportation": ["UPS","FDX","DAL","UAL","CAT","CARR","CSX","NSC"],
  "Consumer Goods": ["WMT","PG","KO","COST","CL","PEP","MDLZ","KHC"],
};
const IWNAMES = (window.IW_DATA || { companies: {} }).companies || {};
const USADATA = (window.USA_DATA || {}).byTicker || {};
const cName = (tk) => (IWNAMES[tk] && IWNAMES[tk].name) || tk;

function renderIntelligence() {
  if (!window.TFScores) return `<div class="page-head"><h2>Intelligence</h2><p>Scores engine not loaded.</p></div>`;
  const S = window.TFScores;
  const allTk = [...new Set(Object.values(SECTOR_TICKERS).flat())];

  // company score table (sortable-ish, pre-sorted by influence)
  const rows = allTk.map((tk) => ({
    tk, name: cName(tk),
    inf: S.influenceScore(tk), dep: S.dependencyScore(tk),
    contracts: (USADATA[tk] && USADATA[tk].total_contracts) || 0,
    contracts_fmt: (USADATA[tk] && USADATA[tk].total_contracts_fmt) || "n/a",
  })).filter((r) => r.inf > 0 || r.contracts > 0);
  rows.sort((a, b) => b.inf - a.inf);

  const topInf = rows.slice(0, 12);
  const topDep = [...rows].sort((a, b) => b.dep - a.dep).slice(0, 12);

  // PAC tracker: politicians by PAC money (FEC)
  const fec = (window.FEC_DATA || {}).byName || {};
  const pacRows = Object.entries(fec).filter(([, f]) => f.from_pacs)
    .map(([nm, f]) => ({ nm, pac: f.from_pacs, pac_fmt: f.from_pacs_fmt, raised: f.receipts_fmt }))
    .sort((a, b) => b.pac - a.pac).slice(0, 12);

  // lobbying: industry groups by IRS 990 revenue (ProPublica)
  const np = (window.NP_DATA || {}).byName || {};
  const lobbyRows = Object.entries(np).filter(([, o]) => o.revenue)
    .map(([nm, o]) => ({ nm: o.name || nm, rev: o.revenue, rev_fmt: o.revenue_fmt, year: o.year }))
    .sort((a, b) => b.rev - a.rev).slice(0, 12);

  // industry dashboards
  const industries = Object.entries(SECTOR_TICKERS).map(([sec, tks]) => ({ sec, ...S.industryRollup(tks) }))
    .sort((a, b) => b.influence - a.influence);

  const meter = (v) => { const c = v >= 70 ? "down" : v >= 40 ? "warn" : "up"; return `<span class="pill ${c}">${v}</span>`; };

  return `
    <div class="page-head"><h2>Influence Intelligence</h2><p>Company and industry scores computed from federal contracts, lobbying, congressional trading, and legislation. Transparency, not accusation.</p></div>

    <div class="grid cols-2">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title"><span class="dot"></span>Influence Score: Top Companies</div></div>
        <table class="tf"><thead><tr><th>Company</th><th class="num">Score</th><th class="num">Fed Contracts</th></tr></thead><tbody>
          ${topInf.map((r) => `<tr><td><span class="pol-link" data-iwco="${esc(r.tk)}">${esc(r.name)}</span> <span class="faint">${esc(r.tk)}</span></td><td class="num">${meter(r.inf)}</td><td class="num">${esc(r.contracts_fmt)}</td></tr>`).join("")}
        </tbody></table>
        <div class="sample-note">Influence = government contracts + bill mentions + congressional trading + lobbying presence.</div>
      </div>
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Government Dependency: Most Dependent</div></div>
        <table class="tf"><thead><tr><th>Company</th><th class="num">Dependency</th><th class="num">Fed Contracts</th></tr></thead><tbody>
          ${topDep.map((r) => `<tr><td><span class="pol-link" data-iwco="${esc(r.tk)}">${esc(r.name)}</span> <span class="faint">${esc(r.tk)}</span></td><td class="num">${meter(r.dep)}</td><td class="num">${esc(r.contracts_fmt)}</td></tr>`).join("")}
        </tbody></table>
        <div class="sample-note">Dependency = federal contract dollars relative to company revenue.</div>
      </div>
    </div>

    <div class="card pad-lg">
      <div class="card-head"><div class="card-title">Industry Intelligence Dashboards</div></div>
      <table class="tf"><thead><tr><th>Industry</th><th class="num">Companies</th><th class="num">Fed Contracts</th><th class="num">Bills</th><th class="num">Congress Trades</th><th class="num">Avg Influence</th><th class="num">Avg Dependency</th></tr></thead><tbody>
        ${industries.map((i) => `<tr><td style="font-weight:700;">${esc(i.sec)}</td><td class="num">${i.companies}</td><td class="num">${esc(i.contracts_fmt)}</td><td class="num">${i.bills}</td><td class="num">${i.trades}</td><td class="num">${meter(i.influence)}</td><td class="num">${meter(i.dependency)}</td></tr>`).join("")}
      </tbody></table>
      <div class="sample-note">Click a company above to open it in InfluenceWeb. Industry rollups aggregate all tracked companies in each sector.</div>
    </div>

    <div class="grid cols-2">
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">PAC Money: Top Recipients</div><div class="card-action" data-goto="political">Politics →</div></div>
        <table class="tf"><thead><tr><th>Politician</th><th class="num">From PACs</th><th class="num">Total Raised</th></tr></thead><tbody>
          ${pacRows.map((r) => `<tr><td><span class="pol-link" data-pol="${esc(r.nm)}">${esc(r.nm)}</span></td><td class="num">${esc(r.pac_fmt)}</td><td class="num">${esc(r.raised || "")}</td></tr>`).join("")}
        </tbody></table>
        <div class="sample-note">Source: OpenFEC. PAC contributions to each member's campaign committee.</div>
      </div>
      <div class="card pad-lg">
        <div class="card-head"><div class="card-title">Lobbying: Industry Groups by Revenue</div></div>
        <table class="tf"><thead><tr><th>Group</th><th class="num">Revenue</th><th class="num">Year</th></tr></thead><tbody>
          ${lobbyRows.map((r) => `<tr><td>${esc(r.nm)}</td><td class="num">${esc(r.rev_fmt)}</td><td class="num">${esc(r.year || "")}</td></tr>`).join("")}
        </tbody></table>
        <div class="sample-note">Source: ProPublica Nonprofit Explorer (IRS Form 990).</div>
      </div>
    </div>`;
}

/* ============================================================
   PAGE: STATES (Constituent Accountability rankings)
   ============================================================ */
function renderStates() {
  const states = Object.entries(STATES).map(([ab, s]) => ({ ab, ...s }))
    .filter((s) => s.prosperity_score != null);
  if (!states.length) return `<div class="page-head"><h2>State Rankings</h2><p>State data not loaded.</p></div>`;
  const byProsperity = [...states].sort((a, b) => b.prosperity_score - a.prosperity_score);
  const byPressure = [...states].sort((a, b) => b.pressure_score - a.pressure_score);
  const byAfford = [...states].sort((a, b) => (b.affordability || 0) - (a.affordability || 0));
  const byReal = [...states].filter((s) => s.real_purchasing_power).sort((a, b) => b.real_purchasing_power - a.real_purchasing_power);
  const m = (v, invert) => { const c = invert ? (v < 40 ? "up" : v < 60 ? "warn" : "down") : (v >= 60 ? "up" : v >= 40 ? "warn" : "down"); return `<span class="pill ${c}">${v}</span>`; };
  const tbl = (arr, key, invert, label) => `
    <div class="card pad-lg">
      <div class="card-head"><div class="card-title">${esc(label)}</div></div>
      <table class="tf"><thead><tr><th>#</th><th>State</th><th class="num">Score</th><th class="num">Med. Income</th><th class="num">Med. Home</th><th class="num">Unemp</th></tr></thead><tbody>
        ${arr.slice(0, 15).map((s, i) => `<tr><td class="faint">${i + 1}</td><td style="font-weight:600;">${esc(s.name)}</td><td class="num">${m(s[key], invert)}</td><td class="num">${money0(s.median_household_income)}</td><td class="num">${money0(s.median_home_value)}</td><td class="num">${s.unemployment ?? "n/a"}%</td></tr>`).join("")}
      </tbody></table>
    </div>`;
  return `
    <div class="page-head"><h2>State Performance Rankings</h2><p>Economic health by state, from FRED and Census ACS. Compare district outcomes with the representatives who serve them.</p></div>
    <div class="grid cols-2">
      ${tbl(byProsperity, "prosperity_score", false, "Constituent Prosperity (highest)")}
      ${tbl(byPressure, "pressure_score", true, "Constituent Pressure (most stressed)")}
    </div>
    ${tbl(byAfford, "affordability", false, "Housing Affordability (most affordable)")}
    <div class="card pad-lg">
      <div class="card-head"><div class="card-title">Real Purchasing Power (income adjusted for cost of living)</div></div>
      <table class="tf"><thead><tr><th>#</th><th>State</th><th class="num">Real Income</th><th class="num">Nominal Income</th><th class="num">Cost of Living</th></tr></thead><tbody>
        ${byReal.slice(0, 20).map((s, i) => `<tr><td class="faint">${i + 1}</td><td style="font-weight:600;">${esc(s.name)}</td><td class="num" style="font-weight:700;">${money0(s.real_purchasing_power)}</td><td class="num muted">${money0(s.median_household_income)}</td><td class="num">${s.cost_of_living} <span class="faint">US=100</span></td></tr>`).join("")}
      </tbody></table>
      <div class="sample-note">Real income = median household income adjusted by BEA Regional Price Parity. A high nominal income in an expensive state buys less.</div>
    </div>`;
}

/* ============================================================
   PAGE: INFLUENCEWEB (graph engine lives in influenceweb.js)
   ============================================================ */
function renderInfluence() {
  return `
    <div class="iw-header">
      <div>
        <h2>InfluenceWeb&trade; <span class="iw-info" title="Explore how sectors, companies, and organizations connect to Congress.">&#9432;</span></h2>
        <p>Explore how sectors, companies, and organizations connect to Congress.</p>
      </div>
      <div class="iw-header-actions">
        <button class="iw-btn" id="iw-filters">Filters</button>
        <button class="iw-btn" id="iw-howto">How It Works</button>
      </div>
    </div>
    <div class="iw-stage">
      <div class="iw-canvas" id="iw-canvas">
        <div class="iw-scene" id="iw-scene">
          <svg class="iw-edges" id="iw-edges" xmlns="http://www.w3.org/2000/svg"></svg>
        </div>
      </div>

      <div class="iw-zoom">
        <button id="iw-zin" title="Zoom in">+</button>
        <button id="iw-zout" title="Zoom out">&minus;</button>
        <button id="iw-fit" title="Reset view">&#9974;</button>
      </div>

      <div id="iw-breadcrumb" class="iw-breadcrumb"></div>

      <div class="iw-legend">
        <div class="iw-legend-item"><span class="iw-dot" style="background:#E5E9F0"></span>Company</div>
        <div class="iw-legend-item"><span class="iw-dot" style="background:#38BDF8"></span>Government</div>
        <div class="iw-legend-item"><span class="iw-dot" style="background:#EF4444"></span>Political</div>
        <div class="iw-legend-item"><span class="iw-dot" style="background:#E9C46A"></span>Financial</div>
        <div class="iw-legend-item"><span class="iw-dot" style="background:#14B8A6"></span>Other</div>
      </div>

      <div id="iw-tip" class="iw-tip"></div>
      <div class="iw-hud" id="iw-hud">Click any sector or company to explore connections</div>

      <aside id="iw-panel" class="iw-panel">
        <button class="iw-panel-close" aria-label="Close">&times;</button>
        <div class="iw-panel-body"></div>
      </aside>
    </div>`;
}

/* ============================================================
   SEARCH
   ============================================================ */
let _searchIndex = null;
function searchIndex() {
  if (_searchIndex) return _searchIndex;
  const idx = [];
  (D.politicians || []).forEach((p) => idx.push({
    type: "pol", key: p.name, group: "Politicians",
    label: p.name, sub: `${p.party || ""} · ${p.state || ""}`, ico: initials(p.name),
  }));
  const seenBill = new Set();
  [...(D.bills || []), ...((D.correlation || {}).top_bills || [])].forEach((b) => {
    if (seenBill.has(b.bill_id)) return;
    seenBill.add(b.bill_id);
    idx.push({
      type: "bill", key: b.bill_id, group: "Bills",
      label: b.bill_id, sub: b.title || "", ico: "BILL",
    });
  });
  (D.events || []).forEach((e) => idx.push({
    type: "event", key: e.id, group: "Historical Events",
    label: e.name, sub: e.date_range || "", ico: "HIST",
  }));
  const tickers = {};
  (D.recent_trades || []).forEach((t) => { if (t.ticker) tickers[t.ticker] = (tickers[t.ticker] || 0) + 1; });
  Object.keys(tickers).forEach((tk) => idx.push({
    type: "page", key: "political", group: "Tickers",
    label: tk, sub: `${tickers[tk]} congressional trades`, ico: tk.slice(0, 4),
  }));
  (D.news || []).forEach((a) => idx.push({
    type: "page", key: "news", group: "News",
    label: a.headline || a.symbol, sub: a.sector || "Markets", ico: a.symbol || "N",
  }));
  (D.everyday || []).forEach((m) => idx.push({
    type: "page", key: "news", group: "Your Costs",
    label: m.category, sub: m.impact, ico: "$",
  }));
  _searchIndex = idx;
  return idx;
}

function runSearch(q) {
  const box = document.getElementById("searchResults");
  q = (q || "").trim().toLowerCase();
  if (q.length < 2) { box.classList.remove("open"); box.innerHTML = ""; return; }

  const caps = { Politicians: 6, Bills: 6, "Historical Events": 4, Tickers: 6, News: 4, "Your Costs": 4 };
  const groups = {};
  for (const item of searchIndex()) {
    if (!(`${item.label} ${item.sub}`.toLowerCase().includes(q))) continue;
    (groups[item.group] = groups[item.group] || []).push(item);
  }
  const order = ["Politicians", "Bills", "Tickers", "Historical Events", "News", "Your Costs"];
  let html = "";
  let total = 0;
  for (const g of order) {
    const items = (groups[g] || []).slice(0, caps[g]);
    if (!items.length) continue;
    html += `<div class="search-group-label">${esc(g)}</div>`;
    html += items.map((it) => `
      <div class="search-item" data-stype="${esc(it.type)}" data-skey="${esc(it.key)}">
        <div class="si-ico">${esc(it.ico)}</div>
        <div class="si-main"><div class="si-title">${esc(it.label)}</div><div class="si-sub">${esc(it.sub)}</div></div>
      </div>`).join("");
    total += items.length;
  }
  box.innerHTML = total ? html : '<div class="search-empty">No matches found</div>';
  box.classList.add("open");
}

function searchDispatch(type, key) {
  document.getElementById("searchResults").classList.remove("open");
  const input = document.getElementById("searchInput");
  if (input) input.value = "";
  if (type === "pol") politicianProfile(key);
  else if (type === "bill") billDetail(key);
  else if (type === "event") { go("history"); eventDetail(key); }
  else if (type === "page") go(key);
}

/* ============================================================
   ROUTER
   ============================================================ */
const PAGES = {
  dashboard: renderDashboard,
  influence: renderInfluence,
  intelligence: renderIntelligence,
  states: renderStates,
  news: renderNews,
  political: renderPolitical,
  portfolio: renderPortfolio,
  markets: renderMarkets,
  reasoning: renderReasoning,
  history: renderHistory,
  settings: renderSettings,
};
const rendered = {};

function go(page) {
  if (!PAGES[page]) page = "dashboard";
  // render lazily, once
  const host = document.getElementById("page-" + page);
  if (host && !rendered[page]) {
    host.innerHTML = PAGES[page]();
    rendered[page] = true;
  }
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  host && host.classList.add("active");
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === page));
  document.querySelector(".viewport").scrollTop = 0;
  location.hash = page;

  // InfluenceWeb graph engine: activate when shown, pause otherwise
  if (window.IW) {
    if (page === "influence") requestAnimationFrame(() => window.IW.activate());
    else window.IW.deactivate();
  }
}

function initTicker() {
  const t = document.getElementById("ticker");
  t.innerHTML = (D.market_ticker || []).map((m) => `
    <span class="tick"><span class="t-label">${esc(m.label)}</span><span class="t-val">${esc(m.value)}</span><span class="t-chg ${m.dir}">${esc(m.change)}</span></span>`).join("");
}

function init() {
  // user chip / greeting
  const u = D.user || {};
  $("#userName").textContent = u.name || "Allan";
  $("#userPlan").textContent = u.plan || "Free Plan";
  $("#userAvatar").textContent = initials(u.name || "Allan");
  $("#greet").textContent = `Good evening, ${u.name || "Allan"}`;

  initTicker();

  // nav clicks
  document.getElementById("nav").addEventListener("click", (e) => {
    const item = e.target.closest(".nav-item");
    if (item) go(item.dataset.page);
  });
  // global click delegation: nav goto, politician profile, full trades, event detail
  document.body.addEventListener("click", (e) => {
    // don't hijack real links (bills, quiver)
    if (e.target.closest("a")) return;

    const secnews = e.target.closest("[data-secnews]");
    if (secnews) { sectorNewsModal(secnews.dataset.secnews); return; }

    const stock = e.target.closest("[data-stock]");
    if (stock && stock.dataset.stock) { stockDetail(stock.dataset.stock); return; }

    const iwco = e.target.closest("[data-iwco]");
    if (iwco) { go("influence"); requestAnimationFrame(() => { if (window.IW && window.IW.openCompany) window.IW.openCompany(iwco.dataset.iwco); }); return; }

    const pol = e.target.closest("[data-pol]");
    if (pol) { politicianProfile(pol.dataset.pol); return; }

    const act = e.target.closest("[data-action]");
    if (act && act.dataset.action === "alltrades") { allTradesView(); return; }

    const bill = e.target.closest("[data-bill]");
    if (bill) { billDetail(bill.dataset.bill); return; }

    const ev = e.target.closest("[data-event]");
    if (ev) { eventDetail(ev.dataset.event); return; }

    const g = e.target.closest("[data-goto]");
    if (g) { go(g.dataset.goto); return; }
  });

  // modal close (button, overlay click, Esc)
  document.getElementById("modalClose").addEventListener("click", closeModal);
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeModal(); document.getElementById("searchResults").classList.remove("open"); }
  });

  // search
  const searchInput = document.getElementById("searchInput");
  searchInput.addEventListener("input", (e) => runSearch(e.target.value));
  searchInput.addEventListener("focus", (e) => { if (e.target.value) runSearch(e.target.value); });
  document.getElementById("searchResults").addEventListener("click", (e) => {
    const it = e.target.closest(".search-item");
    if (it) searchDispatch(it.dataset.stype, it.dataset.skey);
  });
  // close search dropdown on outside click
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) document.getElementById("searchResults").classList.remove("open");
  });

  // dark / light theme toggle (persisted). switch ON = dark (default).
  const tog = document.getElementById("darkToggle");
  const applyTheme = (light) => {
    document.body.classList.toggle("light", light);
    tog.classList.toggle("off", light);
  };
  let lightMode = false;
  try { lightMode = localStorage.getItem("tf-theme") === "light"; } catch (e) {}
  applyTheme(lightMode);
  tog.addEventListener("click", () => {
    lightMode = !lightMode;
    applyTheme(lightMode);
    try { localStorage.setItem("tf-theme", lightMode ? "light" : "dark"); } catch (e) {}
  });

  go(location.hash.replace("#", "") || "dashboard");
}

document.addEventListener("DOMContentLoaded", init);
