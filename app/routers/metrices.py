import asyncio

from fastapi import routing

from app.redis_client import redis_client
from app import metrics
from app.circuit_breaker import breaker

router=routing.APIRouter()

@router.get('')
async def metrics_endpoint():
    try:
        mem =await asyncio.wait_for(redis_client.info('memory'),timeout=1)
        stats =await asyncio.wait_for(redis_client.info('stats'),timeout=1)
        redis_info={
            "used_memory_human":mem.get('used_memory_human'),
            'evicted_keys':stats.get('evicted_keys'),
            'keys':await asyncio.wait_for(redis_client.dbsize(),timeout=1),
        }
    except Exception:
        redis_info={'error':'unavailable'}
    return{**metrics.snapshot(),'circuit':breaker.state.value, "redis":redis_info}