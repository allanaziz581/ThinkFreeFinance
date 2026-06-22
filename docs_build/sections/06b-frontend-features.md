# Part 6B — Frontend Reference: Feature Modules

This document is an exhaustive technical reference for the seven feature-module JavaScript files that power the ThinkFree Finance static webapp. Each module is self-contained in an IIFE, reads only from pre-loaded `window.*` globals, and writes its public API back onto `window.*`.

---

## Table of Contents

1. [influenceweb.js — Interactive Relationship Graph](#influencewebjs)
2. [congress.js — Political-Intelligence Drill-Down](#congressjs)
3. [genimpact.js — Generation Impact Engine](#genimpactjs)
4. [predictions.js — Predictive Market Signals](#predictionsjs)
5. [scores.js — ThinkFree Scores Engine](#scoresjs)
6. [scoreinfo.js — Progressive Score Explanation System](#scoreinfojs)
7. [glossary.js — Finance-Jargon Tooltips](#glossaryjs)

---

## influenceweb.js

**File:** `webapp/js/influenceweb.js`  
**Public API:** `window.IW`  
**Lines:** 1–1201

### Purpose

Renders and controls the interactive "InfluenceWeb" relationship graph — a force-directed bubble map rooted at a U.S. Congress hub node. Clicking any node expands it outward into children: Congress → Sectors → Companies → Category nodes (Board, Shareholders, Political Connections, Legislation, Lobbying, Government Contracts). A side panel opens alongside each focused node showing detailed accountability data. Cross-company relationship edges (shared lobby firm, shared institutional owner, shared board member) are drawn as dashed xlink lines across sectors.

### window.* Data Consumed

| Global | Shape | Purpose |
|--------|-------|---------|
| `window.TF_DATA` | `{bills, recent_trades, politicians, news, correlation, market_ticker}` | Bills, trades, politician list, news sentiment |
| `window.IW_DATA` | `{companies: { [ticker]: {name, domain, blurb, board, executives, owners, lda_registrant_id, fedspending_id} }}` | LittleSis company/board/owner data |
| `window.NP_DATA` | `{byName: { [orgName]: {name, ein, revenue_fmt, year, url} }}` | ProPublica nonprofit financials for lobbying groups |
| `window.SEC_DATA` | `{byTicker: { [ticker]: {entityName, board[], filedAt, latest_10k, filings} }}` | SEC EDGAR current board members |
| `window.SECBULK_DATA` | `{byTicker: { [ticker]: {revenue, net_income_fmt, assets, liabilities, filings_total, fy, sic} }}` | SEC EDGAR bulk financials |
| `window.FEC_DATA` | `{byName: {...}}` | OpenFEC campaign finance (passed through to other modules) |
| `window.USA_DATA` | `{byTicker: { [ticker]: {total_contracts, total_contracts_fmt, top_agencies[], url} }}` | USASpending.gov federal contracts |
| `window.RELATIONSHIPS` | `{byTicker: { [ticker]: {firms[], lobbyists[], issues[], bills[], spend_fmt, filings} }}` | Senate LDA lobbying relationships |
| `window.SP500` | `{byTicker: { [ticker]: {sector, name} }}` | S&P 500 membership for sector merging |
| `window.PRICES_DATA` | `{byTicker: { [ticker]: {name, market_cap, change_pct} }}` | Market price / cap data for sorting |
| `window.TFScores` | computed by scores.js | Influence / dependency scores displayed in panels |
| `window.CongressDrill` | computed by congress.js | Drill-down overlay opened on Congress click |

### Graph Data Model

**Nodes** are plain objects held in the module-scoped `nodes` array:

```js
{
  id: "n<seq>",          // unique string assigned by addNode()
  type: "congress" | "sector" | "company" | "more" | "category",
  colorType: "company" | "government" | "political" | "financial" | "other",
  label: string,
  ticker?: string,       // company and category nodes
  icon: string,          // key into the I{} SVG path map
  parent?: string,       // id of parent node (null for root)
  size: number,          // bubble diameter in px
  x, y: number,          // current world-space position
  vx, vy: number,        // velocity (physics integration)
  tx?, ty?: number,      // target slot position
  angle?: number,        // radial angle from parent (layout hint)
  targetDist?: number,   // target radial distance from parent
  expanded?: boolean,
  collapsing?: boolean,
  fresh?: boolean,       // true = newly added, triggers fade-in
  sensitive?: boolean,   // red ring: trades + bills + lobby all overlap
  _all?, _shown?: any,   // sector pagination state
  moreOf?: string,       // id of parent sector for "more" nodes
  cat?: string,          // category key for category nodes
  sub?: string,          // subtitle string for category nodes
  el?: HTMLElement,      // live DOM element (set by rebuild())
}
```

**Edges** are objects in the module-scoped `edges` array:

```js
{
  a: string,    // source node id
  b: string,    // target node id
  kind: "main" | "xlink",
  label?: string,   // xlink only: human-readable connection reason
  el?: SVGLineElement,
}
```

**nodeById** is a plain object mapping `id → node` for O(1) lookup.

### Layout and Rendering

**Coordinate system:** World space is centered at (0,0). The Congress root is pinned at the origin. The CSS `transform: translate(cam.x, cam.y) scale(cam.zoom)` is applied to `#iw-scene`, converting world→screen. Zoom bounds: `ZOOM_MIN = 0.3`, `ZOOM_MAX = 3.2`. Auto-fit never zooms closer than `FIT_MAX = 1.5`.

**Node sizes** (bubble diameter in px):

| Node type | Size |
|-----------|------|
| `congress` | 118 |
| `sector` | 94 |
| `company`, `more` | 72 |
| `category` | 56 |
| leaf / other | 50 |

**Sector ring:** 11 curated sectors + any additional sectors from SP500 merge. Each sector is placed at angle `-π/2 + (i/n) × 2π` on a dynamic radius computed by `dynRadius()`.

**Company fan layout (staggered zig-zag):** When a sector expands, company nodes fan outward in an arc away from the grandparent. When more than 5 children share a slot, alternate children are placed on an inner and outer radius row (stagger = `childFoot × 0.6`) to prevent overlap. Computed by `layoutChildren()` (influenceweb.js:340–374).

**Physics:** A two-pass force model in `physics()`:
1. Collision-only repulsion: pairs whose centres are closer than `(ra + rb + 34)` are pushed apart.
2. Spring toward slot: each node is pulled toward its `(tx, ty)` target with strength 0.14.
3. Integration: `vx = (vx + fx) × 0.55`. The Congress node is pinned at (0,0).

**Orbit dots:** Each bubble's animated ring has coloured dot `<span>` elements. Dot count encodes relationship richness: up to 10 for Congress/sector nodes, up to 8 for company nodes. Colours cycle through `["#38BDF8","#E9C46A","#EF4444","#14B8A6"]`.

**Company logos:** Clearbit logo CDN is used when `IWD[ticker].domain` is present. On image error, falls back to a 2–3 character initials `<span>` (influenceweb.js:516–518).

**Sensitivity ring:** A company node's `--ring` CSS variable is set to `#EF4444` (red) when `sensitive === true` (meaning trades, bills, and lobbying all overlap for that ticker), otherwise the type color (influenceweb.js:524).

### Interactions

**Zoom/pan (mouse):**
- Wheel on `#iw-canvas` zooms anchored at cursor world position (influenceweb.js:982–989).
- Mousedown + mousemove on canvas pans. A move of >4px sets `drag.moved = true`, suppressing the click handler (influenceweb.js:992–1003).
- `+` / `−` toolbar buttons call `zoomBtn(1.25)` / `zoomBtn(0.8)` centered on viewport midpoint.
- Reset/fit button calls `reset()`.

**Click on nodes:**
- `more` node: calls `revealMore()` to load the next batch of SHOW_LIMIT=12 companies.
- `congress` node: calls `IW.zoomToCongress()` then `CongressDrill.open()`.
- Expanded node (with children): calls `collapse()` to retract the branch, then re-fits camera.
- All other nodes: calls `focus()`.

**Hover:**
- `mouseover` on a node element calls `highlight(id, true)` (dims unrelated nodes/edges) and `showTip(n, e)` (floating brief tooltip).
- `mouseout` clears highlight and hides tooltip.

**Side panel delegated click handler (influenceweb.js:1046–1056):**
- `[data-conn]` → `connectionDetail()` (person-company connection panel)
- `[data-boardback]` → `boardListPanel()` (back to board list)
- `[data-copanel]` → `openPanel()` for the company node
- `[data-exec]` → `personPanel()` (person profile)
- `[data-co]` → `focus()` on matching company node, or expand sector first
- `[data-person]` → `window.politicianProfile()`
- `[data-bill]` → `window.billDetail()`
- `[data-up]` → `focus(nodeById[id])` (navigate up in breadcrumb)
- `[data-board]` → `boardListPanel()` (View All members button)

**Breadcrumb:** Click on a `.iw-crumb[data-cr]` calls `focus(nodeById[id])` to jump directly to that ancestor (influenceweb.js:1059).

### Cross-Company Relationship Links

xlink edges are drawn as dashed SVG lines styled with class `iw-xlink`. They appear when `showXlinks === true` (toggled via the Filters panel checkbox).

`linkSharedOwners()` (influenceweb.js:378–387) scans all visible company nodes pairwise (O(n²)) and calls `sharedLink(a, b)`. `sharedLink` checks in priority order:
1. Shared lobbying firm (from `REL[tk].firms`) → label "Both lobby via {firm}"
2. Shared institutional owner (from `IWD[tk].owners`) → label "Shared owner: {name}"
3. Shared board member (from `boardOf()`) → label "Shared board member: {name}"

The label string is stored as a native SVG `<title>` child so it appears in browser-native tooltips.

### Functions

#### `boardOf(tk)` — influenceweb.js:25–38
**Signature:** `boardOf(tk: string): BoardMember[]`  
Returns the board member list for ticker `tk`. Prefers live SEC EDGAR data from `SECD[tk].board` (normalised to `{name, title, age, committees, independent, since, source:"SEC"}`). Falls back to LittleSis `IWD[tk].board` and `.executives` (source:"LittleSis"). Normalises `independent` flag by checking the `position` string for the word "independent".

#### `buildPersonIndex()` — influenceweb.js:140–148
**Signature:** `buildPersonIndex(): void`  
Walks every ticker in the union of `IWD` and `SECD`, calls `boardOf()` for each, and populates `personIndex[name]` with `{ticker, company, title, current, role}` entries. Called once from `indexData()`. Side effect: populates the module-scoped `personIndex` object used by revolving-door detection.

#### `pushPerson(m, tk, company, role)` — influenceweb.js:151–153
**Signature:** `pushPerson(m: {name, title, current}, tk: string, company: string, role: string): void`  
Appends a single person-company entry to `personIndex[m.name]`. Called exclusively by `buildPersonIndex()`.

#### `indexData()` — influenceweb.js:156–166
**Signature:** `indexData(): void`  
Called once at first activate. Builds all secondary indexes:
- Calls `buildPersonIndex()`
- Deduplicates all bills (merging `D.bills` with `D.correlation.top_bills`) into `billsByTicker` and `lobbyBySector`
- Counts `tradeCount[ticker]` and populates `polsByTicker[ticker]` from `D.recent_trades`

Side effects: mutates `tradeCount`, `billsByTicker`, `polsByTicker`, `lobbyBySector`, `personIndex`.

#### `compName(tk)` — influenceweb.js:169
**Signature:** `compName(tk: string): string`  
Returns the best available display name for a ticker. Priority: `IWD → SECD → PX → SP → tk`.

#### `companyHasData(tk)` — influenceweb.js:172
**Signature:** `companyHasData(tk: string): boolean`  
Returns true when any of `IWD`, `SECD`, `tradeCount`, or `billsByTicker` has data for the ticker.

#### `sectorCompanies(sec)` — influenceweb.js:176–178
**Signature:** `sectorCompanies(sec: SectorDef): string[]`  
Returns all tickers in the sector sorted by market cap descending, then by `companyInfluence()` descending, then alphabetically.

#### `companyInfluence(tk)` — influenceweb.js:182–189
**Signature:** `companyInfluence(tk: string): number`  
Composite heuristic influence score (not capped). Formula:  
`18 + board.length × 1.4 + owners.length × 2.2 + bills × 2.2 + min(trades, 60) × 0.5`  
Used for graph sorting and orbit-dot count. Not the same as the formal `TFScores.influenceScore()`.

#### `sectorInfluence(sec)` — influenceweb.js:193–199
**Signature:** `sectorInfluence(sec: SectorDef): number`  
Aggregates company influence scores for a sector with a per-company cap (`× 0.18`) plus `lobbyBySector` group count (× 4). Used to rank sectors.

#### `influenceLabel(tk)` — influenceweb.js:203–205
**Signature:** `influenceLabel(tk: string): "High" | "Medium" | "Moderate"`  
Maps `companyInfluence()` to a tier: > 55 → High, > 35 → Medium, else → Moderate.

#### `sharedOwner(a, b)` — influenceweb.js:210–213
**Signature:** `sharedOwner(a: string, b: string): boolean`  
Returns true when `IWD[a].owners` and `IWD[b].owners` share any owner name (Set intersection).

#### `sharedLink(a, b)` — influenceweb.js:217–233
**Signature:** `sharedLink(a: string, b: string): string`  
Returns a human-readable connection description (or `""` if none). Priority: shared lobby firm > shared institutional owner > shared board member. Used for xlink edge labels.

#### `addNode(o)` — influenceweb.js:245–248
**Signature:** `addNode(o: Partial<Node>): Node`  
Assigns `o.id = "n" + seq++`, initialises `vx/vy = 0`, `fresh = true`, pushes to `nodes`, indexes in `nodeById`. Returns the node.

#### `addEdge(a, b, kind)` — influenceweb.js:252
**Signature:** `addEdge(a: Node|null, b: Node|null, kind: "main"|"xlink"): void`  
Pushes `{a:a.id, b:b.id, kind}` to `edges`. Guards against null inputs.

#### `sizeForType(o)` — influenceweb.js:256–264
**Signature:** `sizeForType(o: Node): number`  
Returns the bubble diameter (px) for a node's type. See the size table above.

#### `dynRadius(parent, count, childSize)` — influenceweb.js:269–274
**Signature:** `dynRadius(parent: Node, count: number, childSize?: number): number`  
Computes a ring radius large enough so `count` children of diameter `childSize` fit without overlapping. Returns `max(parentRadius + childRadius + 120, (count × footprint) / (2π), 260)`.

#### `expandCongress(cn)` — influenceweb.js:281–292
**Signature:** `expandCongress(cn: Node): void`  
Guards against double-expansion. Creates one sector node per entry in `SECTORS`, placed at evenly spaced angles on a `dynRadius()` circle. Each node starts at the Congress position and springs outward. Adds main edges Congress → sector.

#### `makeCompanyNode(sn, tk)` — influenceweb.js:295–300
**Signature:** `makeCompanyNode(sn: Node, tk: string): Node`  
Creates a company node, computes `sensitive` flag (true when trades + bills + sector lobby all present), adds a main edge from the sector node. Returns the new node.

#### `makeMoreNode(sn)` — influenceweb.js:303–308
**Signature:** `makeMoreNode(sn: Node): Node`  
Creates a "+N More" node showing how many companies remain hidden. Sets `moreOf = sn.id`. Adds a main edge from the sector node.

#### `expandSector(sn)` — influenceweb.js:311–319
**Signature:** `expandSector(sn: Node): void`  
Guards against double-expansion. Calls `sectorCompanies()`, creates up to `SHOW_LIMIT=12` company nodes plus a More node if needed, calls `layoutChildren()` and `linkSharedOwners()`.

#### `revealMore(moreNode)` — influenceweb.js:322–335
**Signature:** `revealMore(moreNode: Node): void`  
Removes the More node from `nodes`/`edges`/`nodeById`, creates the next batch of up to SHOW_LIMIT company nodes, increments `sn._shown`, creates a new More node if still needed, then calls `layoutChildren()`, `linkSharedOwners()`, `rebuild()`, and `fitSubtree(sn, 0.74)`.

#### `layoutChildren(parent)` — influenceweb.js:340–374
**Signature:** `layoutChildren(parent: Node): number`  
Distributes all children of `parent` around it. For root (no grandparent): full circle `span = 2π`. For non-root: outward fan with `span = min(π×0.9, 0.6 + (n-1)×0.2)`. Applies staggered zig-zag (2 rows) when `hasGrandparent && n > 5`. Sets `(tx, ty)` and `angle` on each child. Returns the outer radius.

#### `linkSharedOwners()` — influenceweb.js:378–387
**Signature:** `linkSharedOwners(): void`  
O(n²) scan of all visible company nodes. For each pair not already connected by an xlink, calls `sharedLink()` and pushes an xlink edge if a connection exists.

#### `politicalTies(tk)` — influenceweb.js:392–401
**Signature:** `politicalTies(tk: string): PoliticalTies`  
Returns `{traders, industry, firms, lobbyists, issues, bills, contracts, registered, spend, filings, sec, count}` for the Political Connections panel. Combines `polsByTicker`, `SECTOR_LOBBY`, `CROSS_LOBBY`, and `REL[tk]` lobbying data.

#### `expandCompany(cn)` — influenceweb.js:417–426
**Signature:** `expandCompany(cn: Node): void`  
Guards against double-expansion. Filters `CATEGORIES` (omitting `contracts` when no USASpending record exists), creates one category node per entry, calls `layoutChildren()`.

#### `expandNode(n)` — influenceweb.js:429–433
**Signature:** `expandNode(n: Node): void`  
Dispatcher: routes to `expandCongress`, `expandSector`, or `expandCompany` based on `n.type`.

#### `isDescendant(d, p)` — influenceweb.js:436–439
**Signature:** `isDescendant(d: Node, p: Node): boolean`  
Walks the parent chain of `d`; returns true if `p.id` appears at any level.

#### `collapse(node)` — influenceweb.js:443–451
**Signature:** `collapse(node: Node): void`  
Marks all non-collapsing descendants with `collapsing = true` and sets their `(tx, ty)` to the node's current position (glide inward). Pushes them to `leaving`. Calls `scheduleSweep()`.

#### `scheduleSweep()` — influenceweb.js:456–467
**Signature:** `scheduleSweep(): void`  
Defers DOM cleanup by 300ms (CSS animation duration). On timeout: removes leaving nodes/edges from the live arrays, deletes from `nodeById`, clears `leaving`, calls `rebuild()`. Guards against duplicate timers.

#### `collapseSiblings(n)` — influenceweb.js:471–472
**Signature:** `collapseSiblings(n: Node): void`  
Finds all nodes that share `n.parent`, are not `n`, and are expanded. Calls `collapse()` on each.

#### `s2w(sx, sy)` — influenceweb.js:477
**Signature:** `s2w(sx: number, sy: number): {x, y}`  
Converts screen (viewport-relative) coordinates to world (unzoomed) coordinates using the current camera.

#### `applyCam()` — influenceweb.js:480
**Signature:** `applyCam(): void`  
Writes `translate(cam.x px, cam.y px) scale(cam.zoom)` to `scene.style.transform`.

#### `rebuild()` — influenceweb.js:484–543
**Signature:** `rebuild(): void`  
Full DOM reconstruction. Removes all `.iw-node` divs and clears SVG. Re-creates one SVG `<line>` per edge and one `<div class="iw-node">` per node (with bubble, orbit dots, icon/logo, and label). Applies `iw-faded` to non-active sector nodes. Sets initial opacity for fresh/collapsing nodes and triggers fade transitions via `requestAnimationFrame`. Calls `syncDOM()` at the end.

#### `physics()` — influenceweb.js:547–582
**Signature:** `physics(): number`  
Single physics tick. Two passes: (1) collision-only repulsion for overlapping pairs; (2) spring-toward-slot for each non-congress node. Integrates with damping 0.55. Returns total `|vx| + |vy|` across all nodes (used to detect settlement).

#### `syncDOM()` — influenceweb.js:585–592
**Signature:** `syncDOM(): void`  
Cheap position sync: updates `.el.style.left/top` for every node and `x1/y1/x2/y2` for every edge SVG line. Called every animation frame.

#### `fitSubtree(parent, pad)` — influenceweb.js:596–612
**Signature:** `fitSubtree(parent: Node, pad?: number): void`  
Computes the axis-aligned bounding box of `parent` and its direct children (using `tx/ty` target positions). Sets `camT` to a zoom/pan that fits the bbox into the viewport with margin `pad` (default 0.85), bounded by `ZOOM_MIN` and `FIT_MAX`.

#### `orbitDots(n)` — influenceweb.js:616–627
**Signature:** `orbitDots(n: Node): string`  
Returns HTML `<span class="iw-odot">` elements arranged around the bubble ring. Count: up to 10 for Congress/sector, up to 8 for company, 0 for others. Colour cycles through 4 palette entries.

#### `setBreadcrumb(n)` — influenceweb.js:630–635
**Signature:** `setBreadcrumb(n: Node): void`  
Walks the parent chain of `n` to build a path array, then injects `<span class="iw-crumb">` elements separated by `›` into `#iw-breadcrumb`.

#### `focus(n)` — influenceweb.js:639–659
**Signature:** `focus(n: Node): void`  
The primary interaction handler. Sets `selectedId`, calls `collapseSiblings()`, updates `focusedSector`, calls `expandNode()`, `rebuild()`, `setBreadcrumb()`, `openPanel()`. Adds `iw-focus` CSS class to the node element. Calls `fitSubtree()` or snaps the camera to the node. Sets `settle = 90`.

#### `influenceBadge(tk)` — influenceweb.js:664
**Signature:** `influenceBadge(tk: string): string`  
Returns a coloured `<span>` for the influence tier label ("High"=red, "Medium"=yellow, "Moderate"=teal). Used inside panel HTML.

#### `scoreBlock(tk)` — influenceweb.js:668–680
**Signature:** `scoreBlock(tk: string): string`  
Returns HTML for two `iw-meter` bar rows (Influence Score + Government Dependency) if `window.TFScores` is loaded. Each bar includes a ScoreInfo `si` anchor with `data-si-kind`, `data-si-key`, and `data-si-val` attributes for the progressive-disclosure tooltip system.

#### `secFinancials(tk)` — influenceweb.js:683–695
**Signature:** `secFinancials(tk: string): string`  
Returns a 6-cell grid of SEC EDGAR financials (Revenue, Net Income, Assets, Liabilities, Filings, SIC Industry) from `SECBULK_DATA`. Returns `""` when no data is available.

#### `openPanel(n)` — influenceweb.js:698–748
**Signature:** `openPanel(n: Node): void`  
Builds and injects the panel `innerHTML` based on `n.type`:
- **congress**: stats grid (sectors, companies, bills count) + hint text.
- **sector**: company count + chip list of first 12 tickers.
- **company**: back button, score block, stats grid, SEC financials, "Connected To Congress Through" section, board member rows, peers chip list, latest 10-K link.
- **category**: delegates to `categoryPanel(n)`.

Adds `open` class to the panel element.

#### `currentSectorPeers(tk)` — influenceweb.js:752–755
**Signature:** `currentSectorPeers(tk: string): string[]`  
Returns all other tickers in the same sector as `tk`, sorted by `sectorCompanies()`.

#### `memberRow(m, fromTk)` — influenceweb.js:758–771
**Signature:** `memberRow(m: BoardMember, fromTk: string): string`  
Returns an HTML `<div class="iw-member iw-clickable">` with initials avatar, name, title, and optional badges (Independent, age, committees, connection count). Includes `data-exec` and `data-from` attributes for the click delegation handler.

#### `boardListPanel(tk)` — influenceweb.js:775–784
**Signature:** `boardListPanel(tk: string): void`  
Injects the full board member list for a company into the panel body. Shows source attribution (SEC EDGAR vs. LittleSis). Back button navigates to the company panel.

#### `personPanel(name, fromTk)` — influenceweb.js:788–824
**Signature:** `personPanel(name: string, fromTk?: string): void`  
Renders the person profile panel. Splits `personIndex[name]` into current and previous positions. Current items show normal avatars; previous items show amber avatars with "Revolving Door" label. Each item is a clickable row that opens `connectionDetail()`.

#### `connectionDetail(name, tk, title, isCurrent, fromTk)` — influenceweb.js:828–841
**Signature:** `connectionDetail(name: string, tk: string, title: string, isCurrent: boolean, fromTk: string): void`  
Renders an explanation of a single person–company relationship. Active connections describe a current board role. Previous connections use the revolving-door framing: "career transition; does not imply wrongdoing."

#### `howtoPanel()` — influenceweb.js:844–866
**Signature:** `howtoPanel(): void`  
Renders a static guide panel explaining navigation controls, graph levels, and node colours. Triggered by the `?` toolbar button.

#### `filtersPanel()` — influenceweb.js:869–884
**Signature:** `filtersPanel(): void`  
Renders the graph filters panel including a checkbox to toggle cross-links (xlinks). The checkbox `change` event mutates `showXlinks` and calls `rebuild()`. Also shows the relationship type legend.

#### `categoryPanel(n)` — influenceweb.js:887–965
**Signature:** `categoryPanel(n: Node): string`  
Returns the HTML body string for a category node's panel. Branches by `n.cat`:
- **board**: board member list (same as `boardListPanel` body).
- **shareholders**: owner list from `IWD[tk].owners`.
- **political**: full political connections breakdown (lobby firms, bills lobbied, issues, lobbyists, congressional traders, industry associations, contracts). Ends with transparency disclaimer.
- **bills**: chip list of `billsByTicker[tk]` bill IDs.
- **lobbying**: ProPublica 990 rows for industry/cross-sector lobby groups with revenue, EIN, link.
- **contracts** (default fallback): USASpending total + top agency breakdown with link.

#### `logo(tk)` — influenceweb.js:968–971
**Signature:** `logo(tk: string): string`  
Returns a Clearbit `<img>` with fallback to a 3-character initials `<span>` for use in panel chip lists.

#### `closePanel()` — influenceweb.js:974
**Signature:** `closePanel(): void`  
Removes the `open` CSS class from the panel element.

#### `bind()` — influenceweb.js:979–1065
**Signature:** `bind(): void`  
Attaches all interaction event listeners:
- Wheel zoom on canvas (passive:false, calls `s2w` for anchor-at-cursor).
- Mousedown/mousemove/mouseup for drag-to-pan.
- Click delegation on `#iw-scene` for node clicks.
- Mouseover/mouseout on scene for highlight + tooltip.
- Click delegation on panel for back navigation and sub-panels.
- Panel close button.
- Breadcrumb click.
- Zoom +/− and fit/reset buttons.
- How-to and filters toolbar buttons.

#### `zoomBtn(f)` — influenceweb.js:1068–1072
**Signature:** `zoomBtn(f: number): void`  
Zooms by factor `f` centered on the viewport midpoint. Does not use `camT`; applies immediately.

#### `highlight(id)` — influenceweb.js:1075–1084
**Signature:** `highlight(id?: string): void`  
When `id` is given: dims all nodes/edges that are not connected to `id`. When `id` is null/undefined: clears all dim/hot classes. Uses edge adjacency set for O(edges) lookup.

#### `showTip(n, e)` — influenceweb.js:1087–1097
**Signature:** `showTip(n: Node, e: MouseEvent): void`  
Positions and shows `#iw-tip` with the node's label and a brief subtitle. Tooltip is positioned at cursor + 16px offset within the canvas.

#### `reset()` — influenceweb.js:1100–1114
**Signature:** `reset(): void`  
Clears all node/edge arrays and counters. Creates the Congress root node, calls `expandCongress()`, calls `rebuild()`. Sets `cam` to `{x: W/2, y: H/2, zoom: 0.45}`, calls `fitSubtree()`. Sets `settle = 140`. Shows HUD. Closes panel.

#### `loop()` — influenceweb.js:1117–1132
**Signature:** `loop(): void`  
Main `requestAnimationFrame` loop. When `active`: runs `physics()` and `syncDOM()` while `settle > 0` or `moving >= 0.6`. Interpolates `camT` toward `cam` at rate 0.1 per frame. Calls `applyCam()` every frame.

#### `size()` — influenceweb.js:1135
**Signature:** `size(): void`  
Reads `canvas.getBoundingClientRect()` into `W, H`. Resets SVG dimensions to 1×1 (SVG overflow handles the actual size).

### window.IW Public API

#### `IW.activate()` — influenceweb.js:1140–1150
Binds scene/canvas/panel/tip/hud DOM references. On first call: runs `indexData()`, `size()`, `bind()`, `reset()`, attaches resize handler, starts the animation loop. On subsequent calls: sets `active = true` and re-fits camera.

#### `IW.deactivate()` — influenceweb.js:1152
Sets `active = false` and hides the tooltip.

#### `IW.zoomToCongress(cb)` — influenceweb.js:1155–1165
Animates the camera to zoom in (scale 2.4) centered on the Congress node. All non-Congress nodes fade to 6% opacity. Fires callback after 540ms delay. Saves pre-zoom camera to `preZoomCam`.

#### `IW.zoomOut()` — influenceweb.js:1167–1172
Reverses the Congress zoom: restores all node opacities, restores `preZoomCam` to `camT` for smooth interpolation.

#### `IW.resetView()` — influenceweb.js:1175–1179
Closes the drill overlay, clears `preZoomCam`, calls `reset()`.

#### `IW.openCompany(tk)` — influenceweb.js:1181–1199
Deep-links to a specific company. Calls `this.activate()`, finds the sector node, calls `focus(sn)`, then after 120ms focuses the company node (or reveals more companies first if the ticker is beyond the initial 12).

---

## congress.js

**File:** `webapp/js/congress.js`  
**Public API:** `window.CongressDrill`  
**Lines:** 1–582

### Purpose

Renders the U.S. Congress drill-down overlay (`#iw-drill`). Provides four sub-views accessible from the Congress hub node:
1. **House constellation** — scatter plot of tracked House members
2. **Senate constellation** — scatter plot of tracked Senate/Congress members
3. **Governors** — SVG choropleth / CSS tile cartogram of all 50 state governors
4. **Generation Impact** — per-bill generation impact scores

Per-member hover cards surface FEC funding influence breakdowns (individual vs. PAC vs. other) with optional pie charts. State hover cards show Census economic indicators. The module enforces the transparency-not-accusation framing throughout: all political intelligence output describes timing/funding relationships from public data and never implies wrongdoing.

### window.* Data Consumed

| Global | Shape | Purpose |
|--------|-------|---------|
| `window.TF_DATA` | `{politicians[], bills[], correlation.top_bills[], disclaimer}` | Politician list, bill list, disclaimer text |
| `window.FEC_DATA` | `{byName: { [name]: {receipts, from_individuals, from_pacs, receipts_fmt, url} }}` | OpenFEC campaign finance receipts |
| `window.STATES_DATA` | `{byState: { [stAbbr]: {name, cost_of_living, median_household_income, poverty_rate, unemployment, inflation, affordability, pressure_score, prosperity_score, real_purchasing_power, income_growth} }}` | Census state economics |
| `window.MEMBER_BILLS` | `{byBioguide: { [id]: {total, sponsored, cosponsored} }}` | Congress.gov sponsored/cosponsored bill counts |
| `window.GenImpact` | computed by genimpact.js | Generation impact engine (optional, falls back to local calculation) |
| `window.ScoreInfo` | computed by scoreinfo.js | Badge renderer for score spans (optional) |
| `window.US_MAP_PATHS` | `{[stAbbr]: svgPathData}` | SVG state outline paths (optional, falls back to tile grid) |
| `window.US_MAP_VIEWBOX` | string | SVG viewBox for the US map (default: "174 100 959 593") |
| `window.IW` | computed by influenceweb.js | Graph reset on drill close |
| `window.politicianProfile` | function | External handler for full politician profile |
| `window.stockDetail` | function | External handler for stock detail drawer |
| `window.billDetail` | function | External handler for bill detail |

### Transparency-Not-Accusation Framing

Every political intelligence sub-view includes disclaimer text anchored in the HTML. The footer of `modulesView()` renders `D.disclaimer` (falling back to a hardcoded string). The hover card expanded view always ends with:
> "Funding influence breakdown from FEC and OpenSecrets-style disclosures. Describes outside-funding exposure; does not imply wrongdoing."

The `fundNote` logic (congress.js:249–251) derives a plain-English funding observation from PAC share thresholds:
- ≥ 40%: "Potential influence concentration: high outside-funding exposure."
- ≥ 20%: "Moderate industry-linked support."
- < 20%: "Largely individually funded."

### DOM Target

`#iw-drill` — a full-height slide-in panel. All views are injected via `show(html)` (congress.js:134). The element is made visible with class `open`.

### Functions

#### `funding(name)` — congress.js:61–68
**Signature:** `funding(name: string): FundingBreakdown | null`  
Reads `FEC[name]` and computes percentage breakdowns. Returns `{individual, pac, other, total_fmt, raised}` or `null` when no FEC record exists.

#### `scores(p)` — congress.js:73–80
**Signature:** `scores(p: PoliticianRecord): {influence, transparency, publicImpact, exposure}`  
Derives 0–100 scores from live signals:
- `influence = min(100, 30 + trades × 0.3 + pacShare × 0.6 + |ret| × 0.5)`
- `transparency = max(5, 100 − pacShare × 1.4 − trades × 0.15)`
- `publicImpact = max(10, 70 − pacShare × 0.5 + individual × 0.2)`

These mirror the formulas in `scoreinfo.js` to ensure consistency between the hover card and the full modal.

#### `billGenerationImpact(bill)` — congress.js:111–124
**Signature:** `billGenerationImpact(bill: BillRecord): GenImpactRow[]`  
Local fallback (used when `window.GenImpact` is unavailable). Averages sector weights from `SECTOR_GEN` across all bill sectors, scales to `−70..+70`. Returns `[{gen, score, reason}]` for each of the five cohorts.

#### `ensureHost()` — congress.js:129–132
**Signature:** `ensureHost(): HTMLElement | null`  
Gets or assigns the `host` reference to `#iw-drill`.

#### `show(html)` — congress.js:134
**Signature:** `show(html: string): void`  
Injects `html` into `host.innerHTML`, adds class `open`, resets scroll to top.

#### `close()` — congress.js:135
**Signature:** `close(): void`  
Removes class `open` from the host. Calls `window.IW.resetView()` if available.

#### `modulesView()` — congress.js:138–172
**Signature:** `modulesView(): void`  
Renders the Level 1 Congress landing view: four module cards (House, Senate, Governors, Generation Impact) with member counts from `D.politicians`. Includes the disclaimer footer. Uses `show()`.

#### `constellation(kind)` — congress.js:177–207
**Signature:** `constellation(kind: "house" | "senate"): void`  
Renders the Level 2 member constellation view. Filters `D.politicians` by chamber. Lays dots using the golden-angle spiral: `angle = i × 137.5° × π/180`, `r = 6 + 40 × sqrt(i / n)`. Each dot is a `<span class="cd-dot">` with party-color background. Shows a party count legend. Includes `#cd-hover` placeholder for the hover card.

#### `fundingPie(f, size)` — congress.js:212–229
**Signature:** `fundingPie(f: FundingBreakdown, size?: number): string`  
Returns an SVG pie chart string. Segments: individual (green `#22C55E`), PAC (red `#EF4444`), other (gray `#64748B`). When only one non-zero segment exists, renders a filled circle instead. Default size 40px.

#### `hoverCard(name, dotEl, big)` — congress.js:236–310
**Signature:** `hoverCard(name: string, dotEl: HTMLElement|null, big: boolean): void`  
Renders the politician hover card into `#cd-hover`. Compact view (`big=false`): small pie, activity summary (trades, bills, return), ticker chips. Expanded view (`big=true`): large pie with totals, legislative career totals, PAC/outside spending list, top donors/industries, disclaimer footer. Calls `placeCard()` to position it. Stores `curPolName` and `curDotEl` for toggle continuity.

#### `placeCard(dotEl)` — congress.js:314–328
**Signature:** `placeCard(dotEl: HTMLElement): void`  
Positions `#cd-hover` relative to the dot element, flipping left when right-side overflow would occur. Clamps to drill panel bounds.

#### `hideHover()` — congress.js:331
**Signature:** `hideHover(): void`  
Removes `open` and `big` classes from `#cd-hover`. Clears `curPolName`.

#### `applyMapTf()` — congress.js:338–341
**Signature:** `applyMapTf(): void`  
Applies `translate(x y) scale(s)` to the `#cd-map-g` SVG group. Used for governors map pan/zoom.

#### `partyCount(ab)` — congress.js:344
**Signature:** `partyCount(ab: string): number`  
Counts how many governors in `GOVERNORS` have the given party abbreviation.

#### `governorsView()` — congress.js:348–375
**Signature:** `governorsView(): void`  
Renders the governors panel. Prefers SVG choropleth from `window.US_MAP_PATHS`: renders `<path class="cd-state-path">` elements with fill `${partyColor}33` and matching stroke. Falls back to a CSS grid tile cartogram using `TILE` row/col positions. Includes zoom (+/−/reset) buttons and the hover card placeholder.

#### `stateHover(st, ev)` — congress.js:379–403
**Signature:** `stateHover(st: string, ev: MouseEvent): void`  
Shows a transient hover card near the mouse with Census economics for state `st`: cost of living, median income, poverty rate, unemployment, inflation, affordability, cost pressure tier, and prosperity score. Positioned relative to cursor, clamped to drill panel.

#### `generationView(billId)` — congress.js:408–438
**Signature:** `generationView(billId?: string): void`  
Renders the Generation Impact overlay. Finds the bill in `D.bills + D.correlation.top_bills`. If `window.GenImpact` is loaded, calls `GI.forBill(bill)` and `GI.panel(res, {reasons:true, dims:true})`. Otherwise calls local `billGenerationImpact()` and renders coloured horizontal bars. Shows a bill-picker chip row (first 8 bills). Shows affected sectors, companies, and politicians chips below the bars.

#### `genImpactFromState(s)` — congress.js:443–448
**Signature:** `genImpactFromState(s: StateRecord): GenImpactRow[]`  
Derives generation impact scores from state cost statistics: pressure score, affordability index, and inflation rate. Applies generation-specific tilt multipliers (`Gen Z: 1.2, Millennials: 1.4, Gen X: 0.9, Boomers: 0.5, Retirees: 0.6`). Returns `[{gen, score}]` clamped to `[−90, +40]`.

#### `genBars(impacts)` — congress.js:452–459
**Signature:** `genBars(impacts: GenImpactRow[]): string`  
Renders compact horizontal bar rows for a state detail panel (used when `window.GenImpact` is unavailable).

#### `stateDetail(st)` — congress.js:463–502
**Signature:** `stateDetail(st: string): void`  
Renders the full state detail panel. Shows governor name and party, two card columns (State Economy + Pressure Snapshot), a generation impact section (via `window.GenImpact.panel()` or `genBars()`), and a Federal Bills In Play chip list.

#### `bind()` — congress.js:515–573
**Signature:** `bind(): void`  
Attaches all event listeners to `#iw-drill` using a sentinel `_bound` flag to prevent double-binding. Single delegated `click` handler routes to all sub-view functions via `data-dc` attributes. `mousemove` handler activates politician dot hover cards and state hover cards. Separate `mousedown`/`mousemove`/`mouseup` listeners on `window` manage SVG map dragging. Wheel zoom on `#cd-map-wrap` (passive:false).

### window.CongressDrill Public API

#### `CongressDrill.open()` — congress.js:579
**Signature:** `open(): void`  
Calls `bind()` then `modulesView()`. Entry point called by `influenceweb.js` when the Congress node is clicked.

#### `CongressDrill.generation(billId)` — congress.js:580
**Signature:** `generation(billId: string): void`  
Calls `bind()` then `generationView(billId)`. Allows other modules to jump directly to the generation-impact overlay for a specific bill.

---

## genimpact.js

**File:** `webapp/js/genimpact.js`  
**Public API:** `window.GenImpact`  
**Lines:** 1–337

### Purpose

The Generation Impact engine. A reusable heuristic translation layer that estimates how a bill, company, sector, or state's economic activity may land on each of the five U.S. generational cohorts across six life dimensions. Outputs per-generation signed scores (−100..+100), a confidence percentage, and a plain-English reason. Used by `app.js`, `congress.js`, and `influenceweb.js`.

### Framing Rule (Non-Negotiable)

Every rendered panel ends with:  
> "Estimate of likely exposure by generation. Plain-English, non-partisan; does not imply wrongdoing."

### window.* Data Consumed

`window.ScoreInfo` — optional; when loaded, score values become clickable info chips.

### Data Tables

**`GENS`** (genimpact.js:27): `["Gen Z", "Millennials", "Gen X", "Baby Boomers", "Retirees"]`

**`DIMS`** (genimpact.js:31–38): six dimension pairs `[key, displayLabel]`:
`costOfLiving, housing, income, healthcare, jobs, retirement`

**`GEN_WEIGHT`** (genimpact.js:42–48): How exposed each generation is to each dimension (0..1). Gen Z weights jobs highest (1.0). Retirees weight healthcare (1.0) and retirement (1.0) highest.

**`AREA`** (genimpact.js:54–80): Signed per-dimension effect vectors for each policy area (−1..+1). 23 entries including Real Estate, Healthcare, Technology, Wages & Labor, Taxes, Education, Benefits, and a "default" fallback.

**`REASON_DIM`** (genimpact.js:84–97): Plain-English reason fragments keyed by dimension and direction (`harm` / `help`).

### Functions

#### `clamp(v, lo, hi)` — genimpact.js:100
**Signature:** `clamp(v: number, lo: number, hi: number): number`  
Standard clamp. Used throughout all score calculations.

#### `matchArea(s)` — genimpact.js:103–129
**Signature:** `matchArea(s: string): string | null`  
Maps a free-form sector/industry/topic string to an `AREA` key. Tries exact match first (avoids substring collisions), then falls back to substring keyword matching (e.g. "pharma" → "Pharmaceuticals", "health" → "Health Care"). Returns `null` when no match found.

#### `fromAreas(areas, opts)` — genimpact.js:134–176
**Signature:** `fromAreas(areas: string[], opts?: {orientation?: number, confidenceBoost?: number}): GenerationResult`  
**Core computation function.** Maps each string in `areas` through `matchArea()`, aggregates signed dimension effects (averaged across matched areas), then for each generation computes:
- Per-dimension score: `clamp(round(eff[d] × w[d] × 110 × orient), −100, 100)`
- Overall score: weighted average across dimensions
- Reason: uses the `REASON_DIM` template for the strongest-magnitude dimension

Confidence formula: `clamp(50 + matched × 12 + confidenceBoost, 35, 95)`

Returns `{gens, confidence, areas, matched}`.

#### `forSectors(sectors, opts)` — genimpact.js:181
**Signature:** `forSectors(sectors: string[], opts?: object): GenerationResult`  
Thin wrapper: calls `fromAreas(sectors, opts)` directly.

#### `forBill(bill, opts)` — genimpact.js:185–196
**Signature:** `forBill(bill: BillRecord, opts?: object): GenerationResult`  
Concatenates `bill.sectors` and `bill.topics`, calls `fromAreas()`. Augments result with `{status, title, id, politicians, companies, sectors}` metadata. Status is derived by `billStatus()`.

#### `forCompany(ticker, industry, sectors, opts)` — genimpact.js:200–205
**Signature:** `forCompany(ticker: string, industry: string, sectors: string[], opts?: object): GenerationResult`  
Combines `sectors` and `industry` into an areas array, falls back to `["default"]`. Augments result with `{ticker}`.

#### `forState(s, opts)` — genimpact.js:210–234
**Signature:** `forState(s: StateRecord, opts?: object): GenerationResult`  
Builds a synthetic dimension effect vector directly from real state statistics:
- `costOfLiving = clamp(−(pressure − 40) / 60, −1, 0.4)`
- `housing = clamp(−(60 − afford) / 60, −1, 0.4)`
- `income = clamp(income_growth / 6, −1, 1)`
- `healthcare = clamp(−(infl − 2) / 6, −1, 0.3)`
- `jobs = clamp((4.5 − unemp) / 4, −1, 1)`
- `retirement = clamp(−(infl − 2) / 8, −1, 0.3)`

Runs the same generation-weighting pass as `fromAreas`. Returns confidence=70 (fixed, since state data is directly measured).

#### `billStatus(bill)` — genimpact.js:237–243
**Signature:** `billStatus(bill: BillRecord): "Passed" | "Failed" | "Proposed"`  
Checks `bill.status` or `bill.action_text` for keywords. Returns "Passed" on enacted/signed, "Failed" on vetoed/dead, "Proposed" otherwise.

#### `siGen(g, res)` — genimpact.js:257–271
**Signature:** `siGen(g: GenResult, res: GenerationResult): ScoreInfoPayload`  
Builds the structured `ScoreInfo` explainer payload for one generation's impact score. Sorts dimensions by absolute magnitude, takes the top two for contributor rows, and includes the full weighted-score formula.

#### `bars(res, opts)` — genimpact.js:275–289
**Signature:** `bars(res: GenerationResult, opts?: {reasons?: boolean}): string`  
Renders horizontal bar chart HTML (`<div class="gimp-bars">`). Each row shows the generation label, coloured score (with ScoreInfo chip if `window.ScoreInfo` loaded), a proportional bar, and optional reason text. Green for positive scores, red for negative, gray for neutral (|score| ≤ 8).

#### `confBadge(res)` — genimpact.js:293–303
**Signature:** `confBadge(res: GenerationResult): string`  
Returns the confidence percentage as either a plain string or a ScoreInfo chip explaining how it was calculated.

#### `dimGrid(res)` — genimpact.js:306–315
**Signature:** `dimGrid(res: GenerationResult): string`  
Returns a 6-cell grid showing each dimension's score for the most-affected generation (highest |overall|). Used in the detailed view.

#### `panel(res, opts)` — genimpact.js:319–328
**Signature:** `panel(res: GenerationResult, opts?: {title?: string, reasons?: boolean, dims?: boolean}): string`  
Assembles the complete Generation Impact panel HTML: header (with status badge and/or confidence badge), `bars()`, optional `dimGrid()`, optional confidence line, and the non-partisan disclaimer footer. Returns an HTML string.

### window.GenImpact Public API

```js
window.GenImpact = {
  GENS,       // ["Gen Z", "Millennials", "Gen X", "Baby Boomers", "Retirees"]
  DIMS,       // [[key, label], ...]
  forSectors, forBill, forCompany, forState, billStatus,
  bars, dimGrid, panel,
}
```

---

## predictions.js

**File:** `webapp/js/predictions.js`  
**Public API:** `window.Predictions`  
**Lines:** 1–323

### Purpose

Renders the "Predictive Market Signals" section. Reads precomputed technical-analysis signals (RSI, MACD, moving-average crossovers, QuantLib Black-Scholes metrics), market-wide VIX/index data, congressional trading flow, and policy exposure to produce a bullish-probability score, directional label, forecast cone SVG, confidence rating, and time horizon for each candidate ticker. Registers itself with `window.ScoreInfo` so the progressive-disclosure system can open full breakdowns on click.

### window.* Data Consumed

| Global | Shape | Purpose |
|--------|-------|---------|
| `window.TF_DATA` | `{news[], recent_trades[], market_ticker[]}` | News sentiment, congressional trades, VIX/indices |
| `window.PRICES_DATA` | `{byTicker: {name, change_pct}}` | Current price and daily change |
| `window.USA_DATA` | `{byTicker: {total_contracts}}` | USASpending presence (used in candidate ranking) |
| `window.SP500` | `{byTicker: {sector, name}}` | Sector membership for peer momentum |
| `window.QUANT_DATA` | `{byTicker: {exp_return_1mo, prob_up, prob_down, volatility, ta_score, rsi, rsi_signal, macd_cross, trend, var95, sharpe}}` | QuantLib Black-Scholes + TA metrics |
| `window.TFScores` | computed by scores.js | `politicalExposure()` for policy factor |
| `window.ScoreInfo` | computed by scoreinfo.js | Explainer registration and badge rendering |

### Factor Weights

Eight factors summed with weights totalling 1.0:

| Factor | Weight | Signal Source |
|--------|--------|---------------|
| News Sentiment | 0.20 | Ratio pos/neg headlines from `D.news` |
| Social Sentiment | 0.15 | Congressional buy vs. sell ratio from `D.recent_trades` |
| QuantLib Forecast / Historical Pattern | 0.15 | `Q.exp_return_1mo`, `Q.prob_up/down`; falls back to price momentum |
| Technical (RSI/MACD) / Technical Momentum | 0.15 | `Q.ta_score`; falls back to `chg × 4` |
| VIX / Fear | 0.10 | `VIX` + `Q.volatility` penalty |
| Sector Strength | 0.10 | Average sector peer daily change |
| Macro Environment | 0.10 | S&P + NASDAQ change minus rate pressure |
| Policy Impact | 0.05 | Congressional flow + contracts + bill count |

All factors return a 0–100 score where 50 = neutral.

### Functions

#### `factors(tk)` — predictions.js:59–114
**Signature:** `factors(tk: string): Factor[]`  
Returns an array of 8 factor objects `{key, label, w, v, ...extra}`. Each factor computes its score from the relevant signals as described in the weight table. Uses `Q[tk]` (QuantLib data) when available and falls back to simpler proxies.

- **newsScore**: `clamp(50 + (pos − neg) / news.length × 45, 5, 95)`
- **socialScore**: `clamp(50 + (buys − sells) / (buys + sells) × 40, 8, 92)`
- **patternScore** (with QuantLib): `clamp(50 + Q.exp_return_1mo × 9 + (Q.prob_up − Q.prob_down) × 1.2, 8, 92)`
- **techScore** (with QuantLib): `Q.ta_score` directly (already 0–100)
- **vixScore**: `clamp(100 − (VIX − 12) × 3.5 − ownVolPen, 8, 95)` where `ownVolPen = clamp((Q.volatility − 25) × 0.6, −8, 24)`
- **sectorScore**: `clamp(50 + sectorChg[sec] × 6, 12, 92)`
- **macroScore**: `clamp(50 + (SPCHG + NDCHG) × 6 − YLDCHG × 30, 15, 88)`
- **policyScore**: base 50 + trade flow ± 22 + 6 if contracts + min(bills, 10)

#### `compute(tk)` — predictions.js:127–149
**Signature:** `compute(tk: string): Prediction`  
Calls `factors(tk)`, computes the weighted sum score, maps to `dirLabel/dirClass` via `DIR()`. Computes confidence from data depth (news count, trade count, price data, contracts, QuantLib) and factor agreement. Derives time horizon from VIX level. Returns `{ticker, name, score, dirLabel, dirClass, confidence, confScore, horizon, factors, bull}`.

**Confidence levels:** depth/7 × 50 + agreement/8 × 50 → High ≥ 66, Medium ≥ 45, Low < 45.  
**Horizon:** VIX ≥ 25 → "1–7 Days", ≥ 16 → "7 Days", < 16 → "30 Days".

#### `drivers(p)` — predictions.js:152–183
**Signature:** `drivers(p: Prediction): {up: string[], down: string[]}`  
Converts factor scores to plain-English upside/downside driver lists. Factors ≥ 56 → upside phrase, ≤ 44 → downside phrase. Supplements with specific QuantLib signal names when `Q[tk]` is available (QuantLib positive/negative drift, RSI oversold/overbought, golden/death cross, high volatility). Adds market-level phrases for rising rates and elevated VIX.

#### `explain(tk)` — predictions.js:187–248
**Signature:** `explain(tk: string): ScoreInfoPayload`  
Builds the full ScoreInfo explainer payload for a ticker. Calls `compute()` and `drivers()`. Assembles:
- QuantLib-derived input rows (volatility, Black-Scholes prob, VaR, expected return, Sharpe, RSI, MACD, trend)
- Sentiment/macro/policy rows
- Weighted-score calculation table for all 8 factors
- Eight source attributions (QuantLib, TA library, Finnhub, news, STOCK Act, USASpending, Congress.gov, SEC)
- Non-financial-advice disclaimer footer

#### `cone(p)` — predictions.js:254–272
**Signature:** `cone(p: Prediction): string`  
Returns an SVG forecast cone. The triangle's slope encodes directional bias (`score − 50) / 50`). The band half-width encodes uncertainty: `Q.volatility / 100 × H × 0.55` when QuantLib is available, else `(1 − confScore/100) × H × 0.42`. Colour: green ≥ 55, red ≤ 45, gray otherwise. Uses a `linearGradient` that fades from 32% to 6% opacity toward the right.

#### `card(p)` — predictions.js:277–292
**Signature:** `card(p: Prediction): string`  
Returns HTML for one prediction card: ticker + name, directional label (with ScoreInfo chip), bullish probability score (with ScoreInfo chip), forecast cone SVG, horizon and confidence metadata (with ScoreInfo chip), and a "Why?" button (also a ScoreInfo chip). All `.si` anchors carry `data-si-kind="prediction"` and `data-si-key=ticker`.

#### `candidates()` — predictions.js:296–301
**Signature:** `candidates(): string[]`  
Selects up to 8 tickers from the union of `newsByTk` and `tradeByTk` keys. Filters to valid uppercase ticker symbols with price data. Ranks by activity score: `news.length + trades.length × 0.5 + (has contracts ? 1 : 0)`.

#### `render()` — predictions.js:305–317
**Signature:** `render(): string`  
Calls `candidates()` and `compute()` for each, wraps cards in a `<section class="pm-wrap">` with a header, grid, and disclaimer. Returns `""` when no candidates exist.

### window.Predictions Public API

```js
window.Predictions = { compute, explain, render }
```

Registers the "prediction" kind with `window.ScoreInfo` at load time (predictions.js:320):  
`ScoreInfo.register("prediction", (tk) => explain(tk))`

---

## scores.js

**File:** `webapp/js/scores.js`  
**Public API:** `window.TFScores`  
**Lines:** 1–211

### Purpose

The ThinkFree accountability scores engine. Calculates Influence Score, Government Dependency Score, and Corporate Political Exposure from browser-loaded public data with no extra network requests. Also provides sector-level rollup aggregation, a money formatter, and the `formula()` HTML expander that makes the scoring transparent to users. This is the calculation layer only; it never renders UI directly.

### window.* Data Consumed

| Global | Shape | Purpose |
|--------|-------|---------|
| `window.TF_DATA` | `{bills[], correlation.top_bills[], recent_trades[]}` | Bills and congressional trade disclosures |
| `window.IW_DATA` | `{companies: {...}}` | Board, executives, owners, LDA registrant id |
| `window.NP_DATA` | `{byName: {...}}` | Nonprofit financials (passed to influenceweb) |
| `window.SECBULK_DATA` | `{byTicker: {revenue}}` | Revenue for dependency score denominator |
| `window.USA_DATA` | `{byTicker: {total_contracts, total_contracts_fmt}}` | Federal contract dollars |
| `window.FEC_DATA` | `{byName: {...}}` | Campaign finance (referenced in formula text) |
| `window.RELATIONSHIPS` | `{byTicker: {firms[], spend_fmt, bills[], filings}}` | Senate LDA lobbying signals |
| `window.SEC_DATA` | `{byTicker: {board[]}}` | SEC board count |

### Index Structures (built once at load)

- `tradeCount[ticker]`: total number of STOCK Act trade disclosures
- `polsByTicker[ticker]`: `Set<string>` of member names who traded the ticker
- `billsByTicker[ticker]`: `Set<string>` of bill IDs that mention the ticker

### Functions

#### `moneyToNum(fmt)` — scores.js:31–37
**Signature:** `moneyToNum(fmt: string): number`  
Parses formatted money strings such as `"$9.8M"` → 9,800,000. Handles B/M/K suffixes. Returns 0 on parse failure.

#### `influenceScore(tk)` — scores.js:75–100
**Signature:** `influenceScore(tk: string): number`  
**Returns 0–100.** Capped-component sum formula:

| Component | Formula | Cap |
|-----------|---------|-----|
| Federal contracts | `(log10(contracts) − 5) × 8` | 38 |
| Lobby spend | `(log10(lobbySpend) − 4) × 4` | 16 |
| Lobby footprint | `firms × 1.3 + lobbyBills × 0.6` | 16 |
| Registered | `4 if registered else 0` | 4 |
| Bill mentions | `bills × 2` | 12 |
| Congressional trades | `trades × 0.3 + pols × 1.0` | 14 |
| Board size | `boardN × 0.3` | 4 |

Sum is clamped to [0, 100].

#### `dependencyScore(tk)` — scores.js:106–113
**Signature:** `dependencyScore(tk: string): number`  
**Returns 0–100.** `contracts / (5yr_revenue) × 140`, clamped at 100. When no revenue data: falls back to `log10(contracts) × 8`. Returns 0 when no contracts exist.

#### `label(v)` — scores.js:116–118
**Signature:** `label(v: number): "High" | "Medium" | "Low" | "Minimal"`  
Bucket: ≥ 70 → High, ≥ 40 → Medium, ≥ 15 → Low, < 15 → Minimal.

#### `politicalExposure(tk)` — scores.js:122–138
**Signature:** `politicalExposure(tk: string): PoliticalExposure`  
Returns the raw itemised signals: `{contracts, contracts_raw, bills, congressional_traders, trades, lobby_spend, lobby_firms, lobby_bills, lobbying, influence, dependency}`. Used by `scoreinfo.js`, `predictions.js`, and `influenceweb.js`.

#### `industryRollup(tickers)` — scores.js:143–167
**Signature:** `industryRollup(tickers: string[]): RollupResult`  
Aggregates across a list of tickers: total contracts (summed), unique bill set (union), total trades, average influence score, average dependency score. Returns `{companies, contracts, contracts_fmt, bills, trades, influence, dependency}`.

#### `money(n)` — scores.js:170–178
**Signature:** `money(n: number): string`  
Compact money formatter: T for trillions, B for billions, M for millions, K for thousands.

#### `formula(kind)` — scores.js:197–204
**Signature:** `formula(kind: "company" | "pol"): string`  
Returns an HTML `<details>` expander with the plain-English formula for the given score family. `FORMULAS.company` explains Influence Score + Government Dependency. `FORMULAS.pol` explains Influence, Public Impact, and Transparency scores. Ends with a note that all inputs come from public data and scores are transparency estimates, not accusations of wrongdoing.

### window.TFScores Public API

```js
window.TFScores = {
  influenceScore, dependencyScore, politicalExposure,
  industryRollup, label, money, formula,
  raw: { tradeCount, polsByTicker, billsByTicker },
}
```

---

## scoreinfo.js

**File:** `webapp/js/scoreinfo.js`  
**Public API:** `window.ScoreInfo`  
**Lines:** 1–302

### Purpose

Implements the progressive score-explanation system. Any HTML element with class `si` and `data-si-kind` / `data-si-key` (or `data-si-payload`) attributes becomes interactive:
- **Desktop**: hover shows a brief tooltip; click opens the full breakdown modal.
- **Mobile**: tap opens a bottom sheet with a "View Full Breakdown" button that promotes to the modal.

Built-in explainers for three political score kinds (`pol-influence`, `pol-public`, `pol-transparency`) and two company score kinds (`company-influence`, `company-dependency`) are registered at load time. Other modules (e.g. predictions.js) register additional kinds via `ScoreInfo.register()`. The modal calls `Glossary.annotate()` to wrap finance jargon in hover-definition spans when available.

### window.* Data Consumed

| Global | Purpose |
|--------|---------|
| `window.TF_DATA` | `politicians[]` — politician lookups |
| `window.FEC_DATA` | `{byName}` — funding breakdowns |
| `window.MEMBER_BILLS` | `{byBioguide}` — bill sponsorship counts |
| `window.TFScores` | Company score calculations (via `companyExp()`) |
| `window.PRICES_DATA` | Company name lookup for company explainers |
| `window.Glossary` | Optional jargon annotation in modal body |

### DOM Elements (lazily created)

- `tipEl` — `<div class="si-tip">` appended to `<body>`. Desktop hover tooltip.
- `sheetEl` — `<div class="si-sheet-wrap">` with background overlay and inner `<div class="si-sheet">`. Mobile bottom sheet.
- `modalEl` — `<div class="si-modal-wrap">` with `<div class="si-modal">`. Full breakdown modal.

### Explainer Object Shape

```js
{
  title: string,          // "Political Influence Score"
  value: string,          // "72/100"
  whyLabel?: string,      // Section heading (default "Why this score was assigned")
  bullets: string[],      // 3-4 key points for the tooltip/sheet
  why: string,            // Full plain-English explanation paragraph
  upside?: string[],      // Optional upside drivers list
  downside?: string[],    // Optional downside risks list
  inputs?: {label, value}[],  // Key model inputs table
  contributors?: {label, detail}[],  // Numbered contributor rows
  calc?: {formula, rows: {factor, value}[], total},  // Collapsible calculation
  sources?: {label, url?}[],  // Collapsible sources
  foot?: string,          // Disclaimer footer
  calcLabel?: string,     // "How was this calculated?" override
}
```

### Functions

#### `register(kind, fn)` — scoreinfo.js:25–26
**Signature:** `register(kind: string, fn: (key: string, val?: string) => ExplainerObj): void`  
Adds `fn` to the `REG` registry under `kind`. When a `.si` element with `data-si-kind=kind` is hovered/clicked, `fn(el.dataset.siKey, el.dataset.siVal)` is called to build the explainer.

#### `explainEl(el)` — scoreinfo.js:30–34
**Signature:** `explainEl(el: HTMLElement): ExplainerObj | null`  
Resolves an explainer from an `.si` element. Prefers inline `data-si-payload` JSON; falls back to the registered builder for `data-si-kind`.

#### `polFunding(name)` — scoreinfo.js:41–46
**Signature:** `polFunding(name: string): FundingBreakdown | null`  
Reads `FEC[name]` and computes individual/PAC/other percentages. Returns null when no data.

#### `pol(name)` — scoreinfo.js:50
**Signature:** `pol(name: string): PoliticianRecord | undefined`  
Finds a politician by exact name in `D.politicians`.

#### `polCommon(p)` — scoreinfo.js:53–56
**Signature:** `polCommon(p: PoliticianRecord): {f, pacShare, mb, trades, ret}`  
Extracts commonly needed fields for all three political score explainers in one call.

#### Built-in: `"pol-influence"` explainer — scoreinfo.js:61–96
Registered for `data-si-kind="pol-influence"`. Returns an explainer with:
- Formula: `30 base + trades × 0.3 + PAC share % × 0.6 + |return %| × 0.5 (capped 100)`
- Contributor rows: legislative activity, disclosed trades, outside funding exposure, trading performance
- Sources: Congress.gov (linked with bioguide), OpenFEC (linked), STOCK Act

#### Built-in: `"pol-public"` explainer — scoreinfo.js:100–120
Registered for `data-si-kind="pol-public"`. Returns an explainer with:
- Formula: `70 − PAC share % × 0.5 + individual share % × 0.2 (floor 10)`
- "Public impact rises when a member's funding leans toward individual donors rather than PACs."

#### Built-in: `"pol-transparency"` explainer — scoreinfo.js:124–143
Registered for `data-si-kind="pol-transparency"`. Returns an explainer with:
- Formula: `100 − PAC share % × 1.4 − trades × 0.15 (floor 5)`
- "It is a measure of exposure, not an accusation."

#### `companyExp(tk, which)` — scoreinfo.js:148–186
**Signature:** `companyExp(tk: string, which: "influence" | "dependency"): ExplainerObj | null`  
Delegates to `window.TFScores.politicalExposure(tk)` for raw signals. Builds the explainer for either:
- **influence**: aggregates contracts, lobbying spend/footprint, legislation, congressional trading, board size. Formula: the full capped-component sum.
- **dependency**: federal contracts ÷ ~5yr revenue × 140 (capped 100).

Registered as `"company-influence"` and `"company-dependency"` kinds (scoreinfo.js:189–190).

#### `build()` — scoreinfo.js:197–205
**Signature:** `build(): void`  
Lazily creates the three overlay DOM elements (tooltip, bottom sheet, modal) and attaches their close handlers. The sheet background click closes the sheet. Modal click on wrapper or × button closes the modal. Escape key closes both.

#### `bullets(b)` — scoreinfo.js:208
**Signature:** `bullets(b: string[]): string`  
Returns `<ul class="si-bullets">` with HTML-escaped `<li>` items.

#### `showTip(exp, x, y)` — scoreinfo.js:212–221
**Signature:** `showTip(exp: ExplainerObj, x: number, y: number): void`  
Calls `build()`, injects "Why this score?" + bullet list + "Click for full breakdown →" into `tipEl`. Positions it at `(x+16, y+16)` flipping horizontally/vertically when it would overflow the viewport. Adds class `open`.

#### `hideTip()` — scoreinfo.js:222
**Signature:** `hideTip(): void`  
Removes class `open` from `tipEl`.

#### `openSheet(exp)` — scoreinfo.js:226–236
**Signature:** `openSheet(exp: ExplainerObj): void`  
Mobile path. Injects the sheet content: drag grip, title, value, "Why this score?" + bullets, "View Full Breakdown" button. The button calls `closeSheet()` then `openModal(exp)`. Adds class `open`.

#### `closeSheet()` — scoreinfo.js:237
**Signature:** `closeSheet(): void`  
Removes class `open` from `sheetEl`.

#### `openModal(exp)` — scoreinfo.js:242–266
**Signature:** `openModal(exp: ExplainerObj): void`  
Renders the full breakdown modal. Calls `build()`, `hideTip()`, `closeSheet()`. Calls `window.Glossary.annotate()` on the `why` text and all driver/input strings when Glossary is loaded. Modal body sections (rendered in order):
1. Title + value
2. "Why this score?" section + `why` paragraph
3. Optional upside drivers `<ul>` (green)
4. Optional downside risks `<ul>` (red)
5. Optional key model inputs table
6. Numbered contributor rows
7. Collapsible `<details>` with formula + factor table
8. Collapsible `<details>` with source links
9. Disclaimer footer

#### `closeModal()` — scoreinfo.js:267
**Signature:** `closeModal(): void`  
Removes class `open` from `modalEl`.

#### `bindOnce()` — scoreinfo.js:271–288
**Signature:** `bindOnce(): void`  
Attaches delegated document-level listeners once (via `document._siBound` flag):
- Desktop: `mouseover`, `mousemove` (position tracking), `mouseout` → show/hide tooltip.
- All devices: `click` (capture phase) on `.si` → `openSheet()` (touch) or `openModal()` (mouse).

#### `badge(kind, key, value, opts)` — scoreinfo.js:294–298
**Signature:** `badge(kind: string, key: string, value: string|number, opts?: {payload?: object}): string`  
Returns a `<span class="si">` HTML string with the appropriate `data-si-*` attributes. When `opts.payload` is provided, the explanation is embedded inline as JSON in `data-si-payload`. Otherwise resolution happens lazily via the registered builder. The span includes an `&#9432;` info icon.

### window.ScoreInfo Public API

```js
window.ScoreInfo = { register, badge, openModal, openSheet, explainEl }
```

---

## glossary.js

**File:** `webapp/js/glossary.js`  
**Public API:** `window.Glossary`  
**Lines:** 1–95

### Purpose

Provides jargon-glossary hover tooltips throughout the ThinkFree UI. Detects known finance/quant terms in rendered HTML strings, wraps the first occurrence of each term in a `<span class="term">`, and shows a floating plain-English definition on hover or tap. Designed for non-expert users: definitions are written in everyday language, not formal finance terminology.

### Glossary Terms

All 16 terms (glossary.js:13–30):

| Term | Plain-English Definition |
|------|--------------------------|
| golden cross | "A sign the stock's price trend has recently turned upward..." |
| death cross | "A sign the stock's price trend has recently turned downward..." |
| rsi | "A 0-to-100 speed gauge. Near 70+ the price shot up fast; near 30- it dropped fast..." |
| oversold | "The price dropped fast and may be due for a bounce back up." |
| overbought | "The price ran up fast and may be due to cool off." |
| macd | "A momentum gauge. 'Bullish' means upward push is building..." |
| moving average | "The average price over recent weeks or months..." |
| volatility | "How much the price jumps around. Higher means bigger, less predictable swings..." |
| var | "A rough estimate of the worst loss to expect on a normal day (about 19 out of 20)." |
| sharpe ratio | "Whether the gains were worth the risk taken. Higher is better; above 1 is good." |
| kelly | "A math suggestion for how big a position could be... Shown for context only, not advice." |
| black-scholes | "A well-known finance formula, used here to estimate the chance of a price move." |
| bullish | "Leaning positive: the signs point toward the price possibly going up." |
| bearish | "Leaning negative: the signs point toward the price possibly going down." |
| drift | "The model's best guess at which way the price tends to lean over time." |
| beta | "How much a stock usually moves compared with the overall market." |

### Functions

#### `annotate(s)` — glossary.js:41–50
**Signature:** `annotate(s: string): string`  
Processes an already-HTML-escaped text string. Sorts all term keys longest-first to avoid partial matches (e.g. "moving average" before "average"). For each term, applies a word-boundary `RegExp` (case-insensitive) and replaces the **first** occurrence with `<span class="term" data-term="{key}">{match}</span>`. Subsequent occurrences are left unwrapped (the `used` map prevents double-wrapping). Returns the annotated string.

Side effect: none. Pure string transformation.

#### `ensure()` — glossary.js:57
**Signature:** `ensure(): void`  
Lazily creates the singleton `<div class="term-tip">` tooltip element and appends it to `<body>`.

#### `show(key, x, y)` — glossary.js:61–69
**Signature:** `show(key: string, x: number, y: number): void`  
Looks up `TERMS[key.toLowerCase()]`. Sets `tip.textContent` to the definition, adds class `open`, positions the tooltip at `(x+14, y+14)`, flipping sides if it would overflow the viewport.

#### `hide()` — glossary.js:72
**Signature:** `hide(): void`  
Removes class `open` from `tip`.

#### `bind()` — glossary.js:76–91
**Signature:** `bind(): void`  
Attaches delegated event listeners to `document` once (via `document._termBound` flag):
- `mouseover` → `show()` when cursor enters a `.term` span
- `mousemove` → follow cursor while inside `.term`; `hide()` otherwise
- `mouseout` → `hide()` when leaving a `.term` span (checks `relatedTarget` to avoid hiding on child elements)
- `click` → `show()` briefly for 3800ms then `hide()` (mobile tap support)

### window.Glossary Public API

```js
window.Glossary = { annotate, TERMS }
```

`annotate()` is called by `scoreinfo.js:openModal()` to annotate the `why` paragraph and driver lists with term spans before injecting them into the modal body.

---

*End of Part 6B — Frontend Reference: Feature Modules*
