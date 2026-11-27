import asyncio

import redis.exceptions
from app import cache as cache_module
from app.cache import cache_get, get_or_set, invalidate_product
from app.cache_keys import product_key
from app.circuit_breaker import breaker
from app.redis_client import redis_client


def counting_loader(value, delay=0.0):
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        if delay:
            await asyncio.sleep(delay)
        return value

    return loader, calls


class DeadRedis:
    """بديل لـ Redis بيرمي ConnectionError على أي أمر."""

    def __init__(self):
        self.calls = 0

    def __getattr__(self, name):
        async def fail(*a, **k):
            self.calls += 1
            raise redis.exceptions.ConnectionError("down")

        return fail

    def scan_iter(self, *a, **k):
        self.calls += 1

        async def gen():
            raise redis.exceptions.ConnectionError("down")
            yield  # noqa

        return gen()


async def test_miss_then_hit():
    loader, calls = counting_loader({"v": 1})
    d1, s1 = await get_or_set("t:k1", 60, loader)
    d2, s2 = await get_or_set("t:k1", 60, loader)
    assert (s1, s2) == ("db", "cache")
    assert d1 == d2 == {"v": 1}
    assert calls["n"] == 1


async def test_not_found_is_cached():
    loader, calls = counting_loader(None)
    d1, _ = await get_or_set("t:missing", 60, loader)
    d2, s2 = await get_or_set("t:missing", 60, loader)
    assert d1 is None and d2 is None
    assert s2 == "cache"
    assert calls["n"] == 1


async def test_ttl_jitter_spreads_expiry():
    loader, _ = counting_loader({"v": 1})
    for i in range(20):
        await get_or_set(f"t:j{i}", 100, loader)
    ttls = [await redis_client.ttl(f"t:j{i}") for i in range(20)]
    assert all(95 <= t <= 110 for t in ttls)
    assert len(set(ttls)) > 1


async def test_stampede_hits_db_once():
    loader, calls = counting_loader({"v": 1}, delay=0.2)
    results = await asyncio.gather(*[get_or_set("t:hot", 60, loader) for _ in range(50)])
    assert calls["n"] == 1
    assert all(data == {"v": 1} for data, _ in results)


async def test_corrupted_value_is_treated_as_miss():
    await redis_client.set("t:bad", "not-json{")
    loader, calls = counting_loader({"v": 1})
    data, source = await get_or_set("t:bad", 60, loader)
    assert source == "db" and data == {"v": 1}
    assert calls["n"] == 1


async def test_redis_down_falls_back_and_opens_breaker(monkeypatch):
    dead = DeadRedis()
    monkeypatch.setattr(cache_module, "redis_client", dead)

    loader, calls = counting_loader({"v": 1})
    data, source = await get_or_set("t:k", 60, loader)
    assert (data, source) == ({"v": 1}, "db")   # الطلب ما فشلش
    assert breaker.is_open

    before = dead.calls
    await get_or_set("t:k", 60, loader)
    assert dead.calls == before                  # الدايرة مفتوحة: مفيش اتصال بـ Redis


async def test_breaker_recovers(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(cache_module, "redis_client", DeadRedis())
        await get_or_set("t:k", 60, counting_loader({"v": 1})[0])
    assert breaker.is_open

    monkeypatch.setattr(breaker, "reset_timeout", 0)  # نسمح بالـ probe فوراً
    await get_or_set("t:k", 60, counting_loader({"v": 1})[0])
    assert not breaker.is_open


async def test_missed_invalidation_purges_stale_cache(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(cache_module, "redis_client", DeadRedis())
        await invalidate_product(1)
    assert cache_module._dirty is True

    # Redis رجع، وفيه قيمة قديمة
    await redis_client.set(product_key(1), '{"stale":1}')
    breaker._failures = 0
    breaker._opened_at = None

    assert await cache_get(product_key(1)) is None   # اتمسح قبل القراءة
    assert cache_module._dirty is False