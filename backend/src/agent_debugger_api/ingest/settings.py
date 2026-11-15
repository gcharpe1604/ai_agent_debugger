"""Durable-ingest settings and the one place that decides `project_id`.

Read from the environment or the repo-root `.env`; the defaults match
`.env.example` and compose. Kept apart from `config.Settings`, which requires
DATABASE_URL, so the ingest does not depend on PostgreSQL being configured.
"""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_debugger_api.config import PROJECT_ROOT

# Documented default (clickhouse-span-record.md §8.2). Until API keys exist
# (handoff action 6) every span belongs to this project, and the read API maps
# the frontend's `local` project to it.
DEFAULT_PROJECT_ID = UUID("00000000-0000-4000-8000-000000000001")


class IngestSettings(BaseSettings):
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_trace_topic: str = "agentdbg.traces.v1"
    # Upper bound for one publish call: producer start + every broker ack.
    kafka_publish_timeout_s: float = 10.0
    default_project_id: UUID = DEFAULT_PROJECT_ID

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_ingest_settings() -> IngestSettings:
    return IngestSettings()


def resolve_project_id() -> UUID:
    """The project a durable batch belongs to. Never taken from the client payload.

    Today: DEFAULT_PROJECT_ID (or its env override). Action 6 replaces this
    with the project of the authenticated API key.
    """
    return get_ingest_settings().default_project_id
