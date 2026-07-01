import { LayoutGrid, Newspaper, Landmark, Wallet, LineChart, Brain, History, Settings } from "lucide-react";

/**
 * A faithful miniature of the REAL ThinkFree dashboard (mirrors app.js
 * renderDashboard): left sidebar router, a four-up KPI row (Market Mood,
 * Recession Risk, Market Direction, Top Story), Political Watch with a ranked
 * list, a Bill-Trade correlation readout, and a Sector Scorecard with bars.
 * Shown on the laptop screen in the scroll reveal. Static, illustrative figures.
 */

const NAV = [
  { icon: LayoutGrid, label: "Dashboard", active: true },
  { icon: Newspaper, label: "News" },
  { icon: Landmark, label: "Political Watch" },
  { icon: Wallet, label: "My Portfolio" },
  { icon: LineChart, label: "Markets" },
  { icon: Brain, label: "Reasoning" },
  { icon: History, label: "History" },
  { icon: Settings, label: "Settings" },
];

const KPIS = [
  { label: "Market Mood", pill: "Bullish", pillTone: "up", value: "72%", foot: "Risk-on sentiment across sectors" },
  { label: "Recession Risk", pill: "Low", pillTone: "up", value: "23%", foot: "Yield curve normalizing" },
  { label: "Market Direction", pill: "Up", pillTone: "up", value: "Slightly Up", foot: "Broad indices trending higher" },
  { label: "Top Story", pill: "Fed", pillTone: "info", value: "Fed holds rates", foot: "Guidance stays neutral" },
];

const RANK = [
  { rk: 1, nm: "Rep. A. Morgan", st: "CA", tag: "D", val: "+$412K" },
  { rk: 2, nm: "Sen. J. Blake", st: "TX", tag: "R", val: "+$318K" },
  { rk: 3, nm: "Rep. L. Ortiz", st: "FL", tag: "R", val: "+$204K" },
  { rk: 4, nm: "Sen. P. Reed", st: "NY", tag: "D", val: "+$155K" },
];

const SECTORS = [
  { s: "Technology", v: 8.4 },
  { s: "Defense", v: 7.1 },
  { s: "Energy", v: 6.3 },
  { s: "Healthcare", v: 5.8 },
  { s: "Financials", v: 4.9 },
];

const pillClass = (tone) =>
  tone === "up"
    ? "bg-[rgba(0,196,106,0.14)] text-[#00C46A]"
    : tone === "down"
    ? "bg-[rgba(239,68,68,0.14)] text-[#EF4444]"
    : "bg-brand-glow text-brand";

export default function AppDashboard() {
  return (
    <div className="flex h-full w-full bg-ink-900 text-ash-100">
      {/* sidebar */}
      <aside className="hidden w-[150px] flex-shrink-0 flex-col border-r border-line bg-ink-800 p-3 sm:flex">
        <div className="mb-4 flex items-center gap-2 px-1">
          <span className="grid h-6 w-6 place-items-center rounded-ctl bg-brand text-[10px] font-bold text-ink-900">
            TF
          </span>
          <span className="text-[12.5px] font-semibold">
            Think<span className="text-brand">Free</span>
          </span>
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((n) => {
            const Icon = n.icon;
            return (
              <div
                key={n.label}
                className={`flex items-center gap-2 rounded-ctl px-2 py-1.5 text-[11px] ${
                  n.active ? "bg-brand-glow text-ash-100" : "text-ash-500"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {n.label}
              </div>
            );
          })}
        </nav>
      </aside>

      {/* main */}
      <div className="min-w-0 flex-1 overflow-hidden p-3">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-[13px] font-semibold">Dashboard</div>
            <div className="text-[10px] text-ash-500">Everything in one place, in plain English</div>
          </div>
          <div className="hidden gap-1.5 sm:flex">
            <span className="rounded-ctl border border-line px-2 py-0.5 text-[10px] text-ash-300">Live</span>
          </div>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {KPIS.map((k) => (
            <div key={k.label} className="rounded-ctl border border-line bg-ink-800 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[9.5px] uppercase tracking-wider text-ash-500">{k.label}</span>
                <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold ${pillClass(k.pillTone)}`}>
                  {k.pill}
                </span>
              </div>
              <div className="num mt-1.5 text-[16px] font-bold leading-tight">{k.value}</div>
              <div className="mt-1 text-[9px] leading-snug text-ash-500">{k.foot}</div>
            </div>
          ))}
        </div>

        {/* political + sector */}
        <div className="mt-2 grid grid-cols-1 gap-2 lg:grid-cols-[1.4fr_1fr]">
          <div className="rounded-ctl border border-line bg-ink-800 p-2.5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ash-300">
                Political Watch
              </span>
              <span className="text-[9.5px] text-brand">Full report</span>
            </div>
            <ul className="flex flex-col gap-1.5">
              {RANK.map((r) => (
                <li key={r.rk} className="flex items-center gap-2 text-[11px]">
                  <span className="num w-4 text-ash-500">{r.rk}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {r.nm} <span className="text-ash-500">· {r.st}</span>
                  </span>
                  <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[9px] text-ash-300">{r.tag}</span>
                  <span className="num text-[#00C46A]">{r.val}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-ctl border border-line bg-ink-800 p-2.5">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ash-300">
              Sector Scorecard
            </div>
            <div className="flex flex-col gap-1.5">
              {SECTORS.map((s) => (
                <div key={s.s} className="flex items-center gap-2">
                  <span className="w-[64px] flex-shrink-0 text-[10px] text-ash-300">{s.s}</span>
                  <span className="num w-6 text-[10px] text-ash-500">{s.v}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${(s.v / 10) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
