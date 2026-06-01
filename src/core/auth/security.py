from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.creation_tokens import hash_token
from core.cookies import _get_value_from_cookie
from core.logger import log
from core.config import settings
from core.database import db_session_getter
from repositories.session_repository import TokenRepository
from schemas.user_schemas import UserRead

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def _get_session_from_cookie(request: Request):
    return _get_value_from_cookie(settings.auth.session_id_cookie_name, request)


async def get_current_user(
    token: str = Depends(_get_session_from_cookie),
    db: AsyncSession = Depends(db_session_getter),
    _swagger_doc: str | None = Depends(oauth2_scheme),
) -> UserRead:
    if not token:
        log.error("Session token user not found: %s", token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Session token not set",
        )

    token_hash = hash_token(token)

    token_record = await TokenRepository(db).get_token_by_hash(token_hash, load_user=True)
    if token_record is None:
        log.error("Session token not found: %s", token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Session token not found",
        )

    log.info(
        "Token: user_id = %d\n token_hash = %s\n expired_at = %s",
        token_record.user_id,
        token_record.session_token,
        token_record.expired_at,
    )

    current_datetime = datetime.now(UTC)
    if current_datetime >= token_record.expired_at:
        log.error("Session token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Session token expired",
        )
    
    # Если отключен load_user (False), по факту будет два запроса, один на получение токена сессии, второй - на получение пользователя
    # log.info("Awaitable Attrs loading...")
    # user = await token_record.awaitable_attrs.user
    # user = UserRead.model_validate(user)
    
    # Если включен load_user (True), тут же будет один запрос, который подгрузит вместе с токеном сессии сразу пользователя, без доп.запроса
    user = UserRead.model_validate(token_record.user) 
    
    if not user or not user.is_active:
        log.error("User with id=%d is not active or not exist", user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The user was not found or deleted",
        )
    return user

