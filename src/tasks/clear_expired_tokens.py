from asgiref.sync import async_to_sync

from src.core.celery import celery
from src.core.database import async_session_maker
from src.core.logger import log
from src.repositories.session_repository import TokenRepository


async def clear_expired_database_tokens():
    async with async_session_maker() as session:
        await TokenRepository(db_session=session).delete_expired_at_tokens()


@celery.task
def cleanup_expired_tokens():
    log.info("Clean expired tokens...")
    async_to_sync(clear_expired_database_tokens)()