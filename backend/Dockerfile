# Backend image: the API (default command) and the trace writer
# (command: python -m agent_debugger_api.trace_writer). Build context: backend/.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so a source change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --locked --no-dev --no-editable \
    && rm -rf src

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

USER app
EXPOSE 8008

CMD ["/usr/local/bin/docker-entrypoint.sh"]
