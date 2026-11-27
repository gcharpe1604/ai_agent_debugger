# Landing page — Direction C implementation spec

Source of truth for layout: the canvas frames "C · Spec sheet" (desktop 1440, mobile 375, light and dark).
Source of truth for copy in code blocks: `frontend/src/features/public/site.js` (`SDK_INSTALL`, `envSnippet`, `traceSessionSnippet`). Render from those constants; do not paste copies into JSX.

Scope: `src/features/public` only. Plain CSS with custom properties, no new dependencies.

---

## 1. Tokens

Scope every token to `.public-site` so the app workspace is unaffected. The theme follows the existing app switch: `[data-theme="dark"]`, and `prefers-color-scheme: dark` when no theme has been chosen.

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `--lp-bg` | `#ffffff` | `#0e0e0f` | page |
| `--lp-surface-alt` | `#fafafa` | `#131315` | screenshot wells, figure caption bar, code background |
| `--lp-text` | `#18181b` | `#f4f4f5` | headings, primary text |
| `--lp-text-2` | `#3f3f46` | `#d4d4d8` | body copy, footer links |
| `--lp-muted` | `#71717a` | `#a1a1aa` | lede, section labels, code comments |
| `--lp-faint` | `#a1a1aa` | `#71717a` | line numbers and the `$` prompt only (decorative, `aria-hidden`; fails 4.5:1, so never use it for text) |
| `--lp-border` | `#e4e4e7` | `#27272a` | rules, row dividers, tab separators |
| `--lp-border-strong` | `#d4d4d8` | `#3f3f46` | framed objects: figure, code card, architecture nodes, secondary button |
| `--lp-accent` | `#18181b` | `#fafafa` | primary button background |
| `--lp-on-accent` | `#fafafa` | `#18181b` | primary button text |
| `--lp-type-agent` | `#6d28d9` | `#a78bfa` | type chip, code keywords |
| `--lp-type-model` | `#1d4ed8` | `#7da6ff` | type chip |
| `--lp-type-tool` | `#b45309` | `#f5a524` | type chip |
| `--lp-type-retrieval` | `#0f766e` | `#2dd4bf` | type chip |
| `--lp-error` | `#b42318` | `#f97066` | "● failed" in the figure caption |
| `--lp-success` | `#116549` | `#47cd89` | recovered-retry ↻ glyph |
| `--lp-code-string` | `#067d17` | `#7dd3a8` | strings and `.env` values |

Notes:
- The light values match the app's zinc scale and `--type-*` / `--color-danger` / `--color-success` / `--json-string`. Where the app already defines a token with the same value, alias it (`--lp-type-agent: var(--type-agent)`) instead of repeating the hex.
- The dark type colours and dark error/success are lighter variants I chose for contrast on `#0e0e0f`. If the app's dark theme already defines its own type colours, use those.
- The code keyword colour is `--lp-type-agent` in both themes, and `.env` keys use it too.

### Type

Families: `--lp-font-sans: "Inter Variable", Inter, system-ui, sans-serif` and `--lp-font-mono: "JetBrains Mono", ui-monospace, Consolas, monospace` (the app's `--font-sans`/`--font-mono`).

| Token | Desktop | Mobile (<768) | Weight / tracking | Use |
|---|---|---|---|---|
| `--lp-display` | 76px / 78px | 40px / 44px | 600 / -0.04em | hero h1 (max-width 1040px) |
| `--lp-cta` | 88px / 1.05 | 44px / 1.05 | 600 / -0.04em | final CTA heading |
| `--lp-h2` | 40px / 46px | 28px / 34px | 600 / -0.025em | Quickstart, Architecture headings |
| `--lp-h3` | 32px / 1.2 | 26px / 1.2 | 600 / -0.02em | feature headings (these are `<h2>` in the markup) |
| `--lp-lede` | 19px / 1.5 | 17px / 1.5 | 400 | hero subhead (max-width 560px) |
| `--lp-body` | 16px / 1.5 | same | 400 | feature body |
| `--lp-body-sm` | 15px / 1.5 | same | 400 | step body, buttons |
| `--lp-ui` | 14px | same | 400–500 | nav links, fact rows, footer links, PostgreSQL detail |
| `--lp-label` | 12px mono | same | uppercase / 0.06em | section labels (`01 · QUICKSTART`), footer column titles |
| `--lp-code` | 13px / 22px mono | 12px / 22px | 400 | code blocks, install line |
| `--lp-meta` | 11–12px mono | same | 400 | architecture labels and connectors (11px), figure caption, tabs (12px) |

### Spacing (4px grid), radius, size

```
--lp-space-1: 4px;  --lp-space-2: 8px;  --lp-space-3: 12px; --lp-space-4: 16px;
--lp-space-6: 24px; --lp-space-8: 32px; --lp-space-10: 40px; --lp-space-14: 56px;
--lp-space-16: 64px; --lp-space-18: 72px; --lp-space-24: 96px; --lp-space-28: 112px;

--lp-container: 1280px;        /* includes gutters → 1200px content */
--lp-gutter: 40px;             /* 16px below 768 */
--lp-label-col: 160px;         /* section label column, ≥1024 */
--lp-nav-h: 56px;
--lp-radius-control: 6px;      /* buttons, tabs row, chips, images inside wells */
--lp-radius-frame: 8px;        /* figure, code card, image wells, architecture API group */
--lp-btn-h: 44px;              /* hero and CTA buttons; nav buttons 32px; mobile menu button 44×44 */
```

---

## 2. Page grid

- Container: `max-width: var(--lp-container); margin-inline: auto; padding-inline: var(--lp-gutter)`.
- Section row (≥1024): `display: grid; grid-template-columns: var(--lp-label-col) minmax(0, 1fr)`.
  - Label cell: padding `64px 16px 64px 0`, `border-right: 1px solid var(--lp-border)`.
  - Body cell: padding `64px 0 72px 40px`.
- Every section ends with `border-bottom: 1px solid var(--lp-border)` across the full width. The label column's vertical rule joins up across sections.
- Hero and final CTA do not use the label column; they span the full container.

## 3. Sections, top to bottom

| # | Section | Layout (desktop) | Key values |
|---|---|---|---|
| 0 | Nav | grid `160px 1fr auto`, height 56, bottom rule | Mono wordmark 14/500 with an 18px framed ▸ mark. Links Docs `/docs/`, GitHub, gap 24. Right side: theme toggle (32px, bordered, glyph + mono label "light"/"dark"), Sign in (text), Sign up (primary, 32px). |
| 1 | Hero | padding `96px 40px 64px` | h1 `--lp-display`. Under it, a 2-column grid (`1fr auto`, align end, gap 24): lede on the left; Sign up + Read the quickstart on the right, 44px tall, gap 10. Figure 56px below: `border: 1px solid --lp-border-strong`, radius 8. It has a 36px mono caption bar on `--lp-surface-alt` (`● failed · tool-task-agent · trace 877fc441…e8ce · 7 spans · 2 errors`, gap 16), then `hero-{theme}.webp` at full width. |
| 2 | 01 · Quickstart | body: h2, then a grid `4fr 7fr`, gap 32, 32px below | Left: three steps as an `<ol>` with top and bottom rules, rows `40px 1fr`, padding 16 0. Right: the code card (§4). |
| 3–6 | 02 Runs · 03 Trace · 04 Inspector · 05 Dashboard | body grid `4fr 7fr`, gap 40, align start | Text side: h3; body (margin 12); optional type chips (Trace only: 24px tall, radius 6, an 8px swatch plus a mono label, gap 8); fact list with rules (`key` mono + value, 14px, padding 10 0). Image well: radius 8, `--lp-surface-alt`, `border: 1px solid --lp-border`. Runs: no padding, image flush. Trace: padding 24. Inspector: padding 32, image max 480px. Dashboard: padding 32, image max 560px. Images inside a padded well get a 1px border and radius 6. |
| 7 | 06 · Architecture | h2, then a schematic 32px below, then three notes | See §3.1. The schematic shows how spans actually move: two lanes into one ClickHouse, PostgreSQL beside the API. No numbers or timings. Markup: `Architecture.jsx`, lanes as `<ol aria-label="Write path" / "Read path" / "Accounts">`. |
| 8 | Final CTA | padding `112px 40px` | "Trace your first run." `--lp-cta`. Buttons 32px below. Install box 24px below the buttons: max-width 880, radius 8, `--lp-surface-alt`, padding `12px 8px 12px 16px`, then `$` + wrapped command + 32px copy button. |
| 9 | Footer | same row grid (160 + 1fr) | Label cell: wordmark + "© 2026", padding `48px 16px 48px 0`. Body: 3 columns (Product / Docs / Resources), padding `48px 0 48px 40px`, gap 24. Titles use `--lp-label`; links 14px `--lp-text-2`, gap 8. |

### 3.1 Section 06 · Architecture schematic

Facts it encodes (checked against the backend, 2026-11-27): ingest and read are one FastAPI app; the Web UI never reads ClickHouse, the Read API does; the session is a signed cookie holding only `user_id`, so PostgreSQL stores no sessions; PostgreSQL has one `users` table (accounts and API key hashes), read on every ingest (key hash) and every UI read (session `user_id`).

| Lane | Nodes and connectors (connector labels in mono) |
|---|---|
| `write` | **Agent + SDK** `TraceSession` → `HTTPS · Bearer API key` → **Ingest API** `/api/v1/traces` → `publish` → **Kafka** `agentdbg.traces.v1` → `consume` → **Trace writer** `Kafka consumer` → `insert` → **ClickHouse** `telemetry_spans` |
| `read` | **Web UI** `React` → `session cookie` → **Read API** `/api/v1/projects/…` → `SQL` → the same **ClickHouse** node |
| `side` | **PostgreSQL**, "Accounts and API key hashes. Spans never go here.", hung below the API by `user lookup: key hash, session user_id` |

Style (tokens only, as the rest of the page):
- Node: 1px `--lp-border-strong`, radius 6, padding 12, `--lp-bg`; name 15/600 sans; detail mono 11 `--lp-muted`, with a break opportunity after `/`, `.` and `_`. ClickHouse uses `--lp-surface-alt`. PostgreSQL and the stacked "same as above" references use a dashed border.
- Connector: label mono 11 `--lp-muted`; a 1px `--lp-muted` line with a 6×7px arrowhead. Desktop: the label sits above a horizontal line at the node's mid-height; next to the API group the label is inset 14px so it clears the dashed border.
- API group: a dashed `--lp-border-strong` frame, radius 8, 10px outside the Ingest API and Read API boxes, captioned `one FastAPI app` (mono 11) on its top edge.
- Lane names `write`, `read`, `side`: mono 11, uppercase, 0.06em, `--lp-muted`.

Layout ≥1280: one CSS grid, columns `48px repeat(4, minmax(0,1.25fr) minmax(0,1.2fr)) minmax(0,1.25fr)` (lane name, then node / connector alternating), rows `auto 40px auto 64px auto` (write, gap, read, PostgreSQL connector, PostgreSQL). ClickHouse spans rows 1–3, so both lanes' arrows end on the one box; the read lane's `SQL` connector spans columns 5–9. The PostgreSQL connector runs down from the API group's bottom edge (label to its right); PostgreSQL spans the Ingest API column and the next two.

Below 1280 (narrower, the boxes are too small): the lanes stack, `write` then `read` then `side`, 24px apart. Each node is full width; each connector is a 40px vertical line with a down arrow, 24px in, its label to the right. The read lane ends in a dashed **ClickHouse** "the same node as above"; the side lane starts with a dashed **Ingest API + Read API** "the same app as above". The API group frame is not drawn.

Notes (margin 32, the fact-list style: mono term 88px, then text):
- **Kafka**: The agent never waits on ClickHouse; a writer restart loses nothing.
- **ClickHouse**: Column store for time-range scans of spans.
- **PostgreSQL**: Accounts only.

Link targets (all exist in `site.js` `DOCS`): Quickstart `get-started/quickstart/`, TraceSession `sdk/trace-session/`, Errors and retries `concepts/errors-and-retries/`, Ingest API `api/ingest/`, Dashboard `product/dashboard/`, Self-hosting `self-hosting/docker-compose/`, Limits `limits/`. Use `DOCS.*` and `REPO_URL`; don't hard-code paths.

## 4. Code card and install line

- Card: border `--lp-border-strong`, radius 8, overflow hidden, background `--lp-surface-alt`.
- Tabs: a `role="tablist"` row on `--lp-bg`, each tab 40px tall, padding 0 16, mono 12, with a right border. The active tab gets the card background and `--lp-text`; the others are `--lp-muted`. Order: `terminal` → `.env` → `agent.py`, and `terminal` is the default. Use arrow-key roving focus, as in the app's existing tabs.
  - terminal: `SDK_INSTALL`
  - .env: `envSnippet()` (the live origin; the design shows `https://<your-host>`)
  - agent.py: `traceSessionSnippet`
- Lines: padding 16 0, each line `display: flex`: a line-number cell (40px wide, 32px on mobile, right-aligned, padding-right 12, `--lp-faint`, `aria-hidden`) plus a text cell `flex: 1; min-width: 0; white-space: pre-wrap; overflow-wrap: anywhere`.
- **No horizontal scroll anywhere.** Don't put `overflow-x: auto` on any code block. Long lines wrap inside the text cell, and the line number stays on the first visual line.
- Install command wrapping: render `SDK_INSTALL` with a `<wbr>` after every `/`, `#` and `=`, so it breaks at path boundaries (`…github.com/ ⏎ gcharpe1604/ai_agent_debugger.git# ⏎ subdirectory=sdk/python"`). Copy buttons copy the raw constant, never the rendered text.
- Highlighting (simple, no library): `#…` comments → muted; `"…"` strings → `--lp-code-string`; keywords `from import with as class def return lambda pip install` → `--lp-type-agent`. For `.env`: key → agent colour, `=` → muted, value → string colour.

## 5. Breakpoints

| Range | Behaviour |
|---|---|
| ≥1024 | As designed at 1440. Content width is capped at 1200px. |
| 768–1023 (not drawn; inferred) | Keep the 160px label column. Quickstart and feature inner grids stack to one column (text, then image/code). The architecture schematic stacks (§3.1). Hero CTAs drop below the lede. |
| <768 (drawn at 375) | Gutter 16. Section row becomes one column: label above body, no vertical rule; label padding `40px 0 0`, body padding `16px 0 56px`. Hero padding `48px 16px 32px`; the figure caption shows only `● failed · tool-task-agent`; the hero image is cropped to 260px tall, `object-fit: cover; object-position: left top`. Nav: wordmark, theme toggle (glyph only), Sign up, 44×44 menu button (Docs, GitHub and Sign in go into the menu). The architecture lanes stack vertically (§3.1). Footer: label cell, then a 2-column link grid. Code 12px. |

No element may exceed the viewport width at 375. Check with `document.documentElement.scrollWidth === innerWidth`.

## 6. Images

`frontend/public/landing/{hero,failed,tree,inspector,dashboard}-{light,dark}.webp`. Pick the image by theme (one `<img>` whose `src` changes on theme change, or `<picture>` with `prefers-color-scheme` plus the explicit theme attribute). Set `width`/`height` attributes to avoid layout shift: hero 2400×1034, failed 1568×1002, tree 1390×654, inspector 1008×1084, dashboard 1498×1492. The dashboard images will be re-captured with live data, so re-check that size afterwards.

## 7. Accessibility

- One `<h1>`. Section headings are `<h2>`; section labels are `<p>`, not headings.
- Every screenshot has descriptive `alt` text (see the frames). Decorative SVGs get `aria-hidden="true"`.
- The theme toggle and menu button have an `aria-label`. Hit targets are at least 44px on mobile.
- Colour is never the only signal: "● failed" has text, type chips have labels, and the recovered-retry row has a glyph and text.

## 8. Acceptance

1. Frames match the canvas C at 1440 and 375 in both themes (spacing within ±4px).
2. No horizontal scrollbar on any code block or on the page at 375, 768, 1024 and 1440.
3. All three tabs render from `site.js` constants; copy buttons copy the exact constant.
4. `npm.cmd test`, `npm.cmd run lint` and `npm.cmd run build` pass; the existing `Public.test.jsx` is updated for the new sections.
