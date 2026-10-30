"""Структурные протоколы репозиториев.

Определяют контракт с точки зрения сервисного слоя: сюда попадают только те
методы, которые реально вызывают сервисы. Реальные репозитории ничего не
наследуют — соответствие проверяется структурно (mypy/pyright). Тестовые
фейки достаточно сделать совместимыми по сигнатурам.

Добавление нового запроса в фичу = добавление метода в нужный протокол,
меняются только тесты того сервиса, который его использует.
"""

from datetime import datetime
from typing import Any, Protocol

from pydantic import EmailStr

from src.models.user import User
from src.schemas.user_schemas import UserRegister, UserUpdate


class UserRepo(Protocol):
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

    async def create_user(self, user_data: UserRegister) -> None:
        """Создать пользователя.

        Args:
            user_data (UserRegister): Данные пользователя с уже захэшированным паролем.
        """

    async def update_user(
        self, user_id: int, update_data: UserUpdate, exclude_inactive: bool = False
    ) -> User:
        """Обновить пользователя данными из схемы.

        Args:
            user_id (int): Идентификатор пользователя.
            update_data (UserUpdate): Новые значения полей.
            exclude_inactive (bool, optional): Не обновлять удалённых и неактивных
                пользователей. Defaults to False.

        Returns:
            User: Обновлённый пользователь.
        """

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

        Returns:
            User | None: Обновлённый пользователь или None, если не найден.
        """

    async def delete_user(self, user_id: int) -> None:
        """Мягко удалить пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
        """

    async def restore_user(self, user_id: int) -> None:
        """Восстановить мягко удалённого пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
        """


class TokenRepo(Protocol):
    async def get_token_by_user_id(
        self, user_id: int, load_user: bool = False
    ) -> str | None:
        """Получить хэш сессионного токена пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            load_user (bool, optional): Подгрузить связанного пользователя.
                Defaults to False.

        Returns:
            str | None: Хэш токена или None, если сессии нет.
        """

    async def create_record(
        self, user_id: int, token_hash: str, expired_at: datetime
    ) -> None:
        """Создать запись сессионного токена.

        Args:
            user_id (int): Идентификатор пользователя.
            token_hash (str): Хэш сессионного токена.
            expired_at (datetime): Момент истечения сессии.
        """

    async def update_record(
        self, user_id: int, token: str, expired_at: datetime
    ) -> str:
        """Обновить сессионный токен пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            token (str): Новый хэш сессионного токена.
            expired_at (datetime): Новый момент истечения сессии.

        Returns:
            str: Сохранённый хэш токена.
        """

    async def delete_token(self, user_id: int) -> None:
        """Удалить сессионный токен пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
        """


class VerificationTokenRepo(Protocol):
    async def save_verification_token(self, user_id: int, token: str) -> None:
        """Сохранить токен подтверждения email, заменив предыдущий.

        Args:
            user_id (int): Идентификатор пользователя.
            token (str): Токен подтверждения.
        """

    async def verify_and_consume_token(self, token: str) -> int:
        """Проверить токен подтверждения и удалить его.

        Args:
            token (str): Токен подтверждения.

        Raises:
            InvalidVerificationTokenException: Токен не найден или уже использован.

        Returns:
            int: Идентификатор пользователя, которому принадлежал токен.
        """
