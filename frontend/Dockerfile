# UI image: the built frontend served by Caddy, which also proxies /api to the API.
# Build context: the repo root (needs frontend/ and deploy/Caddyfile):
#   docker build -f frontend/Dockerfile .
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv
