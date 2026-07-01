import Reveal from "../components/ui/Reveal.jsx";
import GeminiLines from "../components/GeminiLines.jsx";
import { ArrowRight } from "lucide-react";

export default function FinalCTA({ onSignIn }) {
  return (
    <section className="border-b border-line py-18 sm:py-22">
      <div className="lp-shell">
        {/* the single Gemini-effect accent: money-trail lines drawing on scroll */}
        <GeminiLines />
        <Reveal>
          <div className="mt-4 rounded-panel border border-line bg-ink-800 px-6 py-16 text-center sm:px-10">
            <h2 className="t-h2">See the connections. See the math.</h2>
            <p className="t-lead mx-auto mt-4 max-w-lg">
              Open ThinkFree and explore the influence map, the quant analysis, and the trackers for
              yourself.
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
