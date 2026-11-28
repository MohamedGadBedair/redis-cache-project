from collections import Counter

KNOWN = {
    "cache_hit", "cache_miss", "cache_bypass", "negative_hit",
    "db_load", "lock_acquired", "lock_waited", "lock_wait_timeout",
    "coalesced", "local_coalesced",
    "redis_error", "circuit_rejected", "breaker_opened",
    "invalidation_ok", "invalidation_failed", "dirty_purge",
}

_counters: Counter[str] = Counter()


def incr(name: str, n: int = 1) -> None:
    if name not in KNOWN:
        raise KeyError(f"unknown metric: {name}")
    _counters[name] += n

def reset()-> None:
    _counters.clear()

def snapshot() -> dict:
    hits = _counters["cache_hit"]
    misses = _counters["cache_miss"]
    bypass = _counters["cache_bypass"]
    total = hits + misses
    healthy = max(total - bypass, 0)
    return {
        "counters": dict(_counters),
        "hit_ratio": round(hits / total, 4) if total else None,
        "hit_ratio_when_redis_up": round(hits / healthy, 4) if healthy else None,
        "bypass_ratio": round(bypass / total, 4) if total else None,
    }