# Landing page screenshots

The landing page (`#/`) shows real screenshots of the app, one per theme, from `frontend/public/landing/`. `LandingPage.jsx` picks the file for the app's resolved theme (`<name>-light.webp` or `<name>-dark.webp`) and shows parts of `trace` and `tracing-failed` through a CSS crop, so a new capture must keep the same 1440×900 layout. If the layout of the trace view or Tracing changes, check the `crop` values in `LandingPage.jsx`.

| File | Page | State |
|---|---|---|
| `trace-<theme>.webp` | Trace view of a failed `tool-task-agent` run (TOOL-05) | First failed span (Pay · attempt 1) selected, Errors tab open |
| `tracing-failed-<theme>.webp` | Tracing, `?outcome=Failed` | Four failed runs |
| `dashboard-<theme>.webp` | Dashboard | Last 7 days |

Each file must stay under 250 KB (the 2026-11-26 capture is 28–51 KB).

## Steps

1. Start the durable stack (`docs/local-development.md`, "Durable pipeline"): `docker compose up -d`, the backend on port 8008, the trace writer, and `npm.cmd run dev` in `frontend/` (port 5175). Reuse processes that are already running.
2. Register a demo account through the UI or `POST /api/v1/auth/register` with name `Demo` and email `demo@example.com` (never a personal address) and a generated password. Keep the API key it returns for step 3. In a database that already has users, the account gets its own project, so other runs do not appear in the screenshots.
3. Seed controlled runs with the demo key (no model calls):

   ```powershell
   $env:AGENT_DEBUGGER_ENDPOINT = 'http://127.0.0.1:8008/api/v1/traces'
   $env:AGENT_DEBUGGER_API_KEY = '<demo key>'
   uv run --directory examples/tool_task_agent --locked python -m tool_task_agent run TOOL-01
   ```

   The 2026-11-26 set (14 runs): TOOL-01, -02, -03, -04, -05, -07 (TOOL-07 is the recovered retry: it counts as completed), RAG-01, -04, -05, RP-01, -03, LG-01, -03, -05. Four runs end Failed (TOOL-02, -03, -04, -05).
4. In a browser at a 1440×900 viewport, sign in as Demo. For each theme, set `localStorage['agent-debugger.frontend.v1.theme']` to `light` or `dark` and reload, then capture the viewport (not the full page) of:
   - `#/projects/default/runs/<TOOL-05 trace id>`: the failed span is selected on open; click the Errors tab.
   - `#/projects/default/runs?outcome=Failed`
   - `#/projects/default`

   Before each capture, move the pointer to the bottom-right corner and blur the focused element, so no hover or focus ring is in the image.
5. Convert each PNG to WebP at quality 82, for example with `sharp` from `docs-site/node_modules`: `sharp(png).webp({ quality: 82, effort: 6 }).toFile(webp)`. Save to `frontend/public/landing/<name>-<theme>.webp`.
6. Update the alt text in `LandingPage.jsx` if what the screenshot shows changed (counts, span names, error type).
