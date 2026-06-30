import { motion, useReducedMotion } from "framer-motion";

/**
 * Apple-style scroll reveal: content rises and fades in once as it enters the
 * viewport. Honors prefers-reduced-motion by rendering static. The `as` prop
 * lets a caller reveal any element (section, div, li) without extra wrappers.
 */
export default function Reveal({
  children,
  as = "div",
  delay = 0,
  y = 22,
  className = "",
  once = true,
}) {
  const reduce = useReducedMotion();
  const MotionTag = motion[as] || motion.div;

  if (reduce) {
    const Tag = as;
    return <Tag className={className}>{children}</Tag>;
  }

  return (
    <MotionTag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, margin: "-12% 0px -10% 0px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </MotionTag>
  );
}
