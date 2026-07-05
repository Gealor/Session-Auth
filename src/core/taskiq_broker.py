from typing import Tuple

from taskiq import SmartRetryMiddleware, TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_aio_pika import AioPikaBroker, Queue
from taskiq_redis import RedisAsyncResultBackend

from .config import settings


def prepare_taskiq() -> Tuple[AioPikaBroker, TaskiqScheduler]:
    result_backend = RedisAsyncResultBackend(
        redis_url=settings.redis.redis_url,
        result_ex_time=settings.redis.results_ex_time_in_seconds,
    )

    broker = AioPikaBroker(
        url=settings.rabbitmq.rabbitmq_url,
        # delayed_message_exchange_plugin=True, # для ретраев и отложенных задач (нужен плагин на RabbitMQ)
        delay_queue=Queue(name="taskiq.delay_queue") # без плагинов
    ).with_result_backend(result_backend=result_backend).with_middlewares(
        SmartRetryMiddleware( # Middleware для умного ретрая, с задержкой и максимальным количеством попыток (можно переопределить у конкретной задачи)
            default_retry_count=settings.taskiq.max_retries,
            default_delay=settings.taskiq.countdown_seconds,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=120,
        )
    )

    scheduler = TaskiqScheduler( # scheduler не выполняет задачи
        broker=broker,
        sources=[LabelScheduleSource(broker)]
    )

    return broker, scheduler

broker, scheduler = prepare_taskiq()

