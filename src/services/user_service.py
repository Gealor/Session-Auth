from src.core.auth.passwords import compare_hashed_passwords, hash_password
from src.core.logger import log
from src.repositories.protocols import TokenRepo, UserRepo, VerificationTokenRepo
from src.schemas.exceptions.users import NewPasswordMatchWithOldException, UserAlreadyVerifiedException, UserNotDeletedException, UserNotFoundException
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import UserRead, UserUpdate


class UserService:
    def __init__(
        self, 
        user_repo: UserRepo,
        verification_token_repo: VerificationTokenRepo,
        token_repo: TokenRepo,
    ):
        """Инициализировать сервис пользователей.

        Args:
            user_repo (UserRepo): Репозиторий пользователей.
            verification_token_repo (VerificationTokenRepo): Репозиторий токенов
                подтверждения email.
            token_repo (TokenRepo): Репозиторий сессионных токенов.
        """
        self.user_repo = user_repo
        self.verification_token_repo = verification_token_repo
        self.token_repo = token_repo

    async def update_user(
        self, user_id: int, update_data: UserUpdate, exclude_inactive: bool = True
    ) -> UserRead:
        """Обновить профиль пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            update_data (UserUpdate): Новые значения полей (None-поля игнорируются).
            exclude_inactive (bool, optional): Не обновлять удалённых и неактивных
                пользователей. Defaults to True.

        Raises:
            UserNotFoundException: Пользователь не найден.
            UniqueException: Нарушено ограничение уникальности.

        Returns:
            UserRead: Обновлённые данные пользователя.
        """
        user = await self.user_repo.update_user(
            user_id=user_id,
            update_data=update_data,
            exclude_inactive=exclude_inactive,
        )
        if not user:
            raise UserNotFoundException

        return UserRead.model_validate(user)

    async def delete_self_user(self, user_id: int) -> ResponseSchema:
        """Мягко удалить аккаунт пользователя и завершить его сессию.

        Args:
            user_id (int): Идентификатор пользователя.

        Returns:
            ResponseSchema: Сообщение об успешном удалении.
        """
        await self.user_repo.delete_user(user_id=user_id)
        await self.token_repo.delete_token(user_id=user_id)
        return ResponseSchema(
            msg="Account successfully deleted. You have been logged out."
        )

    async def restore_deleted_user(self, user_id: int) -> ResponseSchema:
        """Восстановить мягко удалённого пользователя.

        Args:
            user_id (int): Идентификатор пользователя.

        Raises:
            UserNotFoundException: Пользователь не найден.
            UserNotDeletedException: Пользователь не удалён.

        Returns:
            ResponseSchema: Сообщение об успешном восстановлении.
        """
        user = await self.user_repo.get_user_by_id(user_id=user_id)
        if not user:
            raise UserNotFoundException

        if not user.deleted_at and user.is_active:
            raise UserNotDeletedException

        await self.user_repo.restore_user(user_id=user_id)
        return ResponseSchema(msg="User successfully restored")

    async def verify_user(self, token: str):
        """Подтвердить email пользователя по токену подтверждения.

        Токен удаляется из хранилища (одноразовый).

        Args:
            token (str): Токен подтверждения email.

        Raises:
            InvalidVerificationTokenException: Токен не найден, истёк или уже использован.
            UserNotFoundException: Пользователь, которому принадлежит токен, не найден.
            UserAlreadyVerifiedException: Email пользователя уже подтверждён.
        """
        user_id = await self.verification_token_repo.verify_and_consume_token(
            token=token,
        )
        
        user_old = await self.user_repo.get_user_by_id(user_id=user_id, exclude_inactive=True)
        if user_old is None:
            raise UserNotFoundException
        if user_old.is_verified:
            raise UserAlreadyVerifiedException

        data = {"is_verified": True}
        await self.user_repo.update_data_by_dict(
            user_id=user_id, dict_data=data, exclude_inactive=True
        )

    async def update_user_password(self, user_id: int, new_password: str) -> None:
        """Сменить пароль пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            new_password (str): Новый пароль в открытом виде.

        Raises:
            UserNotFoundException: Пользователь не найден.
            NewPasswordMatchWithOldException: Новый пароль совпадает со старым.
        """
        user = await self.user_repo.get_user_by_id(user_id=user_id)
        if user is None:
            log.error("User with id=%d not found", user_id)
            raise UserNotFoundException

        new_password_bytes = new_password.encode("utf-8")
        old_password_hash = user.password.encode("utf-8")

        if await compare_hashed_passwords(new_password_bytes, old_password_hash):
            log.error("New password match with old. User_id=%d", user_id)
            raise NewPasswordMatchWithOldException
        
        updated_password = {
            "password": (await hash_password(new_password)).decode("utf-8"),
        }

        await self.user_repo.update_data_by_dict(
            user_id=user_id,
            dict_data=updated_password,
        )
        log.info("Password successful change on '%s' for user_id=%d", new_password, user_id)
    


