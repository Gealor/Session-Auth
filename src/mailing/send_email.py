from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from src.core.config import settings


async def send_email(
    recepient: str,
    subject: str,
    plain_content: str,
    html_content: str | None = None,
):
    message = MIMEMultipart("alternative")
    message["From"] = settings.mailing.admin_email
    message["To"] = recepient
    message["Subject"] = subject

    plain_text_message = MIMEText(
        plain_content,
        "plain",
        "utf-8",
    )
    message.attach(plain_text_message)
    if html_content is not None:
        html_message = MIMEText(
            html_content,
            "html",
            "utf-8",
        )
        message.attach(html_message)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp.host,
        port=settings.smtp.port,
    )
