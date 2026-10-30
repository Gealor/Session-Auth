from collections.abc import Awaitable, Callable
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.date_now import get_current_datetime
from src.models.sessions import SessionToken
from src.models.user import User
from src.repositories.session_repository import TokenRepository
from src.schemas.exceptions.database import DatabaseException
from src.schemas.exceptions.token import SessionTokenNotFoundException

MISSING_ID = 999_999


@pytest.fixture()
def count_tokens(
    session_maker: async_sessionmaker[AsyncSession],
) -> Callable[[], Awaitable[int]]:
    async def _count_tokens() -> int:
        async with session_maker() as session:
            return await session.scalar(select(func.count()).select_from(SessionToken))

    return _count_tokens


def _in(delta: timedelta):
    return get_current_datetime() + delta


# --------------------------------------------------------------- get_token_by_user_id


async def test_get_by_user_id_returns_token_hash(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="hash-1")

    assert await token_repo.get_token_by_user_id(user.id) == "hash-1"


async def test_get_by_user_id_returns_none_without_session(
    token_repo: TokenRepository,
    make_user,
):
    user = await make_user()

    assert await token_repo.get_token_by_user_id(user.id) is None


async def test_get_by_user_id_returns_only_own_token(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id, token_hash="mine")
    await make_session_token(user_id=other.id, token_hash="other")

    assert await token_repo.get_token_by_user_id(user.id) == "mine"


# ------------------------------------------------------------------ get_token_by_hash


async def test_get_by_hash_returns_record(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    expired_at = _in(timedelta(hours=3))
    await make_session_token(user_id=user.id, token_hash="hash-1", expired_at=expired_at)

    record = await token_repo.get_token_by_hash("hash-1")

    assert record is not None
    assert record.user_id == user.id
    assert record.session_token == "hash-1"
    assert record.expired_at == expired_at


async def test_get_by_hash_returns_none_for_unknown_hash(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="hash-1")

    assert await token_repo.get_token_by_hash("unknown") is None


async def test_get_by_hash_with_load_user_returns_loaded_user(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="hash-1")

    record = await token_repo.get_token_by_hash("hash-1", load_user=True)

    # Пользователь должен быть загружен тем же запросом: синхронный доступ
    # к незагруженной связи в async-сессии упал бы с MissingGreenlet
    assert record is not None
    assert record.user.id == user.id
    assert record.user.email == user.email


async def test_get_by_hash_with_load_user_returns_none_for_unknown_hash(
    token_repo: TokenRepository,
):
    assert await token_repo.get_token_by_hash("unknown", load_user=True) is None


async def test_get_returns_expired_session(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    # Проверка срока — забота вызывающего кода (get_current_user), репозиторий запись не прячет
    user = await make_user()
    await make_session_token(
        user_id=user.id, token_hash="expired", expired_at=_in(-timedelta(days=1))
    )

    assert await token_repo.get_token_by_hash("expired") is not None
    assert await token_repo.get_token_by_user_id(user.id) == "expired"


@pytest.mark.parametrize(
    "state",
    [
        pytest.param({"is_active": False}, id="inactive-without-deleted-at"),
        pytest.param({"is_active": False, "deleted_at": get_current_datetime()}, id="deleted"),
    ],
)
async def test_get_by_hash_returns_session_of_inactive_user(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    state: dict,
):
    # Активность пользователя тоже проверяет вызывающий код — ему нужен пользователь из записи
    user = await make_user(**state)
    await make_session_token(user_id=user.id, token_hash="hash-1")

    record = await token_repo.get_token_by_hash("hash-1", load_user=True)

    assert record is not None
    assert record.user.id == user.id
    assert not record.user.is_active


async def test_session_hash_is_unique_across_users(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    # По хэшу сессия ищется на каждом запросе — он должен однозначно указывать на одну сессию
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id, token_hash="same")

    with pytest.raises(DatabaseException):
        await token_repo.create_record(other.id, "same", _in(timedelta(days=1)))


# ---------------------------------------------------------------------- create_record


async def test_create_record_persists_session(
    token_repo: TokenRepository,
    make_user,
    read_token,
):
    user = await make_user()
    expired_at = _in(timedelta(days=1))

    await token_repo.create_record(user.id, "hash-1", expired_at)

    persisted = await read_token(user.id)
    assert persisted is not None
    assert persisted.session_token == "hash-1"
    assert persisted.expired_at == expired_at


async def test_create_second_record_for_same_user_raises(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    # У пользователя одна сессия: повторное создание — ошибка, а не тихая перезапись
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="first")

    with pytest.raises(DatabaseException):
        await token_repo.create_record(user.id, "second", _in(timedelta(days=1)))

    assert (await read_token(user.id)).session_token == "first"


async def test_create_record_for_missing_user_raises(
    token_repo: TokenRepository,
    count_tokens,
):
    with pytest.raises(DatabaseException):
        await token_repo.create_record(MISSING_ID, "hash-1", _in(timedelta(days=1)))

    assert await count_tokens() == 0


async def test_repository_is_usable_after_failed_create(
    token_repo: TokenRepository,
    make_user,
    read_token,
):
    user = await make_user()
    with pytest.raises(DatabaseException):
        await token_repo.create_record(MISSING_ID, "hash-1", _in(timedelta(days=1)))

    await token_repo.create_record(user.id, "hash-2", _in(timedelta(days=1)))

    assert (await read_token(user.id)).session_token == "hash-2"


# ---------------------------------------------------------------------- update_record


async def test_update_record_replaces_hash_and_expiration(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="old", expired_at=_in(timedelta(hours=1)))
    new_expired_at = _in(timedelta(days=1))

    result = await token_repo.update_record(user.id, "new", new_expired_at)

    assert result == "new"
    persisted = await read_token(user.id)
    assert persisted.session_token == "new"
    assert persisted.expired_at == new_expired_at


async def test_old_hash_is_not_found_after_update(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="old")

    await token_repo.update_record(user.id, "new", _in(timedelta(days=1)))

    assert await token_repo.get_token_by_hash("old") is None
    assert await token_repo.get_token_by_hash("new") is not None


async def test_update_record_does_not_touch_other_users(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id, token_hash="mine")
    await make_session_token(user_id=other.id, token_hash="other")

    await token_repo.update_record(user.id, "new", _in(timedelta(days=1)))

    assert (await read_token(other.id)).session_token == "other"


async def test_update_record_to_hash_of_other_user_raises(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id, token_hash="mine")
    await make_session_token(user_id=other.id, token_hash="taken")

    with pytest.raises(DatabaseException):
        await token_repo.update_record(user.id, "taken", _in(timedelta(days=1)))

    assert (await read_token(user.id)).session_token == "mine"
    assert (await read_token(other.id)).session_token == "taken"


async def test_repository_is_usable_after_failed_update(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id, token_hash="mine")
    await make_session_token(user_id=other.id, token_hash="taken")
    with pytest.raises(DatabaseException):
        await token_repo.update_record(user.id, "taken", _in(timedelta(days=1)))

    assert await token_repo.update_record(user.id, "free", _in(timedelta(days=1))) == "free"
    assert (await read_token(user.id)).session_token == "free"


async def test_update_record_without_session_raises_not_found(
    token_repo: TokenRepository,
    make_user,
    count_tokens,
):
    user = await make_user()

    with pytest.raises(SessionTokenNotFoundException):
        await token_repo.update_record(user.id, "new", _in(timedelta(days=1)))

    assert await count_tokens() == 0


# ----------------------------------------------------------------------- delete_token


async def test_delete_token_removes_session(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id, token_hash="hash-1")

    await token_repo.delete_token(user.id)

    assert await read_token(user.id) is None
    assert await token_repo.get_token_by_hash("hash-1") is None


async def test_delete_token_does_not_touch_other_users(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id)
    await make_session_token(user_id=other.id, token_hash="other")

    await token_repo.delete_token(user.id)

    assert (await read_token(other.id)).session_token == "other"


async def test_delete_token_without_session_is_noop(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    count_tokens,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=other.id)

    await token_repo.delete_token(user.id)

    assert await count_tokens() == 1


# ----------------------------------------------------------- delete_expired_at_tokens


async def test_delete_expired_removes_only_expired_sessions(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    expired_users = [await make_user() for _ in range(2)]
    active_user = await make_user()
    for user in expired_users:
        await make_session_token(user_id=user.id, expired_at=_in(-timedelta(minutes=1)))
    await make_session_token(user_id=active_user.id, expired_at=_in(timedelta(days=1)))

    deleted = await token_repo.delete_expired_at_tokens()

    assert deleted == 2
    for user in expired_users:
        assert await read_token(user.id) is None
    assert await read_token(active_user.id) is not None


async def test_delete_expired_respects_boundary(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    read_token,
):
    # Сессии в секундах от текущего момента: ошибка в сравнении или часовом поясе
    # сместила бы границу и удалила не те записи
    just_expired = await make_user()
    almost_expired = await make_user()
    await make_session_token(user_id=just_expired.id, expired_at=_in(-timedelta(seconds=1)))
    await make_session_token(user_id=almost_expired.id, expired_at=_in(timedelta(seconds=30)))

    assert await token_repo.delete_expired_at_tokens() == 1
    assert await read_token(just_expired.id) is None
    assert await read_token(almost_expired.id) is not None


async def test_delete_expired_returns_zero_when_nothing_expired(
    token_repo: TokenRepository,
    make_user,
    make_session_token,
    count_tokens,
):
    user = await make_user()
    await make_session_token(user_id=user.id, expired_at=_in(timedelta(days=1)))

    assert await token_repo.delete_expired_at_tokens() == 0
    assert await count_tokens() == 1


async def test_delete_expired_on_empty_table_returns_zero(token_repo: TokenRepository):
    assert await token_repo.delete_expired_at_tokens() == 0


# ------------------------------------------------------------------------ foreign key


async def test_session_is_removed_with_user(
    make_user,
    make_session_token,
    read_token,
    session_maker: async_sessionmaker[AsyncSession],
):
    # Жёсткое удаление пользователя (ON DELETE CASCADE) не оставляет висящих сессий
    user = await make_user()
    await make_session_token(user_id=user.id)

    async with session_maker() as session:
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()

    assert await read_token(user.id) is None
