from aiosmtplib import SMTPConnectError
from asgiref.sync import async_to_sync

from src.schemas.user_schemas import UserRead
from src.core.celery import celery
from src.core.config import settings
from src.core.logger import log
from src.mailing.send_verification_email import send_verification_email


@celery.task(
    bind=True, # чтобы привязать задачу, к объекту Task (чтобы иметь доступ к методу retry)
    max_retries=settings.celery.max_retries,
    acks_late=True, # Подтверждать задачу, только после выполнения, успешного или с ошибкой ("выполнение" имеется ввиду, что воркер не умер во время ее выполнения)
    reject_on_worker_lost=True, # Возвращать задачу в очередь при сбое воркера
    ignore_result=True, # не сохранять результат задачи на backend
) # внутрь задачи нельзя подавать датаклассы или другие специфичные для языка типы, типы должны быть примитивами (строки, числа, списки и т.д.)
def send_email_for_verification(
    self,
    user: dict[str, int | str],
    verification_token: str
):
    user_model = UserRead.model_validate(user)
    try:
        async_to_sync(send_verification_email)(user_model, verification_token)
    except SMTPConnectError as e:
        log.error("Failed to connect SMTP server")
        raise self.retry(exc=e, countdown=settings.celery.countdown_seconds)
