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
    ) -> User | None: ...

    async def get_user_by_email(
        self, email: str | EmailStr, exclude_inactive: bool = False
    ) -> User | None: ...

    async def create_user(self, user_data: UserRegister) -> None: ...

    async def update_user(
        self, user_id: int, update_data: UserUpdate, exclude_inactive: bool = False
    ) -> User: ...

    async def update_data_by_dict(
        self,
        user_id: int,
        dict_data: dict[str, Any],
        exclude_inactive: bool = False,
    ) -> User | None: ...

    async def delete_user(self, user_id: int) -> None: ...

    async def restore_user(self, user_id: int) -> None: ...


class TokenRepo(Protocol):
    async def get_token_by_user_id(
        self, user_id: int, load_user: bool = False
    ) -> str | None: ...

    async def create_record(
        self, user_id: int, token_hash: str, expired_at: datetime
    ) -> None: ...

    async def update_record(
        self, user_id: int, token: str, expired_at: datetime
    ) -> str: ...

    async def delete_token(self, user_id: int) -> None: ...


class VerificationTokenRepo(Protocol):
    async def save_verification_token(self, user_id: int, token: str) -> None: ...

    async def verify_and_consume_token(self, token: str) -> int: ...
