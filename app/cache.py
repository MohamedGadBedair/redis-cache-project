import asyncio
import json
import logging
import random
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal

import redis.exceptions as redis_exc

from app.cache_keys import product_key, product_list_pattern
from app.circuit_breaker import breaker
from app.config import settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

# أخطاء الاتصال بس هي اللي بتفتح الدايرة
CONNECTION_ERRORS = (
    redis_exc.ConnectionError,
    redis_exc.TimeoutError,
    OSError,
    TimeoutError,
)

NULL_MARKER = {"__null__": True}
ALL_KEYS_PATTERN = f"{settings.cache_prefix}:{settings.cache_version}:*"

_RELEASE_LOCK = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)

# true = فاتنا invalidation، لازم نمسح الكاش قبل ما نقرأ منه تاني
_dirty = False
_purge_lock = asyncio.Lock()


class CacheUnavailable(Exception):
    """Redis مش متاح (واقع أو بطيء أو الدايرة مفتوحة)."""


class CircuitOpen(CacheUnavailable):
    pass


async def _run(fn, *args, **kwargs):
    """كل أوامر Redis لازم تعدّي من هنا."""
    if not breaker.allow():
        raise CircuitOpen("circuit open")
    try:
        result = await fn(*args, **kwargs)
    except CONNECTION_ERRORS as e:
        breaker.record_failure()
        raise CacheUnavailable(str(e)) from e
    except redis_exc.RedisError as e:
        # Redis رد بخطأ منطقي: السيرفر شغال، مانفتحش الدايرة
        breaker.record_success()
        raise CacheUnavailable(str(e)) from e
    breaker.record_success()
    return result


def _log_failure(op: str, key: str, err: Exception) -> None:
    level = logging.DEBUG if isinstance(err, CircuitOpen) else logging.WARNING
    logger.log(level, "cache %s failed key=%s err=%s", op, key, err)


# ---------- Serialization ----------

def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (Decimal, uuid.UUID)):
        return str(obj)
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")


def serialize(value) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, separators=(",", ":"))


# ---------- Primitive operations ----------

async def _delete(key: str) -> None:
    await _run(redis_client.delete, key)


async def _scan_delete(pattern: str) -> None:
    async def work():
        keys = [k async for k in redis_client.scan_iter(match=pattern, count=100)]
        if keys:
            await redis_client.unlink(*keys)

    await _run(work)


async def _ensure_clean() -> bool:
    """True لو الكاش نضيف ومسموح نقرأ منه."""
    global _dirty
    if not _dirty:
        return True
    async with _purge_lock:
        if not _dirty:
            return True
        try:
            await _scan_delete(ALL_KEYS_PATTERN)
        except CacheUnavailable:
            return False
        _dirty = False
        logger.warning("cache purged after missed invalidation")
        return True


async def cache_get(key: str):
    if not await _ensure_clean():
        return None
    try:
        raw = await _run(redis_client.get, key)
    except CacheUnavailable as e:
        _log_failure("get", key, e)
        return None

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("corrupted cache value key=%s", key)
        await cache_delete(key)
        return None


async def cache_set(key: str, value, ttl: int, jitter: float | None = None) -> None:
    payload = serialize(value)  # bug برمجي هنا لازم يظهر مش يتبلع
    jitter = settings.cache_ttl_jitter if jitter is None else jitter
    final_ttl = ttl + random.randint(0, int(ttl * jitter))
    try:
        await _run(redis_client.set, key, payload, ex=final_ttl)
    except CacheUnavailable as e:
        _log_failure("set", key, e)


async def cache_delete(key: str) -> None:
    try:
        await _delete(key)
    except CacheUnavailable as e:
        _log_failure("delete", key, e)


async def invalidate_product(product_id: int | None = None) -> None:
    """امسح كاش المنتج وكل صفحات الليست. لو فشل نعلّم الكاش dirty."""
    global _dirty
    try:
        if product_id is not None:
            await _delete(product_key(product_id))
        await _scan_delete(product_list_pattern())
    except CacheUnavailable as e:
        _dirty = True
        logger.error("invalidate failed, cache marked dirty: %s", e)


# ---------- Cache-Aside with protection ----------

def _is_null(value) -> bool:
    return isinstance(value, dict) and value.get("__null__") is True


def _lock_key(key: str) -> str:
    return f"{settings.cache_prefix}:lock:{key}"


async def _release_lock(lock_key: str, token: str) -> None:
    try:
        await _run(redis_client.eval, _RELEASE_LOCK, 1, lock_key, token)
    except CacheUnavailable as e:
        _log_failure("unlock", lock_key, e)  # الـ lock له TTL فمش مشكلة


async def _load_and_store(key: str, ttl: int, loader, null_ttl: int):
    data = await loader()
    if data is None:
        await cache_set(key, NULL_MARKER, null_ttl, jitter=0)
    else:
        await cache_set(key, data, ttl)
    return data


async def get_or_set(
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable],
    null_ttl: int | None = None,
):
    """يرجّع (data, source). data = None معناها إن المورد مش موجود."""
    null_ttl = settings.ttl_not_found if null_ttl is None else null_ttl

    cached = await cache_get(key)
    if cached is not None:
        return (None if _is_null(cached) else cached), "cache"

    lock_key = _lock_key(key)
    token = uuid.uuid4().hex

    try:
        got_lock = await _run(
            redis_client.set, lock_key, token, nx=True, px=settings.cache_lock_ttl_ms
        )
    except CacheUnavailable as e:
        _log_failure("lock", key, e)
        return await _load_and_store(key, ttl, loader, null_ttl), "db"

    if got_lock:
        try:
            cached = await cache_get(key)  # double-check
            if cached is not None:
                return (None if _is_null(cached) else cached), "cache"
            return await _load_and_store(key, ttl, loader, null_ttl), "db"
        finally:
            await _release_lock(lock_key, token)

    # مش واخدين الـ lock: نستنى صاحبه، لكن لو Redis وقع نبطّل انتظار
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.cache_lock_wait_seconds
    while loop.time() < deadline and not breaker.is_open:
        await asyncio.sleep(settings.cache_lock_poll_seconds)
        cached = await cache_get(key)
        if cached is not None:
            return (None if _is_null(cached) else cached), "cache"

    return await _load_and_store(key, ttl, loader, null_ttl), "db"