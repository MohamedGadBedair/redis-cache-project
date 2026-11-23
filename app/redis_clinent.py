import redis.asyncio as redis
from app.config import settings

pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_connection_pool_size,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_connect_timeout,
    decode_responses=True,
)

redis_client =redis.Redis(connection_pool=pool)