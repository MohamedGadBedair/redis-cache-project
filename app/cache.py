import json
import logging
from collections.abc import Awaitable, Callable

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import redis.exceptions as redis_exc
REDIS_ERRORS = (redis_exc.RedisError, OSError, TimeoutError)

from app.redis_clinent import redis_client
from app.cach_keys import product_key, product_list_pattern


logger = logging.getLogger(__name__)

# =======================================================================
def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")


def serialize(value) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, separators=(",", ":"))
# ========================================================================
# get value from cache
async def cache_get(key:str):
    """يرجّع القيمة أو None لو miss أو لو Redis فيه مشكلة."""
    try :
        raw = await redis_client.get(key)
    except REDIS_ERRORS as e :
        logger.warning(f'cache_get failed key={key} err={e}')
        return None
    
    if raw is None:
        return None
    
    try :
        return json.loads(raw)
    except json.JSONDecodeError:
        logging.error(f'corrupted cache value key={key}')
        await cache_delete(key)
        return None
# set value in cache
async def cache_set(key:str,value, ttl:int)->None:
    payload = serialize(value)
    try :
        await redis_client.set(name=key,value=payload,ex=ttl)
    except REDIS_ERRORS as e:
        logger.warning(f'cach_set faild key={key} err={e}')
# get or set value in cache
async def get_or_set(key:str,ttl:int, loader:Callable[[], Awaitable]):
    """يرجّع (data, source). loader بيجيب الداتا من DB لو الكاش فاضي."""
    cached = await cache_get(key)
    if cached is not None:
        return cached,'cache'
    # If not in cache, load the value using the loader function
    data = await loader()
    # Set the loaded value in cache
    await cache_set(key, data, ttl)
    if data is not None:
        await cache_set(key, data, ttl)
    return data,'database'

# =======================================================================
# delete value from cache
async def cache_delete(key:str)->None:
    try :
        await redis_client.delete(key)
    except REDIS_ERRORS as e:
        logger.warning(f'cach_delete faild key={key} err={e}')

async def cache_delete_pattern(pattern:str)->None:
    try :
        keys = [k async for k in redis_client.scan_iter(pattern)]
        if keys:
            await redis_client.unlink(*keys)
            await redis_client.delete(*keys)
    except REDIS_ERRORS as e:
        logger.warning(f'cache_delete_pattern failed pattern={pattern} err={e}')

async def invalidate_product(product_id: int | None = None) -> None:
    """امسح كاش المنتج (لو معروف) وكل صفحات الليست."""
    if product_id is not None:
        await cache_delete(product_key(product_id))
    await cache_delete_pattern(product_list_pattern())