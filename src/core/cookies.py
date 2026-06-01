from fastapi import Request, Response

from core.logger import log
from core.config import settings


def _set_cookie(key: str, value: str, response: Response) -> None:
    log.info("Setup cookie %s, value %s...", key, value)
    response.set_cookie(
        key=key,
        value=value,
        httponly=settings.auth.http_only,
        secure=settings.auth.session_cookie_secure,
        samesite=settings.auth.samesite,
        max_age=settings.auth.session_id_expire_minutes * 60,
        path="/",
    )


def _clear_cookie(key: str, response: Response) -> None:
    log.info("Delete cookie %s...", key)
    response.delete_cookie(
        key=key,
        samesite=settings.auth.samesite,
        secure=settings.auth.session_cookie_secure,
        path="/",
    )


def _get_value_from_cookie(key: str, request: Request):
    return request.cookies.get(key, None)
