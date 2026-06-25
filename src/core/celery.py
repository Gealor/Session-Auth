from celery import Celery
from celery.schedules import crontab

from .config import settings


def prepare_celery() -> Celery:
    celery = Celery(
        "src.core.celery", 
        broker=settings.rabbitmq.rabbitmq_url,
        backend="rpc://",
        include=[
            "src.tasks.log_tasks",
            "src.tasks.email_send_tasks",
            "src.tasks.clear_expired_tokens",
        ]
    )
    
    celery.conf.beat_schedule = {
        "cleanup_expired_tokens": {
            "task": "src.tasks.clear_expired_tokens.cleanup_expired_tokens",
            "schedule": crontab(minute="30", hour="11", day_of_week="1,3,5,6"), # тут мы выполняем задачу в 11 часов 30 минут по UTC, в понедельник, среду, пятницу и субботу
            # "schedule": crontab(minute="*/5", hour="*"), # тут мы выполняем задачу, каждые 5 минут (00, 05, 10 и т.д.)
        }
    }

    return celery

celery = prepare_celery()

