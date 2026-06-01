from typing import Any

from asyncpg.exceptions import UniqueViolationError
from pydantic import EmailStr
from sqlalchemy import Select, Update, and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.passwords import hash_password
from models.user import User
from schemas.exceptions.database import DatabaseException, UniqueException
from schemas.exceptions.users import UserNotFoundException
from schemas.user_schemas import (
    UserDelete,
    UserRead,
    UserRegister,
    UserUpdate,
    UserWithWorkInformation,
)
from core.logger import log


class UserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @staticmethod
    def _exclude_deleted_or_not_active(stmt: Select | Update):
        return stmt.where(
            and_(User.is_active, User.deleted_at.is_(None))
        )

    async def get_user_by_email(
        self, email: str | EmailStr, exclude_inactive: bool = False
    ) -> UserWithWorkInformation | None:
        stmt = select(User).where(User.email == email)
        if exclude_inactive:
            stmt = self._exclude_deleted_or_not_active(stmt)

        user = await self.db_session.scalar(stmt)
        if user is None:
            return None

        return UserWithWorkInformation.model_validate(user)

    async def get_user_by_id(
        self, user_id: int, exclude_inactive: bool = False
    ) -> UserRead | None:
        stmt = select(User).where(User.id == user_id)
        if exclude_inactive:
            stmt = self._exclude_deleted_or_not_active(stmt)

        user = await self.db_session.scalar(stmt)
        if user is None:
            return None

        return UserRead.model_validate(user)

    async def create_user(self, user_data: UserRegister):
        user = User(
            nickname=user_data.nickname,
            email=user_data.email,
            password=hash_password(user_data.password).decode("utf-8"),
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
    ) -> UserRead:
        dict_data = update_data.model_dump(exclude_none=True)

        user = await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
            exclude_inactive=exclude_inactive,
        )
        if user is None:
            raise UserNotFoundException
        
        log.info("Update user with id=%d", user_id)
        return UserRead.model_validate(user)

    async def delete_user(self, user_id: int):
        delete_info = UserDelete()
        dict_data = delete_info.model_dump()

        await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
        )
        log.info("Deleted user with id=%d", user_id)

    async def restore_user(self, user_id: int):
        update_data = UserDelete(is_active=True, deleted_at=None)
        dict_data = update_data.model_dump()

        await self.update_data_by_dict(
            user_id=user_id,
            dict_data=dict_data,
        )
        log.info("User restored with id=%d", user_id)
