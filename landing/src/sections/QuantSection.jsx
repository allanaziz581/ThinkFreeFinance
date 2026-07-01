import Reveal from "../components/ui/Reveal.jsx";
import { Code2 } from "lucide-react";

const TILES = [
  { k: "Value at Risk", v: "4.2", u: "%", note: "95% 1-day, per position" },
  { k: "Kelly sizing", v: "0.18", u: "x", note: "fraction of bankroll" },
  { k: "Sharpe ratio", v: "1.34", u: "", note: "risk-adjusted return" },
  { k: "Prob. of profit", v: "62", u: "%", note: "modeled, not promised" },
];

const CARDS = [
  {
    title: "Event-study analysis",
    body: "Abnormal-return analysis measures how a stock actually moved around an event, against its own baseline, market adjusted.",
    metrics: ["Abnormal return", "Market adjusted"],
  },
  {
    title: "Money Trail scoring",
    body: "A transparent chain-of-evidence model scores each law on six links: the law, who it pays, who knew, who traded, the payoff, and the pattern.",
    metrics: ["Chain of evidence", "Every weight visible"],
  },
  {
    title: "Opportunity scores",
    body: "Signals are scored on expected return, risk, and confidence, then ranked, so the strongest setups rise to the top.",
    metrics: ["Expected return", "Confidence"],
  },
  {
    title: "Recession signals",
    body: "Macro, market, and behavioral indicators roll up into a single recession-risk read you can track day to day.",
    metrics: ["Yield curve", "Risk score"],
  },
];

export default function QuantSection() {
  return (
    <section id="quant" className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <Reveal>
          <div className="t-label">03 / Quant and math</div>
          <h2 className="t-h2 mt-3 max-w-3xl">
            Predictive modeling, powered by{" "}
            <span className="whitespace-nowrap rounded-ctl bg-brand-glow px-2 py-0.5 text-brand">
              Quant and Math
            </span>
          </h2>
          <p className="t-lead mt-4 max-w-2xl">
            Every calculation runs in code, through the Quant library, in Python. The math is real,
            not AI. AI is used only as a translation layer that turns the numbers into plain English,
            so the average person can understand what they mean.
          </p>
          <div className="mt-5 inline-flex items-center gap-2 rounded-ctl border border-line bg-ink-800 px-3 py-1.5">
            <Code2 className="h-4 w-4 text-brand" />
            <span className="t-small text-ash-300">Calculated in Python. Translated into plain English.</span>
          </div>
        </Reveal>

        {/* headline metric tiles */}
        <div className="mt-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {TILES.map((t, i) => (
            <Reveal key={t.k} delay={i * 0.04}>
              <div className="lp-card h-full p-5">
                <div className="text-[12px] text-ash-500">{t.k}</div>
                <div className="mt-2 flex items-baseline gap-0.5">
                  <span className="num text-[30px] font-bold leading-none text-ash-100">{t.v}</span>
                  <span className="num text-[15px] text-ash-300">{t.u}</span>
                </div>
                <div className="t-small mt-2">{t.note}</div>
              </div>
            </Reveal>
          ))}
        </div>

        {/* analysis cards */}
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {CARDS.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.04}>
              <div className="lp-card h-full p-5 sm:p-6">
                <h3 className="t-h3">{c.title}</h3>
                <p className="t-body mt-2">{c.body}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {c.metrics.map((m) => (
                    <span key={m} className="lp-metric">
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <p className="t-small mt-6 max-w-2xl">
          The Quant library computes VaR, Kelly sizing, Sharpe, probability of profit, event-study
          abnormal returns, Money Trail scores, opportunity scores, and recession signals in code.
          AI only turns those numbers into plain language. Informational, not investment advice, and
          not a promise of future results.
        </p>
      </div>
    </section>
  );
}
