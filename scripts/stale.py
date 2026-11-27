import subprocess
import time

import httpx


def docker(*args):
    subprocess.run(["docker", "compose", *args], check=True)


with httpx.Client(base_url="http://localhost:8000", timeout=20) as c:
    docker("start", "redis")

    # نتأكد إن المنتج اتخزن في الكاش فعلاً (الدايرة ممكن تكون لسه مقفولة)
    for _ in range(20):
        if c.get("/products/1").json()["source"] == "cache":
            break
        time.sleep(1)
    else:
        raise SystemExit("couldn't get product into cache")
    print("before:", c.get("/products/1").json())

    docker("stop", "redis")
    new_price = float(int(time.time()) % 1000 + 1)
    r = c.put("/products/1", json={"price": new_price})
    print("PUT:", r.status_code, r.json())

    docker("start", "redis")
    time.sleep(11)  # نستنى الدايرة تدي فرصة للـ probe

    after = c.get("/products/1").json()
    print("after:", after)
    assert after["data"]["price"] == new_price, "STALE CACHE!"
    print("OK: no stale data")