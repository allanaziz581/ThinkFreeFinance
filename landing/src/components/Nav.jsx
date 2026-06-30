/**
 * Grounded, conventional top bar: full-bleed, flush to the top edge, solid
 * surface with a single hairline bottom border. No floating capsule, no glow,
 * no backdrop blur. Log in / Get started route to /app (the app shell owns the
 * login gate). Sticky so it stays available without drawing attention.
 */
export default function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-ink-900">
      <div className="lp-shell flex h-14 items-center justify-between">
        <a href="/" className="flex min-w-0 items-center gap-2.5" aria-label="ThinkFree home">
          <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">
            TF
          </span>
          <span className="whitespace-nowrap text-[15px] font-semibold tracking-tight">
            Think<span className="text-brand">Free</span>
          </span>
        </a>
        <nav className="flex flex-shrink-0 items-center gap-2.5">
          <a className="lp-btn lp-btn-ghost" href="/app">
            Log in
          </a>
          <a className="lp-btn lp-btn-primary" href="/app">
            Get started
          </a>
        </nav>
      </div>
    </header>
  );
}
