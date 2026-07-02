import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import InfluenceMap from "../components/InfluenceMap.jsx";

const EASE = [0.22, 1, 0.36, 1];

const LEGEND = [
  ["Government", "#38BDF8"],
  ["Company", "#E5E9F0"],
  ["Political", "#EF4444"],
  ["Financial", "#E9C46A"],
];

export default function Hero({ onSignIn }) {
  const reduce = useReducedMotion();
  const rise = (delay) =>
    reduce
      ? {}
      : {
          initial: { opacity: 0, y: 16 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.7, delay, ease: EASE },
        };

  return (
    <section className="relative flex min-h-[92vh] items-center overflow-hidden border-b border-line">
      {/* Full-bleed interactive influence network (no card box). */}
      <InfluenceMap />

      {/* Readability scrims: a left wash for the copy, a soft vignette, and a
          bottom fade into the page. pointer-events-none so the map stays hoverable. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, rgba(10,11,13,0.94) 0%, rgba(10,11,13,0.78) 34%, rgba(10,11,13,0.28) 60%, rgba(10,11,13,0) 78%), linear-gradient(0deg, #0A0B0D 2%, rgba(10,11,13,0) 26%)",
        }}
      />
      <div aria-hidden="true" className="bg-grid pointer-events-none absolute inset-0 opacity-40" />

      {/* Copy overlay. The wrapper is pointer-events-none so mouse-move reaches the
          canvas beneath; only the buttons re-enable pointer events. */}
      <div className="lp-shell pointer-events-none relative z-10 py-24">
        <div className="max-w-xl">
          <motion.h1 {...rise(0)} className="t-display">
            See the influence.
            <br />
            <span className="text-brand">Predict the market.</span>
          </motion.h1>

          <motion.p {...rise(0.1)} className="t-lead mt-6 max-w-lg">
            ThinkFree maps how Congress, companies, trades, contracts, and lobbying connect, then
            runs predictive quant analysis in code to model where the market may move, and puts it
            all in plain English. Transparent math, not guarantees.
          </motion.p>

          <motion.div {...rise(0.22)} className="pointer-events-auto mt-9 flex flex-wrap gap-3">
            <a className="lp-btn lp-btn-primary lp-btn-lg" href="/app">
              Open the app <ArrowRight className="h-4 w-4" />
            </a>
            <button className="lp-btn lp-btn-ghost lp-btn-lg" onClick={onSignIn} type="button">
              Sign in
            </button>
          </motion.div>

          <motion.p {...rise(0.28)} className="t-small mt-7">
            Informational research, not financial advice. Built on public records.
          </motion.p>
        </div>
      </div>

      {/* category legend */}
      <div className="pointer-events-none absolute bottom-4 right-4 z-10 hidden flex-wrap gap-x-3 gap-y-1 rounded-ctl border border-line bg-ink-900/70 px-2.5 py-1.5 text-[10.5px] text-ash-300 sm:flex">
        {LEGEND.map(([k, c]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
            {k}
          </span>
        ))}
      </div>
    </section>
  );
}
