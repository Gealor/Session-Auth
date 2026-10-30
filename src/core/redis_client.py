from redis.asyncio import Redis

from .config import settings

redis_client: Redis = Redis(
    host=settings.redis.host,
    port=settings.redis.port,
)

def get_redis_client() -> Redis:
    """Зависимость: вернуть общий асинхронный клиент Redis.

    Returns:
        Redis: Клиент Redis приложения.
    """
    return redis_client