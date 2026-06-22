# ThinkFree Webapp — Deploy & Performance Architecture

## How it's built for speed

The webapp is a **fully static site** — plain `index.html`, CSS, and JS. At
runtime it makes **zero API calls**: every API/dataset is fetched **offline** by
the Python build scripts, which pre-generate static `window.*_DATA` JS files.

So a visitor never waits on an API. The only load cost is downloading the static
data files, which a CDN serves instantly. This is the fast-retrieval design:
**all the slow work (scraping, APIs, quant, GPT) happens at build time, not at
request time.**

```
Build time (offline)                Request time (visitor)
────────────────────                ──────────────────────
USASpending, Senate LDA, FEC,       static index.html + js/*.js
Finnhub, Congress.gov, SEC,    ==>   (served from CDN edge, gzipped)
OpenAI/Chef GPT, QuantLib/TA         NO API calls, NO server, NO DB
   -> window.*_DATA .js files
```

## Initial-load budget

| | raw | gzipped (what the CDN sends) |
|---|---|---|
| All JS | ~7.8 MB | ~1.2 MB |
| Loaded on first paint | ~3.3 MB | ~0.6 MB |
| Lazy-loaded (State Legislature page only) | ~4.5 MB | ~0.6 MB |

`legiscan_data.js` (2.8 MB) and `openstates_data.js` (1.7 MB) are **not** in the
initial `<script>` block — `app.js` injects them only when the State Legislature
page is first opened. Most sessions never pay that 4.5 MB.

## Before every deploy

```bash
# 1. (optional) refresh data — see "Refreshing data" below
# 2. compact the JSON data files (~35% smaller raw, faster parse)
./tf_env/bin/python webapp/minify_data.py
# 3. deploy the webapp/ folder to any static host / CDN
```

## Host configuration (the ~10x transfer win)

Any static host works (Netlify, Vercel, Cloudflare Pages, S3+CloudFront, GitHub
Pages). Enable:

1. **Compression** — gzip or brotli on `.js`/`.css`/`.html`. JSON-heavy JS
   compresses ~6-10x (7.8 MB -> ~1.2 MB). Most CDNs do this automatically; if
   self-hosting (nginx), turn on `gzip on; gzip_types application/javascript;`
   (or `brotli on;`).
2. **Cache headers** — the generated data files are content-stable between
   builds, so cache them hard:
   - `js/*.js`, CSS, assets: `Cache-Control: public, max-age=604800` (or
     `immutable` if you fingerprint filenames).
   - `index.html`: `Cache-Control: no-cache` (so new deploys are picked up).
3. **HTTP/2 or HTTP/3** — lets the parallel `<script>` downloads multiplex.

That's it — no server, no database, no runtime secrets (all keys stay in
`.env`, used only by the offline build scripts and never shipped).

## Refreshing data (the offline "API pipeline")

Run the build scripts to regenerate the static data, then `minify_data.py`, then
redeploy. To keep the site fresh automatically, run these on a schedule (cron /
GitHub Action / cloud scheduler) and redeploy on completion:

```bash
./tf_env/bin/python webapp/build_data.py          # core market/news/trades/bills
./tf_env/bin/python webapp/build_prices.py        # Finnhub price + market cap
./tf_env/bin/python webapp/build_quant.py         # QuantLib + technical analysis
./tf_env/bin/python webapp/build_usaspending.py   # federal contracts (resumable)
./tf_env/bin/python webapp/build_relationships.py # Senate LDA lobbying
./tf_env/bin/python webapp/build_news_intel.py    # Chef GPT news summaries
./tf_env/bin/python webapp/build_legiscan.py      # state bills/votes
./tf_env/bin/python webapp/build_openstates.py    # state legislators
# ... (fec, sec, secbulk, states, census, nonprofits, sp500, member_bills, influence)
./tf_env/bin/python webapp/minify_data.py         # always last
```

Each script is incremental/idempotent and only hits the APIs at build time, so
production stays a static, instant-loading site regardless of how heavy the
upstream data work is.
