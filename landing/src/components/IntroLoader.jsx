import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

/**
 * Intro loader: a glowing sphere (the AI-loader concept, built natively with CSS
 * gradients and a rotating sheen, no WebGL) over a progress bar, which then glides
 * open into the site (scale + fade, not a hard cut) while assets load beneath.
 * Click or scroll to enter; skipped under prefers-reduced-motion.
 */
export default function IntroLoader({ onDone }) {
  const reduce = useReducedMotion();
  const [pct, setPct] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (reduce) { onDone(); return; }
    let raf = 0;
    const start = performance.now();
    const DUR = 1400;
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
    window.setTimeout(onDone, 640);
  }

  return (
    <motion.div
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-ink-900"
      initial={{ opacity: 1, scale: 1 }}
      animate={leaving ? { opacity: 0, scale: 1.08 } : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: [0.76, 0, 0.24, 1] }}
      onClick={finish}
      onWheel={finish}
      onTouchStart={finish}
      role="progressbar"
      aria-valuenow={pct}
      aria-label="Loading ThinkFree"
    >
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-40" />

      {/* glowing sphere */}
      <div className="relative mb-9 h-28 w-28">
        <div className="absolute inset-0 animate-[spin_6s_linear_infinite] rounded-full"
             style={{ background: "conic-gradient(from 0deg, rgba(56,189,248,0) 0%, rgba(56,189,248,0.55) 25%, rgba(125,211,252,0.15) 50%, rgba(56,189,248,0) 75%)", filter: "blur(2px)" }} />
        <div className="absolute inset-[6px] rounded-full"
             style={{
               background: "radial-gradient(35% 35% at 38% 32%, rgba(224,246,255,0.95), rgba(56,189,248,0.9) 30%, rgba(20,90,140,0.9) 62%, rgba(6,16,26,0.95) 100%)",
               boxShadow: "0 0 40px rgba(56,189,248,0.35), inset 0 0 24px rgba(0,0,0,0.5)",
             }} />
        <div className="absolute inset-[6px] rounded-full mix-blend-screen"
             style={{ background: "radial-gradient(28% 24% at 36% 28%, rgba(255,255,255,0.85), transparent 60%)" }} />
      </div>

      <div className="relative flex flex-col items-center">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-ctl bg-brand text-[13px] font-bold text-ink-900">TF</span>
          <span className="text-[18px] font-semibold tracking-tight">Think<span className="text-brand">Free</span></span>
        </div>
        <div className="mt-6 h-[3px] w-[220px] overflow-hidden rounded-full bg-white/[0.08]">
          <div className="h-full rounded-full bg-brand transition-[width] duration-100 ease-out" style={{ width: `${pct}%` }} />
        </div>
        <div className="num mt-3 text-[12px] text-ash-500">{pct < 100 ? `Loading ${pct}%` : "Ready"}</div>
        <div className="mt-1 text-[11px] text-ash-500/70">Click or scroll to enter</div>
      </div>
    </motion.div>
  );
}
