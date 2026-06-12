from asyncio import AbstractEventLoop
import asyncio

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from .config import settings
from .logger import log

celery_event_loop: AbstractEventLoop | None = None # не нужен mutex, т.к. воркеры находятся в разных процессах, 
# если бы при запуске воркера был указан параметр --pool threads (т.е. воркеры плодились в одном процессе, но в разных потоках, с общей памятью),
# то mutex и блокировка бы пригодились чтобы не было гонки данных

def get_event_loop() -> AbstractEventLoop:
    return celery_event_loop

@worker_process_init.connect
def init_worker(**kwargs):
    global celery_event_loop
    celery_event_loop = asyncio.new_event_loop()
    log.info("Event loop for worker created!")
    asyncio.set_event_loop(celery_event_loop)

@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    global celery_event_loop
    if celery_event_loop:
        celery_event_loop.close()
        log.info("Event loop for worker closed!")

def prepare_celery() -> Celery:
    celery = Celery(
        "src.core.celery", 
        broker=settings.rabbitmq.rabbitmq_url,
        backend="rpc://",
        include=[
            "src.tasks.log_tasks",
            "src.tasks.email_send_tasks",
        ]
    )

    return celery

celery = prepare_celery()

