from pathlib import Path
from textwrap import dedent
from jinja2 import Environment, FileSystemLoader, select_autoescape

from mailing.send_email import send_email
from schemas.user_schemas import UserRead


async def send_verification_email(
    user: UserRead,
    verification_token: str,
    verification_link: str = "http://127.0.0.1:5500/verify-email.html"
):
    url = f"{verification_link}?token={verification_token}"
    recepient = user.email
    subject = "Confirm your email for site.com"
    plain_content = dedent(
        f"""
        Dear {user.nickname},

        Please follow the link to verify your email:
        {url}

        Or you can entered these code by link:
        {verification_link}

        Code:
        {verification_token}

        Your site admin,
        ©, 2026.
        """
    )
    
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        autoescape=select_autoescape(["html", "xml"])  # автоэкранирование для HTML файлов, чтобы избежать XSS атаки
    )
    template = env.get_template("email-verify-template.html")
    html_content = template.render(
        user=user,
        url=url,
        verification_link=verification_link,
        verification_token=verification_token,
    ) 
    await send_email(
        recepient=recepient,
        subject=subject,
        plain_content=plain_content,
        html_content=html_content,
    )