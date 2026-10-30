import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.auth.creation_tokens import hash_token
from src.core.auth.passwords import compare_hashed_passwords
from src.core.config import settings
from src.core.date_now import get_current_datetime
from src.models.sessions import SessionToken
from src.models.user import User
from src.repositories.session_repository import TokenRepository
from src.repositories.user_repository import UserRepository
from src.schemas.exceptions.database import UniqueException
from src.schemas.exceptions.security import (
    PasswordsNotMatchException,
    UserEmailAlreadyExistsException,
    UserNotActiveException,
)
from src.schemas.exceptions.users import UserNotFoundException
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import UserRegisterWithRepeatPassword
from src.services.auth_service import AuthService
from tests.conftest import TEST_PASSWORD

PASSWORD = "SecretPassword123!"
SESSION_TTL = timedelta(minutes=settings.auth.session_id_expire_minutes)

INACTIVE_STATES = [
    pytest.param({"is_active": False}, id="inactive-without-deleted-at"),
    pytest.param({"is_active": False, "deleted_at": get_current_datetime()}, id="deleted"),
]


def _register_data(
    *,
    nickname: str = "new_user",
    email: str = "new_user@example.com",
    password: str = PASSWORD,
    repeat_password: str | None = None,
) -> UserRegisterWithRepeatPassword:
    return UserRegisterWithRepeatPassword(
        nickname=nickname,
        email=email,
        password=password,
        repeat_password=password if repeat_password is None else repeat_password,
    )


@pytest.fixture()
def count_users(session_maker: async_sessionmaker[AsyncSession]):
    async def _count_users() -> int:
        async with session_maker() as session:
            return await session.scalar(select(func.count()).select_from(User))

    return _count_users


@pytest.fixture()
def find_user_by_email(session_maker: async_sessionmaker[AsyncSession]):
    async def _find(email: str) -> User | None:
        async with session_maker() as session:
            return await session.scalar(select(User).where(User.email == email))

    return _find


@pytest.fixture()
def find_session_by_token(session_maker: async_sessionmaker[AsyncSession]):
    """Найти сессию по выданному клиенту токену — так её ищет приложение на каждом запросе."""

    async def _find(token: str) -> SessionToken | None:
        async with session_maker() as session:
            return await session.scalar(
                select(SessionToken).where(SessionToken.session_token == hash_token(token))
            )

    return _find


# ---------------------------------------------------------------------- register_user


async def test_register_creates_active_unverified_user(
    auth_service: AuthService,
    find_user_by_email,
):
    data = _register_data()

    result = await auth_service.register_user(data)

    assert isinstance(result, ResponseSchema)
    user = await find_user_by_email(data.email)
    assert user is not None
    assert user.nickname == data.nickname
    assert user.is_active
    assert not user.is_verified
    assert user.deleted_at is None


async def test_register_stores_password_hash(
    auth_service: AuthService,
    find_user_by_email,
):
    data = _register_data()

    await auth_service.register_user(data)

    user = await find_user_by_email(data.email)
    assert PASSWORD not in user.password
    assert await compare_hashed_passwords(PASSWORD, user.password.encode("utf-8"))


async def test_register_accepts_long_password(
    auth_service: AuthService,
    find_user_by_email,
):
    long_password = "п" * 100  # 200 байт в UTF-8 — больше лимита bcrypt
    data = _register_data(password=long_password)

    await auth_service.register_user(data)

    user = await find_user_by_email(data.email)
    assert await compare_hashed_passwords(long_password, user.password.encode("utf-8"))


async def test_register_with_mismatched_passwords_raises(
    auth_service: AuthService,
    count_users,
):
    with pytest.raises(PasswordsNotMatchException):
        await auth_service.register_user(_register_data(repeat_password=PASSWORD + "x"))

    assert await count_users() == 0


async def test_register_with_taken_email_raises(
    auth_service: AuthService,
    make_user,
    count_users,
):
    await make_user(email="taken@example.com")

    with pytest.raises(UserEmailAlreadyExistsException):
        await auth_service.register_user(_register_data(email="taken@example.com"))

    assert await count_users() == 1


async def test_register_with_email_of_deleted_user_raises(
    auth_service: AuthService,
    make_user,
):
    # Мягко удалённый аккаунт можно восстановить — его email остаётся занятым
    await make_user(email="taken@example.com", is_active=False, deleted_at=get_current_datetime())

    with pytest.raises(UserEmailAlreadyExistsException):
        await auth_service.register_user(_register_data(email="taken@example.com"))


async def test_register_with_taken_nickname_raises(
    auth_service: AuthService,
    make_user,
    count_users,
):
    await make_user(nickname="taken")

    with pytest.raises(UniqueException):
        await auth_service.register_user(_register_data(nickname="taken"))

    assert await count_users() == 1


async def test_registered_user_can_log_in(auth_service: AuthService):
    data = _register_data()
    await auth_service.register_user(data)

    token = await auth_service.login_user(data.email, PASSWORD)

    assert token


# ------------------------------------------------------------------------- login_user


async def test_login_creates_session_for_returned_token(
    auth_service: AuthService,
    make_user,
    find_session_by_token,
):
    user = await make_user()

    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    session = await find_session_by_token(token)
    assert session is not None
    assert session.user_id == user.id


async def test_login_does_not_store_plain_token(
    auth_service: AuthService,
    make_user,
    read_token,
):
    user = await make_user()

    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    assert (await read_token(user.id)).session_token != token


async def test_login_session_expires_after_configured_ttl(
    auth_service: AuthService,
    make_user,
    find_session_by_token,
):
    user = await make_user()
    before = get_current_datetime()

    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    after = get_current_datetime()
    session = await find_session_by_token(token)
    assert before + SESSION_TTL <= session.expired_at <= after + SESSION_TTL


async def test_repeated_login_replaces_previous_session(
    auth_service: AuthService,
    make_user,
    find_session_by_token,
):
    # Одна сессия на пользователя: новый вход вытесняет предыдущий
    user = await make_user()
    first_token = await auth_service.login_user(user.email, TEST_PASSWORD)

    second_token = await auth_service.login_user(user.email, TEST_PASSWORD)

    assert second_token != first_token
    assert await find_session_by_token(first_token) is None
    assert (await find_session_by_token(second_token)).user_id == user.id


async def test_repeated_login_extends_expired_session(
    auth_service: AuthService,
    make_user,
    make_session_token,
    find_session_by_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, expired_at=get_current_datetime() - timedelta(days=1))

    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    assert (await find_session_by_token(token)).expired_at > get_current_datetime()


async def test_login_does_not_touch_other_users_sessions(
    auth_service: AuthService,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=other.id, token_hash="other")

    await auth_service.login_user(user.email, TEST_PASSWORD)

    assert (await read_token(other.id)).session_token == "other"


async def test_login_with_wrong_password_raises(
    auth_service: AuthService,
    make_user,
    read_token,
):
    user = await make_user()

    with pytest.raises(PasswordsNotMatchException):
        await auth_service.login_user(user.email, "WrongPassword123!")

    assert await read_token(user.id) is None


async def test_login_with_unknown_email_raises(auth_service: AuthService, make_user):
    await make_user(email="user@example.com")

    with pytest.raises(UserNotFoundException):
        await auth_service.login_user("missing@example.com", TEST_PASSWORD)


async def test_login_email_is_case_sensitive(auth_service: AuthService, make_user):
    await make_user(email="user@example.com")

    with pytest.raises(UserNotFoundException):
        await auth_service.login_user("User@example.com", TEST_PASSWORD)


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_login_of_inactive_user_raises(
    auth_service: AuthService,
    make_user,
    read_token,
    state: dict,
):
    user = await make_user(**state)

    with pytest.raises(UserNotActiveException):
        await auth_service.login_user(user.email, TEST_PASSWORD)

    assert await read_token(user.id) is None


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_login_of_inactive_user_with_wrong_password_does_not_reveal_state(
    auth_service: AuthService,
    make_user,
    state: dict,
):
    # Без верного пароля нельзя узнать, что аккаунт удалён — ошибка как у обычного неверного пароля
    user = await make_user(**state)

    with pytest.raises(PasswordsNotMatchException):
        await auth_service.login_user(user.email, "WrongPassword123!")


async def test_concurrent_logins_of_same_user_both_succeed(
    make_user,
    session_maker: async_sessionmaker[AsyncSession],
    find_session_by_token,
):
    # Два устройства входят одновременно; в приложении у каждого запроса своя сессия БД
    user = await make_user()

    def new_service(session: AsyncSession) -> AuthService:
        return AuthService(
            user_repo=UserRepository(db_session=session),
            token_repo=TokenRepository(db_session=session),
        )

    async def login() -> str:
        async with session_maker() as session:
            return await new_service(session).login_user(user.email, TEST_PASSWORD)

    # Окно гонки узкое — повторяем, чтобы порядок «оба не нашли сессию» успел случиться
    for _ in range(20):
        async with session_maker() as session:
            await new_service(session).logout_user(user.id)

        tokens = await asyncio.gather(login(), login())

        # Ни один вход не падает, а живой остаётся ровно одна сессия
        sessions = [await find_session_by_token(token) for token in tokens]
        assert sum(session is not None for session in sessions) == 1


# ------------------------------------------------------------------------ logout_user


async def test_logout_ends_session(
    auth_service: AuthService,
    make_user,
    find_session_by_token,
):
    user = await make_user()
    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    await auth_service.logout_user(user.id)

    assert await find_session_by_token(token) is None


async def test_logout_without_session_is_noop(auth_service: AuthService, make_user):
    user = await make_user()

    await auth_service.logout_user(user.id)


async def test_logout_does_not_touch_other_users_sessions(
    auth_service: AuthService,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id)
    await make_session_token(user_id=other.id, token_hash="other")

    await auth_service.logout_user(user.id)

    assert (await read_token(other.id)).session_token == "other"


async def test_user_can_log_in_again_after_logout(
    auth_service: AuthService,
    make_user,
    find_session_by_token,
):
    user = await make_user()
    await auth_service.login_user(user.email, TEST_PASSWORD)
    await auth_service.logout_user(user.id)

    token = await auth_service.login_user(user.email, TEST_PASSWORD)

    assert (await find_session_by_token(token)).user_id == user.id
