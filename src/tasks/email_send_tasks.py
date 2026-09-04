from typing import Any

from aiosmtplib import SMTPConnectError

from src.schemas.user_schemas import UserRead
from src.core.taskiq_broker import broker
from src.core.config import settings
from src.core.logger import log
from src.mailing.send_verification_email import send_verification_email


@broker.task(
    retry_on_error=True, # повтор для этой задачи
    max_retries=settings.taskiq.max_retries, # переопределяет значение SmartRetryMiddleware
) # внутрь задачи нельзя подавать датаклассы или другие специфичные для языка типы, типы должны быть примитивами (строки, числа, списки и т.д.)
async def send_email_for_verification(
    user: dict[str, Any],
    verification_token: str
):
    user_model = UserRead.model_validate(user)
    try:
        await send_verification_email(user_model, verification_token)
    except SMTPConnectError as e:
        log.error("Failed to connect SMTP server")
        raise e
