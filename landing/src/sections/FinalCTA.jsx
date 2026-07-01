import Reveal from "../components/ui/Reveal.jsx";
import GeminiLines from "../components/GeminiLines.jsx";
import Beams from "../components/Beams.jsx";
import { ArrowRight } from "lucide-react";

export default function FinalCTA({ onSignIn }) {
  return (
    <section className="relative overflow-hidden border-b border-line py-18 sm:py-22">
      {/* ethereal beams aesthetic behind the closing section */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 opacity-70">
        <Beams />
      </div>

      {/* Full-bleed money-trail lines: edge to edge across the page. */}
      <div className="relative w-full overflow-hidden">
        <GeminiLines />
      </div>

      <div className="lp-shell relative">
        <Reveal>
          <div className="mt-4 rounded-panel border border-line bg-ink-800/80 px-6 py-16 text-center backdrop-blur-sm sm:px-10">
            <h2 className="t-h2">See the connections. See the math.</h2>
            <p className="t-lead mx-auto mt-4 max-w-lg">
              Open ThinkFree and explore the influence map, the Quant analysis, and the trackers for
              yourself, all in one place, in plain English.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <a className="lp-btn lp-btn-primary lp-btn-lg" href="/app">
                Open the app <ArrowRight className="h-4 w-4" />
              </a>
              <button className="lp-btn lp-btn-ghost lp-btn-lg" onClick={onSignIn} type="button">
                Sign in
              </button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
