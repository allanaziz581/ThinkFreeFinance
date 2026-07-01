import Reveal from "../components/ui/Reveal.jsx";
import SectionHead from "../components/ui/SectionHead.jsx";
import { Landmark, Newspaper, Receipt } from "lucide-react";

const SMALL = [
  {
    icon: Landmark,
    title: "Congressional-trade tracking",
    body: "Every disclosed trade by members of Congress, with volume, win rate, and timing against related legislation.",
  },
  {
    icon: Newspaper,
    title: "News in plain English",
    body: "Financial news translated into what it means for rent, groceries, jobs, and your money, not Wall Street jargon.",
  },
];

// Plain-English chips that make the cost-of-living tracker concrete for a normal person.
const COL_ITEMS = ["Groceries", "Rent", "Gas", "Mortgage rates", "Car loans", "Jobs", "Utilities"];

export default function Supporting() {
  return (
    <section className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        <SectionHead
          label="04 / In plain English"
          title="Everything in one place, in plain English"
          lead="No finance degree required. ThinkFree pulls it together and explains what it means for you."
        />

        <div className="mt-10 grid grid-cols-1 gap-3 lg:grid-cols-3">
          {/* expanded cost-of-living feature (item 6) */}
          <Reveal className="lg:col-span-2">
            <div className="lp-card h-full p-6 sm:p-7">
              <div className="mb-4 flex items-center gap-3">
                <span className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-ctl border border-line bg-ink-700 text-brand">
                  <Receipt className="h-5 w-5" />
                </span>
                <h3 className="t-h3 text-[18px]">Cost-of-living tracker</h3>
              </div>
              <p className="t-body">
                This is the part that hits home. ThinkFree tracks the prices you actually pay,
                groceries, rent, gas, mortgages, car loans, and jobs, against a fixed starting point,
                so you can see in plain numbers what is getting more expensive and what is easing.
                When the Fed changes rates or a new law passes, it shows what that likely means for
                your monthly budget, in words anyone can follow, not charts only Wall Street reads.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {COL_ITEMS.map((c) => (
                  <span key={c} className="lp-chip">
                    {c}
                  </span>
                ))}
              </div>
            </div>
          </Reveal>

          {/* stacked small cards */}
          <div className="grid grid-cols-1 gap-3">
            {SMALL.map((c, i) => {
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
      </div>
    </section>
  );
}
