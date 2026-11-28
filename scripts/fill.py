import asyncio
import os

import redis.asyncio as redis


async def main():
    r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await r.config_set("maxmemory", "20mb")  # حد صغير للتجربة بس
    payload = "x" * 1000
    for batch in range(50):
        pipe = r.pipeline()
        for i in range(1000):
            pipe.set(f"fill:{batch}:{i}", payload, ex=300)
        await pipe.execute()
    mem = await r.info("memory")
    stats = await r.info("stats")
    print("used:", mem["used_memory_human"], "| evicted:", stats["evicted_keys"], "| keys:", await r.dbsize())
    await r.config_set("maxmemory", "256mb")  # نرجّعه
    await r.aclose()


asyncio.run(main())