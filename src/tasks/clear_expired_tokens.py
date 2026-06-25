from asgiref.sync import async_to_sync

from src.core.celery import celery
from src.core.database import create_engine_and_session_maker
from src.core.logger import log
from src.repositories.session_repository import TokenRepository


async def clear_expired_database_tokens(): 
    engine, async_session_maker = create_engine_and_session_maker() # создаем движок для бд и фабрику сессий внутри задачи из-за использования асинхронного кода в СИНХРОННОМ Celery
    try:
        async with async_session_maker() as session:
            await TokenRepository(db_session=session).delete_expired_at_tokens()
    finally:
        await engine.dispose()


# Вообще Celery + asyncio - АНТИПАТТЕРН, т.к. Celery синхронный фреймворк, и возникают такие танцы с бубном при использовании объектов с пулом соединений
@celery.task
def cleanup_expired_tokens():
    log.info("Clean expired tokens...")
    async_to_sync(clear_expired_database_tokens)()