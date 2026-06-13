from src.core.celery import celery
from src.core.database import async_session_maker
from src.core.logger import log
from src.repositories.session_repository import TokenRepository
from src.core.celery import get_event_loop


async def clear_expired_database_tokens():
    async with async_session_maker() as session:
        await TokenRepository(db_session=session).delete_expired_at_tokens()


@celery.task
def cleanup_expired_tokens():
    event_loop = get_event_loop()
    if event_loop is None:
        raise RuntimeError("Event loop is not initialized. Task must run inside Celery worker.")
    
    log.info("Clean expired tokens...")
    event_loop.run_until_complete(clear_expired_database_tokens())