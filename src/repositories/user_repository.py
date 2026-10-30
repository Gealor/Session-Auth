from typing import Any

from asyncpg.exceptions import UniqueViolationError
from pydantic import EmailStr
from sqlalchemy import Select, Update, and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.exceptions.database import DatabaseException, UniqueException
from src.schemas.exceptions.users import UserNotFoundException
from src.schemas.user_schemas import (
    UserDelete,
    UserRegister,
    UserUpdate,
)
from src.core.logger import log


class UserRepository:
    def __init__(self, db_session: AsyncSession):
        """Инициализировать репозиторий пользователей.

        Args:
            db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        """
        self.db_session = db_session

    @staticmethod
    def _exclude_deleted_or_not_active(stmt: Select | Update):
        """Добавить к запросу фильтр по активным и не удалённым пользователям.

        Args:
            stmt (Select | Update): Исходный запрос по User.

        Returns:
            Select | Update: Запрос с условием is_active и deleted_at IS NULL.
        """
        return stmt.where(
            and_(User.is_active, User.deleted_at.is_(None))
        )

    async def get_user_by_email(
        self, email: str | EmailStr, exclude_inactive: bool = False
    ) -> User | None:
        """Получить пользователя по email.

        Args:
            email (str | EmailStr): Email пользователя.
            exclude_inactive (bool, optional): Исключить удалённых и неактивных
                пользователей. Defaults to False.

        Returns:
            User | None: Пользователь или None, если не найден.
        """
        stmt = select(User).where(User.email == email)
        if exclude_inactive:
            stmt = self._exclude_deleted_or_not_active(stmt)

        user = await self.db_session.scalar(stmt)
        if user is None:
            return None

        return user

    async def get_user_by_id(
        self, user_id: int, exclude_inactive: bool = False
    ) -> User | None:
        """Получить пользователя по идентификатору.

        Args:
            user_id (int): Идентификатор пользователя.
            exclude_inactive (bool, optional): Исключить удалённых и неактивных
                пользователей. Defaults to False.

        Returns:
            User | None: Пользователь или None, если не найден.
        """
        stmt = select(User).where(User.id == user_id)
        if exclude_inactive:
            stmt = self._exclude_deleted_or_not_active(stmt)

        user = await self.db_session.scalar(stmt)
        if user is None:
            return None

        return user

    async def create_user(self, user_data: UserRegister) -> None:
        """Создать активного пользователя.

        Args:
            user_data (UserRegister): Данные пользователя с уже захэшированным паролем.

        Raises:
            UniqueException: Нарушено ограничение уникальности (email, nickname).
            DatabaseException: Иная ошибка целостности при сохранении.
        """
        user = User(
            nickname=user_data.nickname,
            email=user_data.email,
            password=user_data.password,
            is_active=True,
        )

        self.db_session.add(user)
        try:
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            orig = e.orig.__cause__
            if isinstance(orig, UniqueViolationError):
                # В asyncpg доступ к имени ограничения идет напрямую: cause.constraint_name
                log.error("Failed to create user, unique violation: %s", orig.constraint_name)
                log.error(orig.detail)
                # raise orig
                raise UniqueException(exc=orig)
            
            log.error("Failed to create user: %s", e)
            raise DatabaseException

        await self.db_session.refresh(user)
        log.info("Create new user with id=%d", user.id)

    async def update_data_by_dict(
        self,
        user_id: int,
        dict_data: dict[str, Any],
        exclude_inactive: bool = False,
    ) -> User | None:
        """Обновить поля пользователя из словаря.

        Args:
            user_id (int): Идентификатор пользователя.
            dict_data (dict[str, Any]): Имена полей и их новые значения.
            exclude_inactive (bool, optional): Не обновлять удалённых и неактивных
                пользователей. Defaults to False.

        Raises:
            UniqueException: Нарушено ограничение уникальности.
            DatabaseException: Иная ошибка целостности при сохранении.

        Returns:
            User | None: Обновлённый пользователь или None, если не найден.
        """
        stmt = (
            update(User).values(**dict_data).where(User.id == user_id).returning(User)
        )
        if exclude_inactive:
            stmt = self._exclude_deleted_or_not_active(stmt)

        try:
            user = await self.db_session.scalar(stmt)
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            orig = e.orig.__cause__ # не можем просто написать orig = e.orig, т.к. SQLAlchemy оборачивает все ошибки в свою IntegrityError, аналогично не можем просто ловить UniqueViolationError в except блоке
            if isinstance(orig, UniqueViolationError):
                # В asyncpg доступ к имени ограничения идет напрямую: cause.constraint_name
                log.error("Failed to update user, unique violation: %s", orig.constraint_name)
                log.error(orig.detail)
                # raise orig
                raise UniqueException(exc=orig)
            
            log.error("Failed to update user: %s", e)
            raise DatabaseException

        await self.db_session.refresh(user)
        return user

    async def update_user(
        self, user_id: int, update_data: UserUpdate, exclude_inactive: bool = False
    ) -> User:
        """Обновить пользователя данными из схемы.

        Поля со значением None не обновляются.

        Args:
            user_id (int): Идентификатор пользователя.
            update_data (UserUpdate): Новые значения полей.
            exclude_inactive (bool, optional): Не обновлять удалённых и неактивных
                пользователей. Defaults to False.

        Raises:
            UserNotFoundException: Пользователь не найден.

        Returns:
            User: Обновлённый пользователь.
        """
        dict_data = update_data.model_dump(exclude_none=True)

        user = await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
            exclude_inactive=exclude_inactive,
        )
        if user is None:
            raise UserNotFoundException
        
        log.info("Update user with id=%d", user_id)
        return user

    async def delete_user(self, user_id: int) -> None:
        """Мягко удалить пользователя.

        Выставляет is_active=False и deleted_at в текущее время (UTC).

        Args:
            user_id (int): Идентификатор пользователя.
        """
        delete_info = UserDelete()
        dict_data = delete_info.model_dump()

        await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
        )
        log.info("Deleted user with id=%d", user_id)

    async def restore_user(self, user_id: int) -> None:
        """Восстановить мягко удалённого пользователя.

        Выставляет is_active=True и сбрасывает deleted_at.

        Args:
            user_id (int): Идентификатор пользователя.
        """
        update_data = UserDelete(is_active=True, deleted_at=None)
        dict_data = update_data.model_dump()

        await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
        )
        log.info("User restored with id=%d", user_id)
