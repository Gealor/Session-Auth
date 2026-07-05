from typing import Annotated

from taskiq import TaskiqDepends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.taskiq_broker import broker
from src.core.database import db_session_getter
from src.core.logger import log
from src.core.config import settings
from src.repositories.session_repository import TokenRepository


async def clear_expired_database_tokens(db_session):
    await TokenRepository(db_session=db_session).delete_expired_at_tokens()


@broker.task(schedule=[settings.taskiq.cron_config])
async def cleanup_expired_tokens(
    db_session: Annotated[AsyncSession, TaskiqDepends(db_session_getter)]
): # Annotated в таком ключе используется, чтобы можно было объявить зависимость не значением по умолчанию, а типом, 
    # что позволит вынести Annotated[...] в отдельную переменную и переиспользовать ее
    log.info("Clean expired tokens...")
    await clear_expired_database_tokens(db_session)