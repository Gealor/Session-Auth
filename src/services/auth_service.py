from dateutil.relativedelta import relativedelta

from pydantic import EmailStr

from src.core.date_now import get_current_datetime
from src.core.config import settings
from src.core.auth.creation_tokens import create_token
from src.core.auth.passwords import compare_hashed_passwords, hash_password
from src.core.logger import log
from src.repositories.protocols import TokenRepo, UserRepo
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
    def __init__(self, user_repo: UserRepo, token_repo: TokenRepo):
        """Инициализировать сервис аутентификации.

        Args:
            user_repo (UserRepo): Репозиторий пользователей.
            token_repo (TokenRepo): Репозиторий сессионных токенов.
        """
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def _save_session_token(self, user_id: int, token_hash: str):
        """Сохранить хэш сессионного токена пользователя.

        Если у пользователя уже есть сессия, запись обновляется новым хэшем и сроком
        действия, иначе создаётся новая запись.

        Args:
            user_id (int): Идентификатор пользователя.
            token_hash (str): SHA-256 хэш сессионного токена.
        """
        existing_token = await self.token_repo.get_token_by_user_id(user_id)
        expired_at = get_current_datetime() + relativedelta(
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
        """Зарегистрировать нового пользователя.

        Проверяет совпадение пароля и его повтора, уникальность email, хэширует
        пароль и сохраняет пользователя в БД.

        Args:
            user_data (UserRegisterWithRepeatPassword): Данные для регистрации
                с повтором пароля.

        Raises:
            PasswordsNotMatchException: Пароль и его повтор не совпадают.
            UserEmailAlreadyExistsException: Пользователь с таким email уже существует.
            UniqueException: Нарушено ограничение уникальности (например, nickname).

        Returns:
            ResponseSchema: Сообщение об успешной регистрации.
        """
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
        """Аутентифицировать пользователя и создать сессию.

        Проверяет email и пароль, активность аккаунта, генерирует сессионный токен
        и сохраняет его хэш в БД.

        Args:
            email (EmailStr): Email пользователя.
            password (str): Пароль в открытом виде.

        Raises:
            UserNotFoundException: Пользователь с таким email не найден.
            PasswordsNotMatchException: Неверный пароль.
            UserNotActiveException: Аккаунт удалён или заблокирован.

        Returns:
            str: Сессионный токен в открытом виде (для записи в cookie).
        """
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
        """Завершить сессию пользователя, удалив его сессионный токен.

        Args:
            user_id (int): Идентификатор пользователя.
        """
        await self.token_repo.delete_token(user_id)
        log.info("User id=%d logged out, session token deleted", user_id)
