from app.cache_keys import product_key
from app.redis_client import redis_client


async def create(client, price=10.0):
    r = await client.post("/products", json={"name": "T", "price": price, "stock": 5})
    assert r.status_code == 201
    return r.json()["id"]


async def test_get_product_miss_then_hit(client):
    pid = await create(client)
    assert (await client.get(f"/products/{pid}")).json()["source"] == "db"
    assert (await client.get(f"/products/{pid}")).json()["source"] == "cache"


async def test_update_invalidates_product_and_lists(client):
    pid = await create(client, 10.0)
    await client.get(f"/products/{pid}")
    await client.get("/products?page=1&limit=5")

    r = await client.put(f"/products/{pid}", json={"price": 99.5})
    assert r.status_code == 200

    body = (await client.get(f"/products/{pid}")).json()
    assert body["source"] == "db" and body["data"]["price"] == 99.5
    assert (await client.get("/products?page=1&limit=5")).json()["source"] == "db"


async def test_create_invalidates_lists(client):
    await client.get("/products?page=1&limit=5")
    assert (await client.get("/products?page=1&limit=5")).json()["source"] == "cache"
    await create(client)
    assert (await client.get("/products?page=1&limit=5")).json()["source"] == "db"


async def test_delete_invalidates(client):
    pid = await create(client)
    await client.get(f"/products/{pid}")
    assert (await client.delete(f"/products/{pid}")).status_code == 204
    assert (await client.get(f"/products/{pid}")).status_code == 404


async def test_unknown_product_404_and_negative_cached(client):
    assert (await client.get("/products/987654")).status_code == 404
    assert (await client.get("/products/987654")).status_code == 404
    assert "__null__" in await redis_client.get(product_key(987654))