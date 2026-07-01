import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";
import AppDashboard from "./AppDashboard.jsx";

/**
 * Apple-style laptop scroll reveal (item 3): the laptop starts turned away
 * (facing back) with the lid nearly closed; as the user scrolls it rotates
 * around to face front and the lid opens from closed to open, revealing the real
 * ThinkFree dashboard on the screen. Pure CSS 3D transforms driven by scroll
 * progress (no WebGL). Reduced-motion shows it open and front-facing, static.
 */
export default function LaptopReveal() {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  // whole-assembly spin: from facing away (180) to facing us (0)
  const rotateY = useTransform(scrollYProgress, [0.05, 0.6], [180, 0]);
  // gentle downward tilt so we look slightly onto the screen
  const rotateX = useTransform(scrollYProgress, [0, 1], [14, 6]);
  const scale = useTransform(scrollYProgress, [0, 0.6, 1], [0.82, 1, 1.03]);
  // lid opening: folded onto the deck (closed) to upright (open)
  const lid = useTransform(scrollYProgress, [0.3, 0.9], [-88, 0]);
  const headOpacity = useTransform(scrollYProgress, [0, 0.18], [0.35, 1]);

  const staticStyle = reduce
    ? { transform: "rotateX(6deg) rotateY(0deg) scale(1)" }
    : { rotateX, rotateY, scale, transformStyle: "preserve-3d" };
  const lidStyle = reduce ? { transform: "rotateX(0deg)" } : { rotateX: lid };

  return (
    <section ref={ref} className="relative h-[240vh] border-b border-line">
      <div className="sticky top-0 flex h-screen flex-col items-center justify-center overflow-hidden">
        <motion.div
          style={reduce ? undefined : { opacity: headOpacity }}
          className="mb-8 max-w-2xl px-5 text-center"
        >
          <div className="t-label">See it in action</div>
          <h2 className="t-h2 mt-3">The whole picture, on one screen</h2>
          <p className="t-lead mx-auto mt-3 max-w-xl">
            Scroll to open ThinkFree. Everything in one place, in plain English.
          </p>
        </motion.div>

        {/* 3D stage */}
        <div style={{ perspective: "1500px" }} className="flex w-full items-center justify-center">
          <motion.div
            style={staticStyle}
            className="relative"
          >
            {/* lid / screen (hinge at its bottom edge) */}
            <motion.div
              style={{ ...lidStyle, transformOrigin: "bottom center", transformStyle: "preserve-3d" }}
              className="relative h-[min(46vw,360px)] w-[min(74vw,580px)] rounded-t-[12px]"
            >
              {/* screen front: the real dashboard */}
              <div
                className="absolute inset-0 overflow-hidden rounded-t-[12px] border border-line-strong bg-ink-900"
                style={{ backfaceVisibility: "hidden" }}
              >
                <div className="h-full w-full origin-top-left" style={{ transform: "scale(1)" }}>
                  <AppDashboard />
                </div>
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-transparent via-transparent to-white/[0.04]" />
              </div>
              {/* lid back: aluminum with brand mark, seen when facing away */}
              <div
                className="absolute inset-0 grid place-items-center rounded-t-[12px] border border-line-strong bg-ink-700"
                style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
              >
                <div className="flex items-center gap-2 opacity-70">
                  <span className="grid h-7 w-7 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">
                    TF
                  </span>
                  <span className="text-[15px] font-semibold tracking-tight text-ash-100">
                    Think<span className="text-brand">Free</span>
                  </span>
                </div>
              </div>
            </motion.div>

            {/* base / keyboard deck (lies flat forward from the hinge) */}
            <div
              className="absolute left-1/2 top-full h-[min(30vw,230px)] w-[min(74vw,580px)] -translate-x-1/2 rounded-b-[12px] border border-line-strong bg-ink-700"
              style={{ transformOrigin: "top center", transform: "rotateX(90deg)" }}
            >
              <div className="mx-auto mt-4 h-[54%] w-[86%] rounded-[6px] border border-line bg-ink-800/70" />
              <div className="mx-auto mt-2 h-[16%] w-[34%] rounded-[6px] border border-line bg-ink-800/50" />
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
