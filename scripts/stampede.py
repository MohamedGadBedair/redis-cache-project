import asyncio
from collections import Counter
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10) as c:
        await c.get("/health")
        results = await asyncio.gather(*[c.get("/products/3") for _ in range(50)])
    print(Counter(r.json()["source"] for r in results))


asyncio.run(main())