# Landing page screenshots

The landing page (`#/`) shows real screenshots of the app from `frontend/public/landing/`, one file per theme (`<name>-light.webp`, `<name>-dark.webp`); `LandingPage.jsx` picks the one for the app's resolved theme. Each file is cropped at capture time and stored at 2× device scale, so its text stays sharp when the page scales it down. `SHOTS` in `LandingPage.jsx` holds each file's pixel size (the `width`/`height` attributes) and alt text: update both when a capture changes.

| File | What it shows | Viewport (CSS px) | Clip | File size (px, 2×) |
|---|---|---|---|---|
| `hero` | Trace view of a failed live run, its first error selected, Errors tab open | 1440×740 | x 240 → right edge (no app sidebar or account footer), top → just below the Error payload card (y 517), so there is no empty band under the 7 tree rows | 2400×1034 |
| `failed` | Tracing with `?outcome=Failed` | 1024×760 | Filters toolbar to the end of the table | 1568×1002 |
| `tree` | Tree and waterfall of the same live run | 1440×740 | Column header row to the last row, tree pane only | 1390×654 |
| `inspector` | Span inspector of the same run, Errors tab | 1440×740 | Inspector pane, top to the end of its content | 1008×1084 |
| `dashboard` | Dashboard, last 7 days | 1024×1400 | The four KPI tiles (12 px around them), then Latency by agent and Recent failures; the chart band is cut out | 1520×1494 |

Target: every image stays readable when shown about 560 px wide, so no clip is much wider than about 800 CSS px except the hero (shown at about 1100 px). Each WebP must stay under 250 KB; the 2026-11-26 set is 26–93 KB.

## Data (Demo account)

Register a local account named `Demo` with email `demo@example.com` (never a personal address) and a generated password. Keep its API key for the agents. On 2026-11-27 the account has 34 runs, 10 of them failed; the Dashboard shot was re-captured at 34 (the other shots are from 2026-11-26). The 2026-11-26 set had 26 runs, 9 failed:

- Live `ask` runs (they call the model configured in each agent's ignored `.env`, so durations are real and model calls are spans): tool_task_agent 4 (`Please fulfill order ORD-100` three times, worded differently; `Please fulfill order ORD-404 for 3 sensor kits` fails with `order_not_found`), rag_agent 4 (all answered or `insufficient_evidence`: no live RAG failure occurred), research_planning_agent 6 and langgraph_workflow_agent 7 (2 failures each, from provider HTTP 429/503). The later successful runs used the README prompts (field-station recommendations between Ridge and Vale; `Beacon has a stalled worker`, `Beacon host is unavailable; telemetry is delayed`) and small variations of them, run 40 s apart.
- 2026-11-27: 8 more live `ask` runs, 40 s apart: tool_task_agent 2 (`Please fulfill order ORD-100 for the warehouse`, `Fulfill order ORD-100, please`), research_planning_agent 3 (field-station prompts for 35, 20 and 28 people) and langgraph_workflow_agent 3 (`Beacon has a stalled worker` and two variations). Seven succeeded; the third research_planning run failed with `LiveOutputError` (invalid structured output after one repair) and is kept.
- Controlled runs, only for what live runs do not give reliably: TOOL-07 (recovered retry: it counts as completed) and failed TOOL-02, -03, -04, -05.

The hero, tree and inspector use the live run that failed on `ORD-404` (7 spans, 2.96 s). Re-seed with:

```powershell
$env:AGENT_DEBUGGER_ENDPOINT = 'http://127.0.0.1:8008/api/v1/traces'
$env:AGENT_DEBUGGER_API_KEY = '<demo key>'
uv run --directory examples/tool_task_agent --locked python -m tool_task_agent ask 'Please fulfill order ORD-404 for 3 sensor kits'
uv run --directory examples/tool_task_agent --locked python -m tool_task_agent run TOOL-07
```

Provider rate limits (HTTP 429) are common on back-to-back live runs; space them out. Never fake a duration or a failure. Do not delete stored runs to tidy the data without asking.

## Capture

1. Start the durable stack (`docs/local-development.md`, "Durable pipeline"): `docker compose up -d`, the backend on 8008, the trace writer, and `npm.cmd run dev` in `frontend/` (5175). Reuse running processes.
2. Sign in as Demo in a browser driven by Playwright. For each theme, open a new context with `deviceScaleFactor: 2`, the viewport from the table and `localStorage['agent-debugger.frontend.v1.theme']` set to `light` or `dark` before the page loads.
3. Before each capture, move the pointer to a corner and blur the focused element, so no hover or focus ring is in the image. Take each clip from the table with `page.screenshot({ clip })`, measuring the element boxes in the page rather than hard-coding them.
4. Convert to WebP at quality 80 with `sharp` (in `docs-site/node_modules`). For the Dashboard, extract the tiles band and the tables band from one capture and stack them, leaving out the "Traces over time" card.
5. Save to `frontend/public/landing/<name>-<theme>.webp` and look at each image on the built page at 1440 px: its text must be readable at the rendered size.
