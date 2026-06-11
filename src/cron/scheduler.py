from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.database import async_session_maker
from repositories.session_repository import TokenRepository


scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", **settings.cron.clear_database_config)
async def clear_expired_database_tokens():
    async with async_session_maker() as session:
        await TokenRepository(db_session=session).delete_expired_at_tokens()
