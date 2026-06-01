from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import db_session_getter
from core.redis_client import get_redis_client
from services.user_service import UserService

def get_user_service(
    db: AsyncSession = Depends(db_session_getter),
    redis: Redis = Depends(get_redis_client)
) -> UserService:
    return UserService(db_session=db, redis=redis)