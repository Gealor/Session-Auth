import asyncio

from src.schemas.user_schemas import UserRead
from src.core.celery import celery
from src.mailing.send_verification_email import send_verification_email
from src.core.celery import get_event_loop


@celery.task # внутрь задачи нельзя подавать датаклассы или другие специфичные для языка типы, типы должны быть примитивами (строки, числа, списки и т.д.)
def send_email_for_verification(
    user: dict[str, int | str],
    verification_token: str
):
    event_loop = get_event_loop()
    if event_loop is None:
        raise RuntimeError("Event loop is not initialized. Task must run inside Celery worker.")
    
    user_model = UserRead.model_validate(user)
    event_loop.run_until_complete(send_verification_email(user_model, verification_token))