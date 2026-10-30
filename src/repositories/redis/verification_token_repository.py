from redis import WatchError
from redis.asyncio import Redis
from redis.asyncio.client import Pipeline

from src.core.config import settings
from src.core.logger import log
from src.schemas.exceptions.email_verification import InvalidVerificationTokenException


class VerificationTokenRepository:
    def __init__(self, redis: Redis):
        """Инициализировать репозиторий токенов подтверждения email.

        Args:
            redis (Redis): Асинхронный клиент Redis.
        """
        self.redis = redis


    async def save_verification_token(self, user_id: int, token: str) -> None:
        """Сохранить токен подтверждения email, заменив предыдущий.

        Хранит две связанные записи с одинаковым TTL: токен -> user_id и
        user_id -> токен. Старый токен пользователя, если он есть, удаляется.

        Args:
            user_id (int): Идентификатор пользователя.
            token (str): Токен подтверждения.
        """
        user_key = f"{settings.mailing.user_prefix}:{user_id}"
        token_key = f"{settings.mailing.token_prefix}:{token}"
        ttl = settings.mailing.ttl_seconds

        # Функция может выполниться несколько раз (можно провалиться в transaction ниже и увидеть логику), поэтому внутри -
        # только команды Redis через pipe и чтение актуальных данных, без побочных эффектов
        async def _replace(pipe: Pipeline) -> None:
            # До multi() pipe работает в режиме WATCH: команды выполняются сразу,
            # поэтому старый токен читается здесь, уже под наблюдением за user_key
            old_token_bytes: bytes | None = await pipe.get(user_key)

            # После multi() команды не выполняются, а копятся в очереди до EXEC
            # и затем применяются атомарно: либо все, либо ни одной
            pipe.multi()
            if old_token_bytes:
                old_token = old_token_bytes.decode("utf-8")
                pipe.delete(f"{settings.mailing.token_prefix}:{old_token}")

            pipe.set(token_key, user_id, ex=ttl)
            pipe.set(user_key, token, ex=ttl)

        # transaction() ставит WATCH на user_key, вызывает _replace и делает EXEC.
        # Если между WATCH и EXEC user_key изменил другой запрос (параллельный save или
        # verify), Redis отклоняет EXEC целиком (WatchError), и transaction() повторяет
        # всё с начала: снова WATCH, снова чтение свежего старого токена, снова запись.
        # Так параллельные вызовы для одного пользователя не оставляют лишних живых токенов
        await self.redis.transaction(_replace, user_key)

    
    async def verify_and_consume_token(self, token: str) -> int:
        """Проверить токен подтверждения и атомарно удалить его.

        Использует WATCH/MULTI, чтобы токен нельзя было использовать дважды
        при конкурентных запросах.

        Args:
            token (str): Токен подтверждения.

        Raises:
            InvalidVerificationTokenException: Токен не найден, истёк или был
                изменён другим запросом во время проверки.

        Returns:
            int: Идентификатор пользователя, которому принадлежал токен.
        """
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
        
