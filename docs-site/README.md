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
- **Vercel:** one project, the frontend's (root `frontend/`). Its build command,
  `node ../scripts/build-vercel.mjs`, builds the app, then this site, and copies
  `dist/docs` into `frontend/dist/docs` (and the docs 404 page to `frontend/dist/404.html`).
  `frontend/vercel.json` redirects `/docs` to `/docs/` and keeps its SPA fallback off
  `/docs`, so a missing docs page gets the docs 404. The project needs "Include files
  outside the root directory" on, because the build reads `../docs-site` and `../scripts`.
