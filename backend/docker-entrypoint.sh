#!/bin/sh
# API container start: apply PostgreSQL migrations, then serve on 0.0.0.0:8008.
# The trace-writer container overrides this command and does not run migrations.
set -eu

cd /app
alembic -c alembic.ini upgrade head

# Only Caddy reaches this port (it is not published), so X-Forwarded-* from it is trusted.
exec uvicorn agent_debugger_api.main:app \
    --host 0.0.0.0 --port 8008 --workers 1 \
    --proxy-headers --forwarded-allow-ips '*'
