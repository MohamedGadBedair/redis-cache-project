from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_socket_timeout: float = 0.5
    redis_connect_timeout: float = 0.5
    redis_connection_pool_size: int = 20

settings = Settings()
