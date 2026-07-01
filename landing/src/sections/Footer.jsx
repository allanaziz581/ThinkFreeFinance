import { motion, useReducedMotion } from "framer-motion";

const LINKS = [
  { label: "Influence Map", href: "#influence" },
  { label: "Quant", href: "#quant" },
  { label: "Plans", href: "#pricing" },
  { label: "Open the app", href: "/app" },
];

export default function Footer() {
  const reduce = useReducedMotion();
  return (
    <motion.footer
      className="py-12 text-ash-500"
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="lp-shell">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <a href="/" className="flex items-center gap-2.5" aria-label="ThinkFree home">
            <span className="grid h-7 w-7 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">
              TF
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-ash-100">
              Think<span className="text-brand">Free</span>
            </span>
          </a>
          <nav className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {LINKS.map((l) => (
              <a key={l.label} href={l.href} className="text-[13px] text-ash-300 transition-colors hover:text-ash-100">
                {l.label}
              </a>
            ))}
          </nav>
        </div>
        <p className="t-small max-w-3xl">
          ThinkFree is an informational research tool and economic translator. It is not a
          brokerage, robo-advisor, or financial advisor, and nothing here is investment advice or a
          guarantee of future results. Political intelligence describes timing relationships between
          publicly available government disclosures and market events. It does not imply or allege
          wrongdoing of any kind. Data is compiled from public records.
        </p>
      </div>
    </motion.footer>
  );
}
