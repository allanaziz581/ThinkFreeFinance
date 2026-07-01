import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import InfluenceMap from "../components/InfluenceMap.jsx";

const EASE = [0.22, 1, 0.36, 1];

// Two stat cards that sit under the map so the visual column reads as a
// deliberate composition, not empty space (item 2).
const STATS = [
  { v: "5,207", k: "Disclosures traced" },
  { v: "128", k: "Signals ranked daily" },
];

export default function Hero({ onSignIn }) {
  const reduce = useReducedMotion();
  const rise = (delay) =>
    reduce
      ? {}
      : {
          initial: { opacity: 0, y: 16 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.6, delay, ease: EASE },
        };

  return (
    <section className="relative isolate overflow-hidden border-b border-line">
      <div aria-hidden="true" className="bg-grid pointer-events-none absolute inset-0 -z-10" />

      <div className="lp-shell grid items-center gap-12 py-18 sm:py-22 lg:grid-cols-[1.02fr_0.98fr] lg:gap-16 lg:py-30">
        <div>
          <motion.h1 {...rise(0)} className="t-display max-w-xl">
            Map the influence.
            <br />
            <span className="text-brand">See the math.</span>
          </motion.h1>

          <motion.p {...rise(0.08)} className="t-lead mt-6 max-w-xl">
            ThinkFree connects Congress, companies, trades, contracts, and lobbying, runs the real
            math in code, and puts it all in one place in plain English, so anyone can understand
            what is going on.
          </motion.p>

          <motion.div {...rise(0.16)} className="mt-9 flex flex-wrap gap-3">
            <a className="lp-btn lp-btn-primary lp-btn-lg" href="/app">
              Open the app <ArrowRight className="h-4 w-4" />
            </a>
            <button className="lp-btn lp-btn-ghost lp-btn-lg" onClick={onSignIn} type="button">
              Sign in
            </button>
          </motion.div>

          <motion.p {...rise(0.22)} className="t-small mt-7">
            Informational research, not financial advice. Built on public records.
          </motion.p>
        </div>

        {/* Visual column: the ONE influence map, plus two stat cards (no empty space). */}
        <motion.div
          initial={reduce ? {} : { opacity: 0 }}
          animate={reduce ? {} : { opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.18, ease: EASE }}
          className="w-full"
        >
          <div className="relative overflow-hidden rounded-panel border border-line bg-ink-800 [aspect-ratio:16/11]">
            <InfluenceMap />
            <span className="pointer-events-none absolute left-3 top-3 rounded-ctl border border-line bg-ink-900/70 px-2 py-1 text-[10.5px] text-ash-300">
              Live influence graph, hover to explore
            </span>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            {STATS.map((s) => (
              <div key={s.k} className="lp-card p-4">
                <div className="num text-[22px] font-bold text-ash-100">{s.v}</div>
                <div className="t-small mt-1">{s.k}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
