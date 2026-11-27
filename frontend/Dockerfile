# UI image: the built frontend and docs served by Caddy, which also proxies /api to the API.
# Build context: the repo root (needs frontend/, docs-site/ and deploy/Caddyfile):
#   docker build -f frontend/Dockerfile .
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Docs (Astro Starlight). Its theme imports frontend/src/styles/tokens.css, so the
# stage keeps the repo layout: /repo/docs-site next to /repo/frontend.
FROM node:22-alpine AS docs
WORKDIR /repo/docs-site
COPY docs-site/package.json docs-site/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/src/styles/tokens.css /repo/frontend/src/styles/tokens.css
COPY docs-site/ ./
RUN npm run build

FROM caddy:2
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv
# The docs build writes dist/docs/ (base /docs), served at /docs/.
COPY --from=docs /repo/docs-site/dist/docs /srv/docs
