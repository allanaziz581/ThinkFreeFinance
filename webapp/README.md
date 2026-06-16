# ThinkFree Web Front-End

A static, dependency-free web front-end matching the reference mockups — a clean
dark fintech "intelligence terminal" with a **clickable sidebar router** and
multiple pages. The original Streamlit app (`dashboard/app.py`) is kept untouched
as the prototype.

## Run it
Just open `index.html` in a browser (double-click). No server needed — data is
baked into `js/data.js`.

## Pages (sidebar navigation)
- **Dashboard** — KPI tiles, Political Watch feature, insight grid, portfolio, parallels
- **News** — Today's Market Summary, Top News, "What This Means For You"
- **Political Watch** — featured politician (real photo), Top 10 table, recent trades, conflict gauge, timeline, compliance disclaimer
- **My Portfolio** — open positions from `portfolio_snapshot.json`
- **Markets / Reasoning / History / Settings** — sector scores, recession indicators, parallels, profile

## Refresh the data
Re-reads the project JSON outputs and regenerates `js/data.js`:
```
python webapp/build_data.py
```
Sources: `politician_performance.json`, `portfolio_snapshot.json`,
`recession_signals_output.json`, `opportunity_scores.json`,
`historical_parallels.json`, `politician_parties.json`, `news_output/*`.

## Politician photos
Headshots live in `assets/politicians/{bioguide}.jpg`, fetched from the public-domain
@unitedstates image collection (keyed by the bioguide IDs in `politician_parties.json`):
```
python webapp/fetch_politician_photos.py
```
The UI falls back to initials if a photo is missing.

> Note: `PoliticianImages.zip` (GPO Pictorial Directory) is the offline alternative,
> but its PDFs pack several members per page and need a PDF renderer + face-crop step.
> The bioguide route above is recommended and needs no extra dependencies.

## Files
```
webapp/
├── index.html                  # shell: sidebar + topbar + ticker + page hosts
├── css/styles.css              # design system (tokens, grid, cards, gauges)
├── js/app.js                   # router + page renderers
├── js/data.js                  # AUTO-GENERATED real data (do not hand-edit)
├── build_data.py               # compiles project JSON -> data.js
├── fetch_politician_photos.py  # downloads headshots by bioguide id
└── assets/politicians/*.jpg    # headshots
```
