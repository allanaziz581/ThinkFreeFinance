import Reveal from "../components/ui/Reveal.jsx";
import SectionHead from "../components/ui/SectionHead.jsx";

const ICONS = {
  capitol: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 21h18" />
      <path d="M4 10h16" />
      <path d="M5 10v8M19 10v8M9 10v8M15 10v8" />
      <path d="M12 3 4 7h16Z" />
    </svg>
  ),
  chart: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 3 3 5-6" />
    </svg>
  ),
  news: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="7" y1="8" x2="13" y2="8" />
      <line x1="7" y1="12" x2="17" y2="12" />
      <line x1="7" y1="16" x2="17" y2="16" />
    </svg>
  ),
};

const CARDS = [
  {
    icon: "capitol",
    title: "Congressional-trade tracking",
    body: "Every disclosed trade by members of Congress, with volume, win rate, and timing against related legislation.",
  },
  {
    icon: "chart",
    title: "Cost-of-living tracker",
    body: "Groceries, rent, gas, mortgages, jobs, and more, measured against a fixed baseline so you see what really changed.",
  },
  {
    icon: "news",
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
          {CARDS.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.05}>
              <div className="lp-card h-full p-6">
                <div className="mb-4 grid h-10 w-10 place-items-center rounded-ctl border border-line bg-ink-700 text-brand [&>svg]:h-[20px] [&>svg]:w-[20px]">
                  {ICONS[c.icon]}
                </div>
                <h3 className="t-h3">{c.title}</h3>
                <p className="t-body mt-2">{c.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
