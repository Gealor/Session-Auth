from fastapi import APIRouter, Body, Depends, HTTPException, Response, status

from src.core.auth.security import get_current_user
from src.core.config import settings
from src.core.cookies import _clear_cookie, _set_cookie
from src.core.database import db_session_getter
from src.core.logger import log
from src.core.redis_client import get_redis_client
from src.schemas.exceptions.database import UniqueException
from src.schemas.exceptions.email_verification import InvalidVerificationTokenException
from src.schemas.exceptions.security import (
    PasswordsNotMatchException,
    UserEmailAlreadyExistsException,
    UserNotActiveException,
)
from src.schemas.exceptions.users import UserAlreadyVerifiedException, UserNotFoundException
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import (
    LoginCredentials,
    UserRead,
    UserRegisterWithRepeatPassword,
)
from src.services.auth_service import AuthService
from src.dependencies import get_user_service
from src.services.email_verification import EmailVerificationService
from src.services.user_service import UserService
from src.tasks.email_send_tasks import send_email_for_verification


router = APIRouter(prefix="/auth", tags=["Session"])


@router.post("/register")
async def create_user(
    user_data: UserRegisterWithRepeatPassword,
    db=Depends(db_session_getter),
) -> ResponseSchema: # Если схема не будет соответствовать результату, то fastapi выдаст ошибку валидации, т.к. аннотации в fastapi это не условность
    try:
        result = await AuthService(db_session=db).register_user(user_data)
    except PasswordsNotMatchException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
        )
    except UserEmailAlreadyExistsException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists",
        )
    except UniqueException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"\'{e}\' with this value already exist"
        )
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error"
        )

    return result


@router.post("/login")
async def login_user(
    response: Response,
    credentials: LoginCredentials,
    db=Depends(db_session_getter),
) -> ResponseSchema:
    try:
        token = await AuthService(db_session=db).login_user(
            email=credentials.email,
            password=credentials.password,
        )
    except (UserNotFoundException, PasswordsNotMatchException):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    except UserNotActiveException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account deleted or blocked"
        )
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error"
        )
    _set_cookie(
        key = settings.auth.session_id_cookie_name,
        value=token,
        response=response,
    )
    return ResponseSchema(
        msg = "Succesful login!",
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: UserRead = Depends(get_current_user),
    db=Depends(db_session_getter),
) -> ResponseSchema:
    try:
        await AuthService(db_session=db).logout_user(user_id=current_user.id)
    except Exception as e:
        log.error("Unexpected error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during logout",
        )
    _clear_cookie(
        key = settings.auth.session_id_cookie_name,
        response = response,
    )
    return ResponseSchema(msg = "Successfully logged out.")


@router.post("/send-verification-email", status_code=status.HTTP_202_ACCEPTED)
async def generate_token_and_send_verification_email(
    current_user: UserRead = Depends(get_current_user),
    redis = Depends(get_redis_client)
):
    
    try:
        token = await EmailVerificationService(redis=redis).save_verification_token(
            user_id=current_user.id,
            is_verified=current_user.is_verified,
        )
    except UserAlreadyVerifiedException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    send_email_for_verification.delay(user=current_user.model_dump(), verification_token=token)

    
@router.post("/verify")
async def verify_user(
    token: str = Body(embed=True),
    user_service: UserService = Depends(get_user_service)
):
    try:
        await user_service.verify_user(token)
    except InvalidVerificationTokenException:
        log.info("Invalid verification token: %s", token)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    except UserAlreadyVerifiedException:
        log.info("Email already verified")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    except UserNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
     
