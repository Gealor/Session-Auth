from src.core.taskiq_broker import broker
from src.core.database import async_session_maker
from src.core.logger import log
from src.core.config import settings
from src.repositories.session_repository import TokenRepository


async def clear_expired_database_tokens():
    async with async_session_maker() as session:
        await TokenRepository(db_session=session).delete_expired_at_tokens()


@broker.task(schedule=[settings.taskiq.cron_config])
async def cleanup_expired_tokens():
    log.info("Clean expired tokens...")
    await clear_expired_database_tokens()