import Reveal from "../components/ui/Reveal.jsx";
import InfluenceMap from "../components/InfluenceMap.jsx";

const CHAIN = ["The law", "Who it pays", "Who knew", "Who traded", "The payoff", "The pattern"];

export default function InfluencePillar() {
  return (
    <section id="influence" className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <Reveal>
          <div className="t-label">The signature view</div>
          <h2 className="t-h2 mt-3">The Influence Map</h2>
          <p className="t-lead mt-4 max-w-xl">
            A living map of the connections between Congress, companies, congressional trades,
            government contracts, and lobbying. Tap a sector and its companies branch out across the
            graph. Follow the money from a law to who it pays, who knew, and who traded.
          </p>

          <ol className="mt-7 flex flex-wrap gap-2" aria-label="The chain of evidence">
            {CHAIN.map((step, i) => (
              <li key={step} className="lp-chip">
                <span className="font-semibold text-brand">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </Reveal>

        <Reveal delay={0.08}>
          <div className="overflow-hidden rounded-panel border border-line bg-ink-800 [aspect-ratio:16/12]">
            <InfluenceMap />
          </div>
        </Reveal>
      </div>
    </section>
  );
}
