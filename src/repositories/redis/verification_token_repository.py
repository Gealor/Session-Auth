from redis import WatchError
from redis.asyncio import Redis

from core.config import settings
from core.logger import log
from schemas.exceptions.email_verification import InvalidVerificationTokenException


class VerificationTokenRepository:
    def __init__(self, redis: Redis):
        self.redis = redis


    async def save_verification_token(self, user_id: int, token: str) -> None:
        user_prefix = settings.mailing.user_prefix
        token_prefix = settings.mailing.token_prefix
        
        old_token_key = f"{user_prefix}:{user_id}"
        old_token_bytes = await self.redis.get(old_token_key)
        if old_token_bytes:
            old_token = old_token_bytes.decode("utf-8")
            log.info("Old verification token: %s", old_token)
            await self.redis.delete(f"{token_prefix}:{old_token}")
            log.info("Old verification token (%s) deleted", old_token)



        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.set(f"{token_prefix}:{token}", user_id, ex=settings.mailing.ttl_seconds)
            await pipe.set(old_token_key, token, ex=settings.mailing.ttl_seconds)
            await pipe.execute()

    
    async def verify_and_consume_token(self, token: str) -> int:
        token_key = f"{settings.mailing.token_prefix}:{token}"

        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(token_key)
                user_id = await pipe.get(token_key)
                if not user_id:
                    raise InvalidVerificationTokenException
                
                user_id = int(user_id)
                log.info("Got user_id: %d", user_id)
                
                user_key = f"{settings.mailing.user_prefix}:{user_id}"
                
                pipe.multi()
                await pipe.delete(token_key)
                await pipe.delete(user_key)
                await pipe.execute()
            except WatchError:
                raise InvalidVerificationTokenException

        return int(user_id)
        
