import { useRef } from "react";
import { motion, useScroll, useSpring, useTransform, useReducedMotion } from "framer-motion";
import AppDashboard from "./AppDashboard.jsx";

/**
 * Laptop scroll reveal. A large light SILVER laptop, kept vertically CENTERED in
 * the viewport, whose lid opens in sync with scroll (1:1, smoothed by a light
 * spring so it never stutters). The open completes with a short tail before the
 * section releases to the next one. Moderate scroll distance: deliberate but not
 * locked. The heading is pinned at the top. Pure CSS 3D (no WebGL); reduced-motion
 * shows it open and static.
 */
export default function LaptopReveal() {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  // Light spring smooths scroll jank while still tracking position closely.
  const smooth = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.35 });

  const lid = useTransform(smooth, [0.06, 0.82], [80, 3]);
  const scale = useTransform(smooth, [0, 0.82], [0.96, 1]);
  const glow = useTransform(smooth, [0.28, 0.82], [0, 1]);

  const lidStyle = reduce
    ? { transform: "rotateX(3deg)" }
    : { rotateX: lid, transformOrigin: "50% 100%", transformStyle: "preserve-3d" };

  return (
    <section ref={ref} className="relative h-[160vh] border-b border-line">
      <div className="sticky top-0 h-screen overflow-hidden">
        {/* pinned heading at the top */}
        <div className="absolute inset-x-0 top-0 px-4 pt-20 text-center">
          <div className="t-label justify-center">01 / The product</div>
          <h2 className="t-h2 mt-3">The whole picture, on one screen</h2>
          <p className="t-lead mx-auto mt-3 max-w-xl">
            Scroll to open ThinkFree. Everything in one place, in plain English.
          </p>
        </div>

        {/* laptop centered in the full viewport */}
        <div className="flex h-full items-center justify-center px-4" style={{ perspective: "1500px" }}>
          <motion.div
            style={reduce ? undefined : { scale, rotateX: 8, transformStyle: "preserve-3d", willChange: "transform" }}
            className="relative"
          >
            {/* screen / lid: silver aluminum frame around a dark bezel + dashboard */}
            <motion.div
              style={lidStyle}
              className="relative h-[min(54vw,480px)] w-[min(92vw,860px)] rounded-t-[18px] bg-gradient-to-b from-[#E7ECF2] to-[#C3CCD8] p-[8px] shadow-[0_40px_90px_rgba(0,0,0,0.55)]"
            >
              <div className="absolute left-1/2 top-[3px] h-[4px] w-[4px] -translate-x-1/2 rounded-full bg-[#6b7480]" />
              <div className="relative h-full w-full overflow-hidden rounded-[11px] border border-black/60 bg-ink-900">
                <AppDashboard />
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-transparent via-transparent to-white/[0.06]" />
                <motion.div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0"
                  style={{
                    opacity: reduce ? 0.25 : glow,
                    background: "radial-gradient(60% 50% at 50% 40%, rgba(56,189,248,0.10), transparent 70%)",
                  }}
                />
              </div>
            </motion.div>

            {/* body / deck: prominent silver slab with a hinge notch */}
            <div className="relative mx-auto h-[22px] w-[min(96vw,900px)] rounded-b-[16px] rounded-t-[4px] bg-gradient-to-b from-[#CBD3DE] to-[#9BA6B4] shadow-[0_18px_40px_rgba(0,0,0,0.5)]">
              <div className="absolute left-1/2 top-0 h-[7px] w-[110px] -translate-x-1/2 rounded-b-[8px] bg-[#8b95a3]" />
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
