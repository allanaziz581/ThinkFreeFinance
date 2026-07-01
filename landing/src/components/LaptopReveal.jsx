import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";
import AppDashboard from "./AppDashboard.jsx";

/**
 * Laptop scroll reveal. A clearly visible laptop whose lid rotates up from nearly
 * closed to open as the user scrolls, revealing the real ThinkFree dashboard on
 * the screen. Pure CSS 3D transforms driven by scroll (no WebGL). The dashboard
 * is the front face the whole time, so it is never hidden. Reduced-motion shows
 * it open and static.
 */
export default function LaptopReveal() {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  // lid lifts from nearly-closed (folded back) to open+upright
  const lid = useTransform(scrollYProgress, [0.12, 0.62], [82, 4]);
  const scale = useTransform(scrollYProgress, [0, 0.62], [0.92, 1]);
  const glow = useTransform(scrollYProgress, [0.2, 0.62], [0, 1]);
  const headY = useTransform(scrollYProgress, [0, 0.2], [24, 0]);
  const headO = useTransform(scrollYProgress, [0, 0.2], [0.3, 1]);

  const lidStyle = reduce
    ? { transform: "rotateX(4deg)" }
    : { rotateX: lid, transformOrigin: "50% 100%", transformStyle: "preserve-3d" };

  return (
    <section ref={ref} className="relative h-[230vh] border-b border-line">
      <div className="sticky top-0 flex h-screen flex-col items-center justify-center overflow-hidden px-4">
        <motion.div
          style={reduce ? undefined : { y: headY, opacity: headO }}
          className="mb-8 max-w-2xl text-center"
        >
          <div className="t-label">See it in action</div>
          <h2 className="t-h2 mt-3">The whole picture, on one screen</h2>
          <p className="t-lead mx-auto mt-3 max-w-xl">
            Scroll to open ThinkFree. Everything in one place, in plain English.
          </p>
        </motion.div>

        <div style={{ perspective: "1400px" }} className="flex w-full justify-center">
          <motion.div
            style={reduce ? undefined : { scale, rotateX: 8, transformStyle: "preserve-3d" }}
            className="relative"
          >
            {/* screen / lid */}
            <motion.div
              style={lidStyle}
              className="relative h-[min(52vw,420px)] w-[min(84vw,680px)] overflow-hidden rounded-t-[14px] border-[3px] border-ink-600 bg-ink-900 shadow-[0_30px_80px_rgba(0,0,0,0.55)]"
            >
              <div className="h-full w-full">
                <AppDashboard />
              </div>
              {/* screen sheen + power-on glow */}
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-transparent via-transparent to-white/[0.05]" />
              <motion.div
                aria-hidden="true"
                className="pointer-events-none absolute inset-0"
                style={{
                  opacity: reduce ? 0.25 : glow,
                  background: "radial-gradient(60% 50% at 50% 40%, rgba(56,189,248,0.10), transparent 70%)",
                }}
              />
            </motion.div>

            {/* body / keyboard deck (front lip of the laptop base) */}
            <div className="relative mx-auto h-[16px] w-[min(88vw,712px)] rounded-b-[12px] rounded-t-[3px] border border-ink-600 bg-gradient-to-b from-ink-600 to-ink-700">
              <div className="absolute left-1/2 top-0 h-[5px] w-[70px] -translate-x-1/2 rounded-b-[6px] bg-ink-800" />
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
