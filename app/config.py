from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_socket_timeout: float = 0.5
    redis_connect_timeout: float = 0.5
    redis_connection_pool_size: int = 20

    cache_prefix:str ='myapp'
    cache_version:str ='v1'
    ttl_product:int =60
    ttl_product_list:int = 30

    ttl_not_found:int = 10
    cache_ttl_jitter:float = 0.1
    cache_lock_ttl_ms: int = 5000
    cache_lock_wait_seconds:float = 2.0
    cache_lock_poll_seconds:float = 0.05
    
    breaker_failure_threshold: int = 3
    breaker_reset_seconds: float = 10.0
    redis_pool_wait_timeout: float = 1.0

settings = Settings()
