import asyncio
import random
import time

import httpx

n=200

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=20) as c:
        await c.get("/health")
        ids = [random.choice([1, 1, 1, 2, 2, 3, 4, 5, 6, 7]) for _ in range(n)]
        t = time.perf_counter()
        for i in range(0, len(ids), 30):  # 30 طلب متزامن في كل دفعة
            await asyncio.gather(*[c.get(f"/products/{p}") for p in ids[i : i + 30]])
        print(f"{n} requests in {time.perf_counter() - t:.2f}s")
        print((await c.get("/metrics")).json())


asyncio.run(main()) 