from aiosmtplib import SMTPConnectError

from src.schemas.user_schemas import UserRead
from src.core.celery import celery
from src.core.config import settings
from src.core.celery import get_event_loop
from src.core.logger import log
from src.mailing.send_verification_email import send_verification_email


@celery.task(
    bind=True, # чтобы привязать задачу, к объекту Task (чтобы иметь доступ к методу retry)
    max_retries=settings.celery.max_retries,
    acks_late=True, # Подтверждать задачу, только после выполнения, успешного или с ошибкой ("выполнение" имеется ввиду, что воркер не умер во время ее выполнения)
    reject_on_worker_lost=True, # Возвращать задачу в очередь при сбое воркера
) # внутрь задачи нельзя подавать датаклассы или другие специфичные для языка типы, типы должны быть примитивами (строки, числа, списки и т.д.)
def send_email_for_verification(
    self,
    user: dict[str, int | str],
    verification_token: str
):
    event_loop = get_event_loop()
    if event_loop is None:
        raise RuntimeError("Event loop is not initialized. Task must run inside Celery worker.")
    
    user_model = UserRead.model_validate(user)
    try:
        event_loop.run_until_complete(send_verification_email(user_model, verification_token))
    except SMTPConnectError as e:
        log.error("Failed to connect SMTP server")
        raise self.retry(exc=e, countdown=settings.celery.countdown_seconds)
