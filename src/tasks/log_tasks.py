from src.core.celery import celery
from src.core.logger import log


@celery.task
def log_action(user_id: int):
    log.info("Action! From user with id=%s", user_id)