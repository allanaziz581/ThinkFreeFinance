import { TrendingUp, TrendingDown, Landmark, Activity } from "lucide-react";

/**
 * A distinct visual (NOT the influence map): a restrained mock of the app's
 * intelligence dashboard, shown inside the container-scroll card. Static,
 * illustrative figures; framed as analysis, not advice.
 */

const STATS = [
  { label: "Recession risk", value: "3.4", unit: "/10", tone: "pos", delta: "-0.6" },
  { label: "Signals ranked", value: "128", unit: "", tone: "neutral", delta: "+12" },
  { label: "Disclosures traced", value: "5,207", unit: "", tone: "neutral", delta: "+43" },
];

const ROWS = [
  { who: "Defense appropriations", tag: "Contract", val: "+2.1%", up: true },
  { who: "Semiconductor subsidy", tag: "Lobbying", val: "+4.7%", up: true },
  { who: "Energy leasing bill", tag: "Trade", val: "-1.3%", up: false },
  { who: "Healthcare pricing rule", tag: "Contract", val: "+0.8%", up: true },
];

// simple deterministic sparkline path
const SPARK = "M0,26 L14,20 L28,23 L42,12 L56,16 L70,7 L84,10 L98,3";

export default function DashboardMock() {
  return (
    <div className="grid grid-cols-1 gap-3 p-4 sm:p-5 md:grid-cols-3">
      {/* left: stat tiles + sparkline */}
      <div className="flex flex-col gap-3 md:col-span-2">
        <div className="grid grid-cols-3 gap-3">
          {STATS.map((s) => (
            <div key={s.label} className="rounded-ctl border border-line bg-ink-800 p-3">
              <div className="text-[11px] text-ash-500">{s.label}</div>
              <div className="mt-1.5 flex items-baseline gap-1">
                <span className="num text-[20px] font-bold text-ash-100">{s.value}</span>
                <span className="num text-[12px] text-ash-500">{s.unit}</span>
              </div>
              <div
                className={`num mt-1 text-[11px] ${
                  s.tone === "pos" ? "text-[#00C46A]" : "text-ash-500"
                }`}
              >
                {s.delta}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-ctl border border-line bg-ink-800 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[12px] text-ash-300">
              <Activity className="h-4 w-4 text-brand" />
              Opportunity score trend
            </div>
            <span className="num text-[12px] text-[#00C46A]">+18.2%</span>
          </div>
          <svg viewBox="0 0 98 30" className="mt-3 h-16 w-full" preserveAspectRatio="none">
            <path d={SPARK} fill="none" stroke="#38BDF8" strokeWidth="1.5" strokeLinecap="round" />
            <path d={`${SPARK} L98,30 L0,30 Z`} fill="rgba(56,189,248,0.08)" stroke="none" />
          </svg>
        </div>
      </div>

      {/* right: money-trail feed */}
      <div className="rounded-ctl border border-line bg-ink-800 p-4">
        <div className="mb-3 flex items-center gap-2 text-[12px] text-ash-300">
          <Landmark className="h-4 w-4 text-brand" />
          Money Trail
        </div>
        <ul className="flex flex-col gap-2.5">
          {ROWS.map((r) => (
            <li key={r.who} className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-[12.5px] text-ash-100">{r.who}</div>
                <div className="text-[10.5px] uppercase tracking-wider text-ash-500">{r.tag}</div>
              </div>
              <span
                className={`num flex items-center gap-1 text-[12px] ${
                  r.up ? "text-[#00C46A]" : "text-[#EF4444]"
                }`}
              >
                {r.up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {r.val}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
