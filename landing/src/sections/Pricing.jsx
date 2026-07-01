import Reveal from "../components/ui/Reveal.jsx";
import SectionHead from "../components/ui/SectionHead.jsx";
import { Check } from "lucide-react";

// Mirrors the app's public tier catalogue (server/config.py public_tiers). Kept
// as static metadata so the landing stays fully isolated from the app; it is not
// secret and is safe to show unauthenticated.
const TIERS = [
  {
    name: "Free",
    price: "$0",
    cadence: "Daily briefing",
    features: ["Daily market briefing", "Live prices", "Plain-English news"],
    highlight: false,
  },
  {
    name: "Pro · Hourly",
    price: "$5",
    cadence: "per month",
    features: ["Fresh prices every hour", "Live prices", "Plain-English news"],
    highlight: false,
  },
  {
    name: "Pro · 30-min",
    price: "$15",
    cadence: "per month",
    features: ["Refreshes every 30 minutes", "Includes after hours", "Full Quant + Money Trail"],
    highlight: true,
  },
  {
    name: "Pro · 5-min",
    price: "$25",
    cadence: "per month",
    features: ["Fastest feed, every 5 minutes", "Includes after hours", "Everything in Pro"],
    highlight: false,
  },
];

export default function Pricing() {
  return (
    <section id="pricing" className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <SectionHead
          label="Plans"
          title="Start free. Move faster when you need to."
          lead="Every plan reads the same public records and shows the same transparent math. Higher tiers just refresh the live data more often."
          center
        />

        <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TIERS.map((t, i) => (
            <Reveal key={t.name} delay={i * 0.05}>
              <div
                className={`relative flex h-full flex-col rounded-panel border bg-ink-800 p-6 transition-colors duration-200 ${
                  t.highlight ? "border-brand" : "border-line hover:border-line-strong"
                }`}
              >
                {t.highlight ? (
                  <span className="absolute right-4 top-4 rounded-ctl border border-brand/40 bg-brand-glow px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-brand">
                    Popular
                  </span>
                ) : null}
                <div className="text-[13px] font-semibold text-ash-300">{t.name}</div>
                <div className="mt-3 flex items-baseline gap-1.5">
                  <span className="num text-[32px] font-bold leading-none text-ash-100">{t.price}</span>
                  <span className="t-small">{t.cadence}</span>
                </div>
                <ul className="mt-5 flex flex-1 flex-col gap-2.5">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-[13px] text-ash-300">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" />
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href="/app"
                  className={`lp-btn mt-6 w-full ${t.highlight ? "lp-btn-primary" : "lp-btn-ghost"}`}
                >
                  Get started
                </a>
              </div>
            </Reveal>
          ))}
        </div>

        <p className="t-small mt-6 text-center">
          Prices shown for reference. Nothing here is investment advice or a guarantee of results.
        </p>
      </div>
    </section>
  );
}
