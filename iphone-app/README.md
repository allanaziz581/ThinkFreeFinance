# ThinkFree - iPhone App

A native **SwiftUI** iPhone app for ThinkFree, reusing the same real data as the
web platform (LittleSis, SEC EDGAR, USASpending, OpenFEC, ProPublica, FRED,
Census, BEA, BLS). The dashboard layout mirrors the web version.

## Screens (bottom tab bar)
- **Dashboard** - KPI tiles (Market Mood, Recession Risk, Direction, Top Story), the
  Political Watch feature card with the top trader's photo + ranked list, "How This
  Affects You" everyday costs, and the portfolio card. Layout matches the web.
- **News** - market overview summary, then stories ranked by source credibility with
  sentiment + credibility badges; tap a story for detail + the original source link.
- **Politics** - ranked politicians with photos; tap for a profile (net worth,
  portfolio, summary, most-traded), plus the compliance disclaimer.
- **Intelligence** - recession risk + factors, sector opportunity scores, and the
  Bill-Trade Correlation Index.

## How to open & run

The app uses [XcodeGen](https://github.com/yonyz/XcodeGen) to generate the Xcode
project from `project.yml` (so there's no fragile checked-in `.xcodeproj`).

```bash
# 1. install tools (one time)
brew install xcodegen

# 2. refresh bundled data from the web app (optional - already exported)
./tf_env/bin/python iphone-app/export_app_data.py

# 3. generate the Xcode project
cd iphone-app
xcodegen generate

# 4. open and run
open ThinkFree.xcodeproj
#    pick an iPhone simulator (or your device) and press Run (Cmd+R)
```

> No XcodeGen? Create a new Xcode project (iOS App, SwiftUI, name "ThinkFree"),
> delete its starter files, then drag the `ThinkFree/` folder (Models, Views, Theme,
> ThinkFreeApp.swift) and the `ThinkFree/Resources/` folder into the project
> (check "Copy items if needed" and "Create folder references" for Resources).

## Data
All data is bundled JSON in `ThinkFree/Resources/`, exported from `webapp/js/*.js`
by `export_app_data.py`. The app is fully offline - no API keys, no network calls.
Re-run the exporter after rebuilding the web data to refresh the app.

## Structure
```
iphone-app/
├── project.yml                 # XcodeGen spec
├── export_app_data.py          # webapp data -> bundled JSON
└── ThinkFree/
    ├── ThinkFreeApp.swift      # app entry + tab bar
    ├── Theme/Theme.swift       # dark fintech palette + Card/Pill components
    ├── Models/Models.swift     # Codable models
    ├── Models/DataStore.swift  # loads bundled JSON
    ├── Views/DashboardView.swift
    ├── Views/NewsView.swift
    ├── Views/PoliticalView.swift
    ├── Views/IntelligenceView.swift
    ├── Info.plist
    └── Resources/              # data.json, fec.json, ... + politicians/*.jpg
```
