import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

/**
 * Intro loader: a LARGE glowing orb that fills the screen and encapsulates all of
 * the loading content (brand, progress bar, percentage sit inside the orb). The
 * orb center is deep so the text stays readable, with a luminous cyan rim and a
 * slow rotating sheen. On completion the whole thing glides open (scale + fade)
 * into the site loading beneath. Click, scroll, or touch to enter. Skipped under
 * prefers-reduced-motion. Native CSS gradients, no WebGL.
 */
export default function IntroLoader({ onDone }) {
  const reduce = useReducedMotion();
  const [pct, setPct] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (reduce) { onDone(); return; }
    let raf = 0;
    const start = performance.now();
    const DUR = 1500;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / DUR);
      setPct(Math.round((1 - Math.pow(1 - p, 2.2)) * 100));
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
    window.setTimeout(onDone, 680);
  }

  return (
    <motion.div
      className="fixed inset-0 z-[200] flex items-center justify-center overflow-hidden bg-ink-900"
      initial={{ opacity: 1 }}
      animate={leaving ? { opacity: 0 } : { opacity: 1 }}
      transition={{ duration: 0.62, ease: [0.76, 0, 0.24, 1] }}
      onClick={finish}
      onWheel={finish}
      onTouchStart={finish}
      role="progressbar"
      aria-valuenow={pct}
      aria-label="Loading ThinkFree"
    >
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-30" />

      {/* the enveloping orb */}
      <motion.div
        className="relative grid place-items-center rounded-full"
        style={{
          width: "min(92vw, 92vh, 680px)",
          height: "min(92vw, 92vh, 680px)",
        }}
        initial={{ scale: 0.92, opacity: 0 }}
        animate={leaving ? { scale: 1.7, opacity: 0 } : { scale: 1, opacity: 1 }}
        transition={{ duration: leaving ? 0.62 : 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* outer soft glow */}
        <div className="absolute inset-0 rounded-full"
             style={{ boxShadow: "0 0 120px 20px rgba(56,189,248,0.16), inset 0 0 120px rgba(56,189,248,0.10)" }} />
        {/* rotating rim sheen */}
        <div className="absolute inset-0 animate-[spin_9s_linear_infinite] rounded-full"
             style={{
               background: "conic-gradient(from 0deg, rgba(56,189,248,0) 0deg, rgba(56,189,248,0.55) 60deg, rgba(125,211,252,0.10) 150deg, rgba(56,189,248,0) 240deg, rgba(56,189,248,0.4) 320deg, rgba(56,189,248,0) 360deg)",
               WebkitMask: "radial-gradient(closest-side, transparent 93%, #000 95%)",
               mask: "radial-gradient(closest-side, transparent 93%, #000 95%)",
               filter: "blur(1px)",
             }} />
        {/* readable deep-center fill with luminous edge */}
        <div className="absolute inset-0 rounded-full border border-brand/20"
             style={{
               background: "radial-gradient(circle at 50% 44%, rgba(7,10,15,0.97) 0%, rgba(9,22,36,0.94) 40%, rgba(30,110,160,0.34) 74%, rgba(125,211,252,0.14) 90%, rgba(56,189,248,0) 100%)",
             }} />

        {/* content inside the orb */}
        <div className="relative flex flex-col items-center px-8 text-center">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-ctl bg-brand text-[14px] font-bold text-ink-900">TF</span>
            <span className="text-[22px] font-semibold tracking-tight">Think<span className="text-brand">Free</span></span>
          </div>
          <p className="t-small mt-3 max-w-[260px] text-ash-300">
            Mapping influence. Running the math.
          </p>
          <div className="mt-6 h-[3px] w-[min(60vw,260px)] overflow-hidden rounded-full bg-white/[0.10]">
            <div className="h-full rounded-full bg-brand transition-[width] duration-100 ease-out" style={{ width: `${pct}%` }} />
          </div>
          <div className="num mt-3 text-[13px] text-ash-300">{pct < 100 ? `Loading ${pct}%` : "Ready"}</div>
          <div className="mt-1 text-[11px] text-ash-500">Click or scroll to enter</div>
        </div>
      </motion.div>
    </motion.div>
  );
}
