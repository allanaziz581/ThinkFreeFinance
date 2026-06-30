import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// The landing is its own standalone app, compiled to the FastAPI-served
// webapp/landing-dist/ directory. base "/landing/" namespaces every hashed
// asset under /landing/* so it can never collide with the vanilla app's
// /css and /js mounts, and so the landing CSP can be scoped to exactly
// "/" and "/landing/*" without touching app routes.
export default defineConfig({
  base: "/landing/",
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../webapp/landing-dist", import.meta.url)),
    emptyOutDir: true,
    // No inline scripts in the emitted HTML: keeps the landing CSP at a
    // strict script-src 'self' (no 'unsafe-inline', no hashes to maintain).
    modulePreload: { polyfill: false },
    assetsInlineLimit: 0,
  },
});
