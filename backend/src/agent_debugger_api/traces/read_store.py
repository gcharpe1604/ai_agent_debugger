"""The trace store the durable read API uses: ClickHouse, connected on first use.

The app must start without ClickHouse (like it starts without Kafka), so the
client is created by the first read, not at import. A failed read drops the
client; the next request connects again.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import clickhouse_connect
from clickhouse_connect.driver.exceptions import ClickHouseError

from agent_debugger_api.contracts import TraceStore
from agent_debugger_api.trace_writer.clickhouse_store import ClickHouseTraceStore
from agent_debugger_api.trace_writer.schema import TABLE
from agent_debugger_api.trace_writer.settings import WriterSettings

logger = logging.getLogger(__name__)


class TraceStoreUnavailable(Exception):
    """The store could not answer. The route turns this into 503, never into empty data."""


def read_client(settings: WriterSettings):
    """A ClickHouse client that request threads can share."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        connect_timeout=3,
        # One client serves every request thread. ClickHouse refuses concurrent
        # queries inside one session, so the client must not open one.
        autogenerate_session_id=False,
    )


def clickhouse_store_from_settings() -> ClickHouseTraceStore:
    """Same connection settings as the trace-writer (`CLICKHOUSE_*` in the root `.env`)."""
    settings = WriterSettings()
    return ClickHouseTraceStore(read_client(settings), table=f"{settings.clickhouse_database}.{TABLE}")


class LazyReadStore:
    """Read half of `TraceStore`. Synchronous: call it through `run_in_threadpool`."""

    def __init__(self, factory: Callable[[], TraceStore] = clickhouse_store_from_settings) -> None:
        self._factory = factory
        self._store: TraceStore | None = None
        self._lock = threading.Lock()

    def _call(self, method: str, *args, **kwargs):
        try:
            with self._lock:
                if self._store is None:
                    self._store = self._factory()
                store = self._store
            return getattr(store, method)(*args, **kwargs)
        except (ClickHouseError, OSError) as exc:
            # Type only: a driver message can contain the query or the server address.
            logger.warning("trace store read failed: %s", type(exc).__name__)
            with self._lock:
                self._store = None
            raise TraceStoreUnavailable(method) from exc

    def get_trace(self, project_id, trace_id):
        return self._call("get_trace", project_id, trace_id)

    def list_runs(self, project_id, started_from, started_to, limit=50, before=None):
        return self._call("list_runs", project_id, started_from, started_to, limit, before)
