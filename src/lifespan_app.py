import asyncio

from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from schemas.exceptions.database import DatabaseStartupException
from schemas.exceptions.redis import RedisStartupException
from core.database import async_session_maker, engine
from core.logger import log
from core.redis_client import redis_client
from cron.scheduler import scheduler


class Lifespan:
    async def startup(self):
        """Проверить подключение к Redis и БД при запуске приложения"""
        try:
            await asyncio.gather(
                self._check_redis(),
                self._check_database()
            )
        except (RedisStartupException, DatabaseStartupException):
            raise

        self._startup_scheduler()

    async def shutdown(self):
        """Закрыть соединения при завершении приложения"""
        try:
            await asyncio.gather(
                self._redis_close(),
                self._engine_dispose(),
            )

        except Exception as e:
            log.error("Unexpected error during Redis close: %s", e)


    async def _check_redis(self) -> None:
        """Проверить подключение к Redis"""
        try:
            pong = await redis_client.ping() # type: ignore
            if not pong:
                raise RedisStartupException("Redis ping return False")

            log.info("Redis successful connected")
        except RedisConnectionError as e:
            log.error("Failed to connect Redis: %s", e)
            raise RedisStartupException(f"Failed to connect Redis: {e}") from e
        except Exception as e:
            raise RedisStartupException(f"Unexpected error during connection to Redis: {e}") from e

    async def _check_database(self) -> None:
        """Проверить подключение к базе данных"""
        try:
            async with async_session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                if result is None:
                    raise DatabaseStartupException("Database return empty result")

                log.info("Database successful connected")
        except DatabaseStartupException:
            raise
        except Exception as e:
            raise DatabaseStartupException(f"Unexpected error during connection to database: {e}") from e
        
    async def _redis_close(self) -> None:
        await redis_client.aclose()
        log.info("Redis successful closed")
    
    async def _engine_dispose(self) -> None:
        await engine.dispose()
        log.info("Engine successful disposed!")
        
    def _startup_scheduler(self):
        scheduler.start()
        log.info("Scheduler startup!")

    def _shutdown_scheduler(self):
        scheduler.shutdown()
        log.info("Scheduler shutdown!")

    
