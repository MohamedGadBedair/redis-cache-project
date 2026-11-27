import sys
import time

import httpx

n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
with httpx.Client(base_url="http://localhost:8000", timeout=10) as c:
    for i in range(n):
        t = time.perf_counter()
        r = c.get("/products/1")
        print(i, r.status_code, r.json().get("source"), f"{time.perf_counter() - t:.3f}s")
        time.sleep(0.2)