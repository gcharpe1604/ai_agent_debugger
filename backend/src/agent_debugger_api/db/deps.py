from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from agent_debugger_api.db.session import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """One AsyncSession per request. FastAPI caches it, so every dependency of a request shares it."""
    async with get_session_factory()() as session:
        yield session
