import asyncio


def run_async(coro):
    """
    Run a coroutine from a Celery task.

    Each call uses a fresh event loop (asyncio.run), but the SQLAlchemy engine
    is module-global: pooled asyncpg connections stay bound to the loop that
    opened them, so the next task in the same worker process fails with
    "Event loop is closed". Disposing the pool before the loop ends avoids it.
    """
    async def _wrapped():
        from app.core.database import engine
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())
