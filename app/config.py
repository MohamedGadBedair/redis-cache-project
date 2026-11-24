from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_socket_timeout: float = 0.5
    redis_connect_timeout: float = 0.5
    redis_connection_pool_size: int = 20

    cach_prefix:str ='myapp'
    cach_version:str ='v1'
    ttl_product:int =60
    ttl_product_list:int = 30

settings = Settings()
