#!/usr/bin/env bash
# Compile the public landing (React + Vite) into webapp/landing-dist/ during the
# Render deploy.
#
# Best-effort by design: the compiled bundle is ALSO committed to the repo, so if
# Node/npm is unavailable on the build host (or the build hiccups) we keep the
# committed bundle and continue instead of failing the entire web-service deploy.
# This script therefore always exits 0.
set -u

# Resolve the repo root from this script's location, regardless of caller cwd.
cd "$(dirname "$0")/.." || exit 0

if ! command -v npm >/dev/null 2>&1; then
  echo "[build_landing] npm not found; serving committed webapp/landing-dist bundle"
  exit 0
fi

cd landing || { echo "[build_landing] landing/ missing; skipping"; exit 0; }

echo "[build_landing] installing landing dependencies"
npm ci || npm install || { echo "[build_landing] install failed; serving committed bundle"; exit 0; }

echo "[build_landing] building landing bundle"
npm run build || { echo "[build_landing] build failed; serving committed bundle"; exit 0; }

echo "[build_landing] landing build complete"
exit 0
