import redis.asyncio as redis
from app.config import settings
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

pool = redis.BlockingConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_connection_pool_size,
    timeout=settings.redis_pool_wait_timeout,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_connect_timeout,
    retry=Retry(NoBackoff(), 1),   # محاولة إعادة واحدة فورية، بدون انتظار
    decode_responses=True,
)

redis_client =redis.Redis(connection_pool=pool)