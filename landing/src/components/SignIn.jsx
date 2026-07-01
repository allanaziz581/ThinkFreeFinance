import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Loader2, ArrowRight, Check } from "lucide-react";

/**
 * Onboard-card sign-in (the 3-step onboarding pattern) wired to REAL auth:
 * step 1 Welcome (credentials) -> step 2 Verifying (POST /api/auth/login) ->
 * step 3 Signed in (redirect to /app). The httpOnly session cookie is set by the
 * backend; this stores nothing and imports no app auth code. Anything beyond the
 * happy path (MFA, signup) is completed on /app.
 */
const STEPS = ["Welcome", "Verifying", "Signed in"];

export default function SignIn({ open, onClose }) {
  const [step, setStep] = useState(0);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function reset() { setStep(0); setError(""); setPassword(""); }
  function close() { reset(); onClose(); }

  async function submit(e) {
    e.preventDefault();
    if (step === 1) return;
    setError("");
    setStep(1);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (res.ok) {
        setStep(2);
        window.setTimeout(() => window.location.assign("/app"), 900);
        return;
      }
      setStep(0);
      if (res.status === 401) setError("Incorrect email or password.");
      else if (res.status === 429) setError("Too many attempts. Please wait and try again.");
      else setError("Could not sign in right now. Please try again.");
    } catch {
      setStep(0);
      setError("Network error. Please try again.");
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
        >
          <div className="absolute inset-0 bg-black/70" onClick={close} aria-hidden="true" />
          <motion.div
            role="dialog" aria-modal="true" aria-label="Sign in to ThinkFree"
            initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }} transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-sm overflow-hidden rounded-panel border border-line-strong bg-ink-800"
          >
            <div className="bg-grid-faint pointer-events-none absolute inset-0 opacity-60" />
            <div className="relative p-7">
              <button onClick={close} aria-label="Close"
                className="absolute right-4 top-4 grid h-8 w-8 cursor-pointer place-items-center rounded-ctl border border-line text-ash-500 transition-colors hover:border-line-strong hover:text-ash-100">
                <X className="h-4 w-4" />
              </button>

              {/* brand + step progress */}
              <div className="flex items-center gap-2.5">
                <span className="grid h-7 w-7 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">TF</span>
                <span className="text-[15px] font-semibold tracking-tight">Think<span className="text-brand">Free</span></span>
              </div>
              <div className="mt-5 flex items-center gap-2">
                {STEPS.map((s, i) => (
                  <div key={s} className="flex flex-1 flex-col gap-1.5">
                    <div className={`h-1 rounded-full transition-colors duration-300 ${i <= step ? "bg-brand" : "bg-white/[0.08]"}`} />
                    <span className={`text-[10px] ${i === step ? "text-ash-100" : "text-ash-500"}`}>{s}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 min-h-[220px]">
                <AnimatePresence mode="wait">
                  {step === 0 ? (
                    <motion.form key="form" onSubmit={submit}
                      initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.22 }}
                      className="flex flex-col gap-3">
                      <h2 className="t-h3 text-[19px]">Welcome back</h2>
                      <p className="t-small -mt-1">Sign in to open your intelligence dashboard.</p>
                      <label className="mt-1 flex flex-col gap-1.5">
                        <span className="text-[12px] font-medium text-ash-300">Email</span>
                        <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                          className="rounded-ctl border border-line bg-ink-900 px-3 py-2.5 text-[14px] text-ash-100 outline-none transition-colors focus:border-brand" placeholder="you@example.com" />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className="text-[12px] font-medium text-ash-300">Password</span>
                        <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)}
                          className="rounded-ctl border border-line bg-ink-900 px-3 py-2.5 text-[14px] text-ash-100 outline-none transition-colors focus:border-brand" placeholder="Your password" />
                      </label>
                      {error ? <p className="text-[12.5px] text-[#EF4444]" role="alert">{error}</p> : null}
                      <button type="submit" className="lp-btn lp-btn-primary mt-1 w-full">
                        Continue <ArrowRight className="h-4 w-4" />
                      </button>
                    </motion.form>
                  ) : step === 1 ? (
                    <motion.div key="verify" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      className="flex min-h-[220px] flex-col items-center justify-center gap-3 text-center">
                      <Loader2 className="h-8 w-8 animate-spin text-brand" />
                      <div className="t-h3 text-[17px]">Verifying details</div>
                      <p className="t-small">Checking your credentials securely.</p>
                    </motion.div>
                  ) : (
                    <motion.div key="done" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
                      className="flex min-h-[220px] flex-col items-center justify-center gap-3 text-center">
                      <span className="grid h-12 w-12 place-items-center rounded-full border border-brand/40 bg-brand-glow text-brand">
                        <Check className="h-6 w-6" />
                      </span>
                      <div className="t-h3 text-[17px]">Signed in</div>
                      <p className="t-small">Opening your dashboard.</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {step === 0 ? (
                <p className="t-small mt-2 text-center">
                  New here? <a href="/app" className="text-brand hover:underline">Create an account</a>
                </p>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
