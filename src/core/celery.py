from celery import Celery
from .config import settings


celery = Celery(
    "src.core.celery", 
    broker=settings.rabbitmq.rabbitmq_url,
    backend="rpc://",
)