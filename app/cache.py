import uuid
import json
import random
import asyncio
import logging
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from collections.abc import Awaitable, Callable

from app.config import settings
from app.redis_clinent import redis_client
from app.cach_keys import product_key, product_list_pattern

import redis.exceptions as redis_exc
REDIS_ERRORS = (redis_exc.RedisError, OSError, TimeoutError)

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
async def cache_set(key:str,value, ttl:int, jitter:float|None = None)->None:
    payload = serialize(value)
    jitter = settings.cache_ttl_jitter if jitter is None else jitter
    final_ttl = ttl + random.randint(0, int(ttl * jitter))
    try :
        await redis_client.set(name=key,value=payload,ex=final_ttl)
    except REDIS_ERRORS as e:
        logger.warning(f'cach_set faild key={key} err={e}')

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
    except REDIS_ERRORS as e:
        logger.warning(f'cache_delete_pattern failed pattern={pattern} err={e}')
# delete product cache and list cache
async def invalidate_product(product_id: int | None = None) -> None:
    """امسح كاش المنتج (لو معروف) وكل صفحات الليست."""
    if product_id is not None:
        await cache_delete(product_key(product_id))
    await cache_delete_pattern(product_list_pattern())

# =======================================================================
NULL_MARKER = {'__null__':True}

_RELEASE_LOCK = (
    "if redis.call(get, KEYS[1])==ARGV[1]"
    "then return redis.call('del',KEYS[1])else ruturn 0 end"
    )

def _is_null(value)->bool:
    return isinstance(value,dict) and value.get('__unll__') is True

def _lock_key(key:str)->str:
    # prefix مختلف عشان مسح الـ patterns بتاعة الليست مايلمسش الـ locks
    return f'{settings.cach_prefix}:lock:{key}'

async def _release_lock(lock_key:str, token:str)->None:
    # بنمسح الـ lock بس لو لسه بتاعنا (مش بتاع حد تاني بعد ما انتهت صلاحية بتاعنا)
    try :
        await redis_client.eval(_RELEASE_LOCK, 1,lock_key,token)
    except REDIS_ERRORS as e:
        logger.warning(f'release_lock failed lock_key={lock_key} err={e}')

async def _load_and_store(key:str ,ttl:int, loader, null_ttl:int):
    date = await loader()
    if date is None:
        await cache_set(key,NULL_MARKER,null_ttl,jitter=0)
    else: 
        await cache_set(key,date,ttl)
    return date

async def get_or_set(
        key:str,
        ttl:int,
        loader:Callable[[], Awaitable],
        null_ttl:int | None = None
):
    """يرجّع (data, source). data = None معناها إن المورد مش موجود."""
    null_ttl= settings.ttl_not_found if null_ttl is None else null_ttl

    cached = await cache_get(key)
    if cached is not None:
        return (None if _is_null(cached) else cached, 'cache')
    
    lock_key=_lock_key(key)
    token = uuid.uuid4().hex

    try :
        get_lock = await redis_client.set(
            lock_key, token,nx=True,px=settings.cache_lock_ttl_ms
        )
    except REDIS_ERRORS as e:
        # Redis فيه مشكلة: نحمّل من الـ DB مباشرة
        logger.warning('lock failed key=%s err=%s', key, e)
        return await _load_and_store(key, ttl, loader, null_ttl), 'db'
    
    if get_lock:
        try :
            # double-check: ممكن حد يكون خلّص وخزّن قبل ما ناخد الـ lock
            cached = await cache_get(key)
            if cached is not None:
                return (None if _is_null(cached) else cached, 'cache')
            return await _load_and_store(key, ttl, loader, null_ttl), 'db'
        finally:
            await _release_lock(lock_key, token)

    # مش واخدين الـ lock: نستنى صاحبه يملا الكاش
    loop = asyncio.get_running_loop()
    deadline = loop.time()+settings.cahc_lock_wait_seconds
    while loop.time()<deadline:
        await asyncio.sleep(settings.cach_lock_poll_seconds)
        cached = await cache_get(key)
        if cached is not None:
            return (None if _is_null(cached) else cached, 'cache')
        
    # انتهت مهلة الانتظار: نحمّل بنفسنا بدل ما نفشل
    return await _load_and_store(key, ttl, loader, null_ttl), 'db'