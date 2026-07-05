import asyncio

async def retry(coro, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return await coro()
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
