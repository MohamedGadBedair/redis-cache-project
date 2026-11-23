import json
import logging

from app.redis_clinent import redis_client

logger = logging.getLogger(__name__)

async def cache_get(key:str):
    """يرجّع القيمة أو None لو miss أو لو Redis فيه مشكلة."""
    try :
        raw = await redis_client.get(key)
        return json.load(raw) if raw is not None else None
    except Exception as e :
        logger.warning(f'cache_get failed key={key} err={e}')
        return None
    
async def cache_set(key:str,value, ttl:int)->None:
    try :
        await redis_client.set(key,json.dump(value),ttl)
    except Exception as e:
        logger.warning(f'cach_set faild key={key} err={e}')