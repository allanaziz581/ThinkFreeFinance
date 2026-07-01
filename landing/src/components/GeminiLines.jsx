import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";

/**
 * Gemini-effect (Aceternity pattern): several long curved SVG paths that "draw"
 * as the section scrolls into view, evoking the money-trail flowing from a law
 * out to markets. Restrained single-accent cyan, low opacity, no glow.
 */
const PATHS = [
  "M0,120 C 260,120 360,40 640,40 C 900,40 980,120 1200,120",
  "M0,140 C 260,140 360,90 640,90 C 900,90 980,140 1200,140",
  "M0,160 C 260,160 360,150 640,150 C 900,150 980,160 1200,160",
  "M0,180 C 260,180 360,210 640,210 C 900,210 980,180 1200,180",
  "M0,200 C 260,200 360,260 640,260 C 900,260 980,200 1200,200",
];

function Path({ d, progress, reduce, delay }) {
  const pathLength = useTransform(progress, [0.1 + delay, 0.75 + delay], [0, 1]);
  return (
    <motion.path
      d={d}
      stroke="#38BDF8"
      strokeWidth="1.2"
      fill="none"
      strokeLinecap="round"
      style={reduce ? { pathLength: 1, opacity: 0.35 } : { pathLength, opacity: 0.5 }}
    />
  );
}

export default function GeminiLines() {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end center"] });

  return (
    <div ref={ref} className="relative h-[220px] w-full overflow-hidden" aria-hidden="true">
      <svg
        viewBox="0 0 1200 320"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
      >
        {PATHS.map((d, i) => (
          <Path key={i} d={d} progress={scrollYProgress} reduce={reduce} delay={i * 0.03} />
        ))}
      </svg>
    </div>
  );
}
