import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Loader2, ArrowRight } from "lucide-react";

/**
 * Animated sign-in (21st.dev sign-in-flow pattern) that authenticates against
 * the REAL backend: it POSTs to the same-origin /api/auth/login, which sets the
 * httpOnly session cookie, then hands off to /app. It is not a fake form and it
 * stores nothing. Anything beyond the happy path (MFA, signup, reset) is
 * completed on /app, which owns the full auth flow. The landing never imports
 * app auth code; it only calls the public login API.
 */
export default function SignIn({ open, onClose }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        // MFA or any further step is completed in the full app flow.
        window.location.assign("/app");
        return;
      }
      if (res.status === 401) {
        setError("Incorrect email or password.");
      } else if (res.status === 429) {
        setError("Too many attempts. Please wait a moment and try again.");
      } else {
        setError("Could not sign in right now. Please try again.");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div className="absolute inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Sign in to ThinkFree"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-sm overflow-hidden rounded-panel border border-line-strong bg-ink-800"
          >
            <div className="bg-grid-faint pointer-events-none absolute inset-0 opacity-60" />
            <div className="relative p-7">
              <button
                onClick={onClose}
                aria-label="Close"
                className="absolute right-4 top-4 grid h-8 w-8 cursor-pointer place-items-center rounded-ctl border border-line text-ash-500 transition-colors hover:border-line-strong hover:text-ash-100"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="flex items-center gap-2.5">
                <span className="grid h-7 w-7 place-items-center rounded-ctl bg-brand text-[12px] font-bold text-ink-900">
                  TF
                </span>
                <span className="text-[15px] font-semibold tracking-tight">
                  Think<span className="text-brand">Free</span>
                </span>
              </div>

              <h2 className="t-h3 mt-5 text-[19px]">Welcome back</h2>
              <p className="t-small mt-1">Sign in to open your intelligence dashboard.</p>

              <form onSubmit={submit} className="mt-5 flex flex-col gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-[12px] font-medium text-ash-300">Email</span>
                  <input
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="rounded-ctl border border-line bg-ink-900 px-3 py-2.5 text-[14px] text-ash-100 outline-none transition-colors focus:border-brand"
                    placeholder="you@example.com"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-[12px] font-medium text-ash-300">Password</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-ctl border border-line bg-ink-900 px-3 py-2.5 text-[14px] text-ash-100 outline-none transition-colors focus:border-brand"
                    placeholder="Your password"
                  />
                </label>

                {error ? (
                  <p className="text-[12.5px] text-[#EF4444]" role="alert">
                    {error}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={busy}
                  className="lp-btn lp-btn-primary mt-1 w-full disabled:opacity-70"
                >
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      Sign in <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>

              <p className="t-small mt-4 text-center">
                New here?{" "}
                <a href="/app" className="text-brand hover:underline">
                  Create an account
                </a>
              </p>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
