import Reveal from "../components/ui/Reveal.jsx";
import SectionHead from "../components/ui/SectionHead.jsx";

// Bento grid: a wide lead card, then the supporting analyses. Each card states
// what the math is, framed as transparent analysis, never a guaranteed outcome.
const CARDS = [
  {
    title: "Risk and return metrics",
    body: "The quant library computes the core numbers behind every opportunity, so risk is measured, not guessed.",
    metrics: ["Value at Risk", "Kelly sizing", "Sharpe ratio", "Probability of profit"],
    wide: true,
  },
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
  {
    title: "Transparent by design",
    body: "This is analysis, not advice and not a guarantee. The math is shown so you can judge it yourself, then decide.",
    metrics: ["Inputs shown", "No black box"],
  },
];

function QCard({ card }) {
  return (
    <Reveal className={card.wide ? "sm:col-span-2" : ""}>
      <div className="lp-card h-full p-5 sm:p-6">
        <h3 className="t-h3">{card.title}</h3>
        <p className="t-body mt-2">{card.body}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {card.metrics.map((m) => (
            <span key={m} className="lp-metric">
              {m}
            </span>
          ))}
        </div>
      </div>
    </Reveal>
  );
}

export default function QuantSection() {
  return (
    <section id="quant" className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <SectionHead
          label="The substance"
          title="Predictive modeling, powered by quant and math"
          lead="The quant library calculates everything. Not opinions, real math, shown transparently. Every score shows its inputs and weights, so you can see exactly how a number was reached."
        />

        <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CARDS.map((c) => (
            <QCard key={c.title} card={c} />
          ))}
        </div>

        <p className="t-small mt-6 max-w-2xl">
          ThinkFree is an AI-powered research analyst and economic translator. The numbers above are
          transparent, math-based analysis of public data. They are informational, not investment
          advice, and not a promise of future results.
        </p>
      </div>
    </section>
  );
}
