from datetime import datetime
from dateutil.relativedelta import relativedelta

from pydantic import EmailStr

from src.core.config import settings
from src.core.auth.creation_tokens import create_token
from src.core.auth.passwords import compare_hashed_passwords, hash_password
from src.core.logger import log
from src.repositories.session_repository import TokenRepository
from src.repositories.user_repository import UserRepository
from src.schemas.exceptions.security import (
    PasswordsNotMatchException,
    UserEmailAlreadyExistsException,
    UserNotActiveException,
)
from src.schemas.exceptions.users import UserNotFoundException
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import (
    UserRegister,
    UserRegisterWithRepeatPassword,
)


class AuthService:
    def __init__(self, db_session):
        self.db_session = db_session
        self.user_repo = UserRepository(db_session=self.db_session)
        self.token_repo = TokenRepository(db_session=self.db_session)

    async def _save_session_token(self, user_id: int, token_hash: str):
        existing_token = await self.token_repo.get_token_by_user_id(user_id)
        expired_at = datetime.now() + relativedelta(
            minutes=settings.auth.session_id_expire_minutes
        )
        if existing_token:
            await self.token_repo.update_record(user_id, token_hash, expired_at)
        else:
            await self.token_repo.create_record(user_id, token_hash, expired_at)

    async def register_user(
        self,
        user_data: UserRegisterWithRepeatPassword,
    ) -> ResponseSchema:
        if user_data.password != user_data.repeat_password:
            log.error(
                "Password and repeat password do not match: %s != %s",
                user_data.password,
                user_data.repeat_password,
            )
            raise PasswordsNotMatchException

        existing_user = await self.user_repo.get_user_by_email(user_data.email)
        if existing_user:
            log.error("User with these email already exist")
            raise UserEmailAlreadyExistsException

        user_register_data = UserRegister(**user_data.model_dump())
        user_register_data.password = (await hash_password(user_data.password)).decode("utf-8")
        await self.user_repo.create_user(
            user_register_data,
        )

        return ResponseSchema(msg="Succesful registration. Now you can log in.")

    async def login_user(self, email: EmailStr, password: str) -> str:
        user = await self.user_repo.get_user_by_email(email=email)
        if not user:
            log.error("User by email %s not found", email)
            raise UserNotFoundException

        is_valid = await compare_hashed_passwords(
            entered_password=password.encode("utf-8"),
            hashed_password=user.password.encode("utf-8"),
        )
        if not is_valid:
            log.error("Passwords do not match")
            raise PasswordsNotMatchException

        if not user.is_active:
            log.error("User with email %s is not active", email)
            raise UserNotActiveException

        token, token_hash = create_token()
        log.info("Session token created.")
        await self._save_session_token(
            user_id=user.id,
            token_hash=token_hash,
        )
        log.info("Session token created and saved.")

        log.info("Succesful log in in account: %s", email)
        return token

    async def logout_user(self, user_id: int):
        await self.token_repo.delete_token(user_id)
        log.info("User id=%d logged out, session token deleted", user_id)
