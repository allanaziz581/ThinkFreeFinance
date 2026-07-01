import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import InfluenceMap from "../components/InfluenceMap.jsx";

const EASE = [0.22, 1, 0.36, 1];

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
      {/* Vercel-style graph-paper backdrop: fine hairline grid, radial-masked.
          No glow, no colored orb. */}
      <div aria-hidden="true" className="bg-grid pointer-events-none absolute inset-0 -z-10" />

      <div className="lp-shell grid items-center gap-12 py-18 sm:py-22 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:py-30">
        <div>
          <motion.h1 {...rise(0)} className="t-display max-w-xl">
            Map the influence.
            <br />
            <span className="text-brand">See the math.</span>
          </motion.h1>

          <motion.p {...rise(0.08)} className="t-lead mt-6 max-w-xl">
            ThinkFree maps how Congress, companies, congressional trades, government contracts, and
            lobbying connect, then runs transparent quantitative analysis and translates it into
            plain English.
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

        {/* The ONE influence map on the whole page. */}
        <motion.div
          initial={reduce ? {} : { opacity: 0 }}
          animate={reduce ? {} : { opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.18, ease: EASE }}
          className="w-full"
        >
          <div className="overflow-hidden rounded-panel border border-line bg-ink-800 [aspect-ratio:16/12]">
            <InfluenceMap />
          </div>
          <p className="t-small mt-3">
            A live network of sectors, companies, and Congress. Connections trace back to public
            disclosures.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
