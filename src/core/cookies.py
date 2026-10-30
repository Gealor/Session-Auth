from fastapi import Request, Response

from .logger import log
from .config import settings


def _set_cookie(key: str, value: str, response: Response) -> None:
    """Установить cookie с параметрами безопасности из настроек.

    Args:
        key (str): Имя cookie.
        value (str): Значение cookie.
        response (Response): HTTP-ответ, в который добавляется cookie.
    """
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
    """Удалить cookie из браузера клиента.

    Args:
        key (str): Имя cookie.
        response (Response): HTTP-ответ, в который добавляется удаление cookie.
    """
    log.info("Delete cookie %s...", key)
    response.delete_cookie(
        key=key,
        samesite=settings.auth.samesite,
        secure=settings.auth.session_cookie_secure,
        path="/",
    )


def _get_value_from_cookie(key: str, request: Request):
    """Получить значение cookie из запроса.

    Args:
        key (str): Имя cookie.
        request (Request): Входящий HTTP-запрос.

    Returns:
        str | None: Значение cookie или None, если она не установлена.
    """
    return request.cookies.get(key, None)
