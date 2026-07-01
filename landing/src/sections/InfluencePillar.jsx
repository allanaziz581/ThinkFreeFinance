import Reveal from "../components/ui/Reveal.jsx";
import { GitBranch, Landmark, Building2, LineChart, ArrowRight } from "lucide-react";

const CHAIN = ["The law", "Who it pays", "Who knew", "Who traded", "The payoff", "The pattern"];

// A bento feature grid (distinct from the hero map): one wide lead cell plus
// supporting cells, each a facet of the influence graph.
const CELLS = [
  {
    icon: GitBranch,
    title: "One connected graph",
    body: "Congress, companies, trades, contracts, and lobbying live in a single network you can trace end to end, not scattered across tabs.",
    wide: true,
  },
  {
    icon: Landmark,
    title: "From the law outward",
    body: "Start at a bill and branch to the sectors and companies it touches.",
  },
  {
    icon: Building2,
    title: "Who it pays",
    body: "Government contracts and lobbying, tied to the firms that receive them.",
  },
  {
    icon: LineChart,
    title: "Who traded",
    body: "Disclosed congressional trades, aligned in time with related legislation.",
  },
];

export default function InfluencePillar() {
  return (
    <section id="influence" className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <Reveal>
          <div className="t-label">The signature view</div>
          <h2 className="t-h2 mt-3 max-w-2xl">The Influence Map</h2>
          <p className="t-lead mt-4 max-w-2xl">
            A living map of the connections between Congress, companies, congressional trades,
            government contracts, and lobbying. Follow the money from a law to who it pays, who knew,
            and who traded.
          </p>
        </Reveal>

        {/* chain-of-evidence stepper */}
        <Reveal delay={0.05}>
          <ol
            className="mt-8 flex flex-wrap items-center gap-x-2 gap-y-2"
            aria-label="The chain of evidence"
          >
            {CHAIN.map((step, i) => (
              <li key={step} className="flex items-center gap-2">
                <span className="lp-chip">
                  <span className="num font-semibold text-brand">{i + 1}</span>
                  {step}
                </span>
                {i < CHAIN.length - 1 ? (
                  <ArrowRight className="h-3.5 w-3.5 text-ash-500" aria-hidden="true" />
                ) : null}
              </li>
            ))}
          </ol>
        </Reveal>

        {/* bento */}
        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CELLS.map((c, i) => {
            const Icon = c.icon;
            return (
              <Reveal key={c.title} delay={i * 0.05} className={c.wide ? "lg:col-span-1 sm:col-span-2" : ""}>
                <div className="lp-card h-full p-6">
                  <div className="mb-4 grid h-10 w-10 place-items-center rounded-ctl border border-line bg-ink-700 text-brand">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="t-h3">{c.title}</h3>
                  <p className="t-body mt-2">{c.body}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
