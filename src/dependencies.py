from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import db_session_getter
from src.core.redis_client import get_redis_client
from src.services.user_service import UserService

def get_user_service(
    db: AsyncSession = Depends(db_session_getter),
    redis: Redis = Depends(get_redis_client)
) -> UserService:
    return UserService(db_session=db, redis=redis)