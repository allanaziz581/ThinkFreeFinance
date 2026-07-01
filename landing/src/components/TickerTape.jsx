/**
 * A restrained Bloomberg-style ticker tape under the nav: index and ticker quotes
 * in tabular mono, up/down colored, scrolling slowly. Illustrative figures. The
 * marquee is CSS-driven and pauses under prefers-reduced-motion (shows a static
 * row). aria-hidden: decorative, not content.
 */
const QUOTES = [
  { s: "S&P 500", v: "5,431.60", c: "+0.42%", up: true },
  { s: "NASDAQ", v: "17,862.30", c: "+0.61%", up: true },
  { s: "DOW", v: "39,110.80", c: "-0.14%", up: false },
  { s: "VIX", v: "12.94", c: "-2.10%", up: false },
  { s: "10Y", v: "4.21%", c: "+0.03", up: true },
  { s: "NVDA", v: "126.40", c: "+1.84%", up: true },
  { s: "LMT", v: "462.10", c: "+0.31%", up: true },
  { s: "XOM", v: "112.75", c: "-0.52%", up: false },
  { s: "JPM", v: "204.60", c: "+0.44%", up: true },
  { s: "AAPL", v: "213.30", c: "+0.27%", up: true },
];

function Row() {
  return (
    <div className="flex shrink-0 items-center">
      {QUOTES.map((q, i) => (
        <span key={i} className="num inline-flex items-center gap-2 whitespace-nowrap px-4 text-[11.5px]">
          <span className="font-medium text-ash-300">{q.s}</span>
          <span className="text-ash-100">{q.v}</span>
          <span className={q.up ? "text-up" : "text-down"}>{q.c}</span>
          <span className="text-line" aria-hidden="true">|</span>
        </span>
      ))}
    </div>
  );
}

export default function TickerTape() {
  return (
    <div
      aria-hidden="true"
      className="relative overflow-hidden border-b border-line bg-ink-900/80"
      style={{ height: "30px" }}
    >
      <div className="tt-track flex items-center" style={{ height: "30px" }}>
        <Row />
        <Row />
      </div>
      {/* edge fades */}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-16"
           style={{ background: "linear-gradient(90deg, #070A0F, transparent)" }} />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-16"
           style={{ background: "linear-gradient(270deg, #070A0F, transparent)" }} />
    </div>
  );
}
