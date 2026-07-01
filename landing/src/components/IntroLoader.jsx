import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

/**
 * Intro loading reveal (item 4): a brief branded loading screen with a progress
 * bar while the page settles, then it slides up to reveal the site. The user can
 * also click or scroll to enter immediately. Reduced-motion skips the animation.
 */
export default function IntroLoader({ onDone }) {
  const reduce = useReducedMotion();
  const [pct, setPct] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (reduce) {
      onDone();
      return;
    }
    let raf = 0;
    const start = performance.now();
    const DUR = 1300;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / DUR);
      // ease-out so it decelerates toward 100
      const eased = 1 - Math.pow(1 - p, 2.2);
      setPct(Math.round(eased * 100));
      if (p < 1) raf = requestAnimationFrame(tick);
      else finish();
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function finish() {
    if (leaving) return;
    setPct(100);
    setLeaving(true);
    // let the slide-up transition play, then unmount
    window.setTimeout(onDone, 620);
  }

  return (
    <motion.div
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-ink-900"
      initial={{ y: 0 }}
      animate={leaving ? { y: "-100%" } : { y: 0 }}
      transition={{ duration: 0.6, ease: [0.76, 0, 0.24, 1] }}
      onClick={finish}
      onWheel={finish}
      role="progressbar"
      aria-valuenow={pct}
      aria-label="Loading ThinkFree"
    >
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
      <div className="relative flex flex-col items-center">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-ctl bg-brand text-[14px] font-bold text-ink-900">
            TF
          </span>
          <span className="text-[20px] font-semibold tracking-tight">
            Think<span className="text-brand">Free</span>
          </span>
        </div>

        <div className="mt-7 h-[3px] w-[220px] overflow-hidden rounded-full bg-white/[0.08]">
          <div
            className="h-full rounded-full bg-brand transition-[width] duration-100 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="num mt-3 text-[12px] text-ash-500">
          {pct < 100 ? `Loading ${pct}%` : "Enter"}
        </div>
        <div className="mt-1 text-[11px] text-ash-500/70">Click or scroll to enter</div>
      </div>
    </motion.div>
  );
}
