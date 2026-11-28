import asyncio
import sys
import time

import httpx

N, CONC = 3000, 30


async def main(label: str):
    lat: list[float] = []
    sem = asyncio.Semaphore(CONC)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=20) as c:
        await c.get("/health")

        async def run(i: int):
            async with sem:
                t = time.perf_counter()
                r = await c.get(f"/products/{1 + i % 7}")
                r.raise_for_status()
                lat.append((time.perf_counter() - t) * 1000)

        t0 = time.perf_counter()
        await asyncio.gather(*[run(i) for i in range(N)])
        total = time.perf_counter() - t0

    lat.sort()
    q = lambda p: lat[int(len(lat) * p) - 1]
    print(f"{label}: {N / total:.0f} req/s | p50={q(.5):.1f}ms p95={q(.95):.1f}ms p99={q(.99):.1f}ms")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "run"))