export default function Footer() {
  return (
    <footer className="py-12 text-ash-500">
      <div className="lp-shell">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <a href="/" className="flex items-center gap-2.5" aria-label="ThinkFree home">
            <span className="grid h-7 w-7 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">
              TF
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-ash-100">
              Think<span className="text-brand">Free</span>
            </span>
          </a>
          <a className="lp-btn lp-btn-ghost" href="/app">
            Open the app
          </a>
        </div>
        <p className="t-small max-w-3xl">
          ThinkFree is an informational research tool and economic translator. It is not a
          brokerage, robo-advisor, or financial advisor, and nothing here is investment advice or a
          guarantee of future results. Political intelligence describes timing relationships between
          publicly available government disclosures and market events. It does not imply or allege
          wrongdoing of any kind. Data is compiled from public records.
        </p>
      </div>
    </footer>
  );
}
