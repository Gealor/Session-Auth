from src.core.taskiq_broker import broker
from src.core.logger import log


@broker.task
async def log_action(user_id: int):
    """Задача TaskIQ: залогировать действие пользователя.

    Args:
        user_id (int): Идентификатор пользователя.
    """
    log.info("Action! From user with id=%s", user_id)