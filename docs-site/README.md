# docs-site

The Agent Debugger docs: an [Astro Starlight](https://starlight.astro.build) site served at `/docs/`.
Pages are MDX in `src/content/docs/`; the sidebar is in `astro.config.mjs`.

## Local development

```powershell
cd docs-site
npm.cmd ci
npm.cmd run dev      # http://localhost:4321/docs/
npm.cmd run build    # dist/docs/; fails on a broken internal link (starlight-links-validator)
```

`src/styles/theme.css` imports `../frontend/src/styles/tokens.css` and maps Starlight's
`--sl-*` variables to the app's tokens, so both share one palette and font set. Keep
`frontend/` next to `docs-site/` when building.

## Build output and serving

`base` is `/docs` and `outDir` is `dist/docs`, so `dist/` can be served as a site root:

- **VM (Caddy):** `frontend/Dockerfile` builds this site in its `docs` stage and copies
  `dist/docs` to `/srv/docs`; `deploy/Caddyfile` serves `/docs/*` before the SPA fallback.
- **Vercel:** deploy this folder as its own project (root `docs-site`, output `dist`;
  see `vercel.json`). The app project's `frontend/vercel.json` rewrites `/docs` and
  `/docs/:path*` to it. Replace `<DOCS_PROJECT_URL>` there with that project's URL, and
  keep "Include files outside the root directory" on (the theme reads `frontend/`).
