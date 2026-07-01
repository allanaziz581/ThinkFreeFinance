import Reveal from "../components/ui/Reveal.jsx";
import InfluenceMap from "../components/InfluenceMap.jsx";
import { GitBranch, Landmark, LineChart } from "lucide-react";

const CHAIN = ["The law", "Who it pays", "Who knew", "Who traded", "The payoff", "The pattern"];
const LEGEND = [
  ["Government", "#38BDF8"],
  ["Company", "#E5E9F0"],
  ["Political", "#EF4444"],
  ["Financial", "#E9C46A"],
];
const CELLS = [
  { icon: GitBranch, title: "One connected graph", body: "Congress, companies, trades, contracts, and lobbying in a single network you trace end to end." },
  { icon: Landmark, title: "From the law outward", body: "Start at a bill and branch to the sectors and firms it pays, then to who lobbied for it." },
  { icon: LineChart, title: "Who traded, and when", body: "Disclosed congressional trades aligned in time with the legislation they precede." },
];

export default function InfluencePillar() {
  return (
    <section id="influence" className="border-b border-line pt-18 sm:pt-22">
      <div className="lp-shell">
        <Reveal>
          <div className="t-label">02 / Influence network</div>
          <h2 className="t-h2 mt-3 max-w-2xl">The Influence Map</h2>
          <p className="t-lead mt-4 max-w-2xl">
            A living map of the connections between Congress, companies, congressional trades,
            government contracts, and lobbying. Hover any node to light up its ties. Follow the money
            from a law to who it pays, who knew, and who traded.
          </p>
        </Reveal>
      </div>

      {/* prominent full-bleed interactive map that fills the section */}
      <div className="relative mt-9 h-[min(74vh,660px)] w-full overflow-hidden border-y border-line bg-ink-800/40">
        <InfluenceMap />
        {/* soft top/bottom scrims so overlays stay readable */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
             style={{ background: "linear-gradient(0deg, #070A0F 4%, rgba(7,10,15,0) 100%)" }} />
        {/* legend */}
        <div className="pointer-events-none absolute right-4 top-4 z-10 hidden flex-wrap gap-x-3 gap-y-1 rounded-ctl border border-line bg-ink-900/70 px-2.5 py-1.5 text-[10.5px] text-ash-300 sm:flex">
          {LEGEND.map(([k, c]) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
              {k}
            </span>
          ))}
        </div>
        {/* chain-of-evidence overlaid at the bottom */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 pb-5">
          <div className="lp-shell">
            <ol className="flex flex-wrap items-center gap-x-2 gap-y-2" aria-label="The chain of evidence">
              {CHAIN.map((step, i) => (
                <li key={step} className="lp-chip bg-ink-900/80">
                  <span className="num font-semibold text-brand">{i + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      {/* supporting cells so the section reads full and dense */}
      <div className="lp-shell py-9 sm:py-11">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {CELLS.map((c, i) => {
            const Icon = c.icon;
            return (
              <Reveal key={c.title} delay={i * 0.05}>
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
