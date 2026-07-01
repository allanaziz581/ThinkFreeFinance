import { useRef } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";

/**
 * Container-scroll reveal (Aceternity pattern): as the section scrolls through
 * the viewport, a perspective card rotates from tilted-back to flat and scales
 * up, while a heading above it settles. Reduced-motion renders it flat/static.
 */
export default function ContainerScroll({ title, kicker, children }) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });

  const rotate = useTransform(scrollYProgress, [0, 0.4], [22, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.4], [0.9, 1]);
  const translate = useTransform(scrollYProgress, [0, 0.4], [40, 0]);
  const headOpacity = useTransform(scrollYProgress, [0, 0.25], [0.4, 1]);

  return (
    <section ref={ref} className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell" style={{ perspective: "1000px" }}>
        <motion.div
          style={reduce ? undefined : { opacity: headOpacity }}
          className="mx-auto max-w-2xl text-center"
        >
          {kicker ? <div className="t-label">{kicker}</div> : null}
          <h2 className="t-h2 mt-3">{title}</h2>
        </motion.div>

        <motion.div
          style={
            reduce
              ? undefined
              : { rotateX: rotate, scale, y: translate, transformStyle: "preserve-3d" }
          }
          className="mx-auto mt-10 max-w-4xl rounded-panel border border-line-strong bg-ink-800 p-2 sm:p-3"
        >
          <div className="overflow-hidden rounded-[10px] border border-line bg-ink-900">
            {children}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
