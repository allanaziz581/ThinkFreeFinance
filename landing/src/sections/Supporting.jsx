import Reveal from "../components/ui/Reveal.jsx";
import SectionHead from "../components/ui/SectionHead.jsx";
import { Landmark, Receipt, Newspaper } from "lucide-react";

const CARDS = [
  {
    icon: Landmark,
    title: "Congressional-trade tracking",
    body: "Every disclosed trade by members of Congress, with volume, win rate, and timing against related legislation.",
  },
  {
    icon: Receipt,
    title: "Cost-of-living tracker",
    body: "Groceries, rent, gas, mortgages, jobs, and more, measured against a fixed baseline so you see what really changed.",
  },
  {
    icon: Newspaper,
    title: "News in plain English",
    body: "Financial news translated into what it means for rent, groceries, jobs, and your money, not Wall Street jargon.",
  },
];

export default function Supporting() {
  return (
    <section className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <SectionHead label="Also inside" title="Everything in one place, in plain English" />

        <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {CARDS.map((c, i) => {
            const Icon = c.icon;
            return (
              <Reveal key={c.title} delay={i * 0.05}>
                <div className="lp-card h-full p-6">
                  <div className="mb-4 grid h-10 w-10 place-items-center rounded-ctl border border-line bg-ink-700 text-brand">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="t-h3">{c.title}</h3>
                  <p className="t-body mt-2">{c.body}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
