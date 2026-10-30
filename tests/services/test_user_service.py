import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.auth.passwords import compare_hashed_passwords
from src.core.date_now import get_current_datetime
from src.models.user import User
from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.schemas.exceptions.database import UniqueException
from src.schemas.exceptions.email_verification import InvalidVerificationTokenException
from src.schemas.exceptions.users import (
    NewPasswordMatchWithOldException,
    UserAlreadyVerifiedException,
    UserNotDeletedException,
    UserNotFoundException,
)
from src.schemas.response_schemas import ResponseSchema
from src.schemas.user_schemas import UserRead, UserUpdate
from src.services.user_service import UserService
from tests.conftest import TEST_PASSWORD

MISSING_ID = 999_999
NEW_PASSWORD = "BrandNewPassword456!"

INACTIVE_STATES = [
    pytest.param({"is_active": False}, id="inactive-without-deleted-at"),
    pytest.param({"is_active": False, "deleted_at": get_current_datetime()}, id="deleted"),
]


async def _password_matches(password: str, password_hash: str) -> bool:
    return await compare_hashed_passwords(password, password_hash.encode("utf-8"))


# ------------------------------------------------------------------------ update_user


async def test_update_user_returns_updated_profile(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user(nickname="old")

    result = await user_service.update_user(user.id, UserUpdate(nickname="new"))

    assert isinstance(result, UserRead)
    assert result.id == user.id
    assert result.nickname == "new"
    assert result.email == user.email
    assert (await read_user(user.id)).nickname == "new"


async def test_update_user_with_empty_data_keeps_profile(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user(nickname="old")

    result = await user_service.update_user(user.id, UserUpdate())

    assert result.nickname == "old"
    assert (await read_user(user.id)).nickname == "old"


async def test_update_missing_user_raises_not_found(user_service: UserService):
    with pytest.raises(UserNotFoundException):
        await user_service.update_user(MISSING_ID, UserUpdate(nickname="new"))


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_update_inactive_user_raises_not_found(
    user_service: UserService,
    make_user,
    read_user,
    state: dict,
):
    user = await make_user(nickname="old", **state)

    with pytest.raises(UserNotFoundException):
        await user_service.update_user(user.id, UserUpdate(nickname="new"))

    assert (await read_user(user.id)).nickname == "old"


async def test_update_to_taken_nickname_raises(
    user_service: UserService,
    make_user,
    read_user,
):
    await make_user(nickname="taken")
    user = await make_user(nickname="mine")

    with pytest.raises(UniqueException):
        await user_service.update_user(user.id, UserUpdate(nickname="taken"))

    assert (await read_user(user.id)).nickname == "mine"


# ------------------------------------------------------------------- delete_self_user


async def test_delete_self_soft_deletes_user_and_ends_session(
    user_service: UserService,
    make_user,
    make_session_token,
    read_user,
    read_token,
):
    user = await make_user()
    await make_session_token(user_id=user.id)

    result = await user_service.delete_self_user(user.id)

    assert isinstance(result, ResponseSchema)
    persisted = await read_user(user.id)
    assert not persisted.is_active
    assert persisted.deleted_at is not None
    assert await read_token(user.id) is None


async def test_delete_self_without_session(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()

    await user_service.delete_self_user(user.id)

    assert not (await read_user(user.id)).is_active


async def test_delete_self_does_not_touch_other_users(
    user_service: UserService,
    make_user,
    make_session_token,
    read_user,
    read_token,
):
    user = await make_user()
    other = await make_user()
    await make_session_token(user_id=user.id)
    await make_session_token(user_id=other.id, token_hash="other")

    await user_service.delete_self_user(user.id)

    assert (await read_user(other.id)).is_active
    assert (await read_token(other.id)).session_token == "other"


# --------------------------------------------------------------- restore_deleted_user


async def test_restore_deleted_user(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user(is_active=False, deleted_at=get_current_datetime())

    result = await user_service.restore_deleted_user(user.id)

    assert isinstance(result, ResponseSchema)
    persisted = await read_user(user.id)
    assert persisted.is_active
    assert persisted.deleted_at is None


async def test_delete_then_restore_round_trip(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user(nickname="keeper")

    await user_service.delete_self_user(user.id)
    await user_service.restore_deleted_user(user.id)

    persisted = await read_user(user.id)
    assert persisted.is_active
    assert persisted.deleted_at is None
    assert persisted.nickname == "keeper"


async def test_restore_missing_user_raises_not_found(user_service: UserService):
    with pytest.raises(UserNotFoundException):
        await user_service.restore_deleted_user(MISSING_ID)


async def test_restore_active_user_raises_not_deleted(
    user_service: UserService,
    make_user,
):
    user = await make_user()

    with pytest.raises(UserNotDeletedException):
        await user_service.restore_deleted_user(user.id)


# ------------------------------------------------------------------------ verify_user


async def test_verify_user_marks_email_verified(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
    read_user,
):
    user = await make_user()
    await verification_token_repo.save_verification_token(user.id, "token-1")

    await user_service.verify_user("token-1")

    assert (await read_user(user.id)).is_verified


async def test_verify_user_does_not_touch_other_users(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
    read_user,
):
    user = await make_user()
    other = await make_user()
    await verification_token_repo.save_verification_token(user.id, "token-1")

    await user_service.verify_user("token-1")

    assert not (await read_user(other.id)).is_verified


async def test_verify_user_token_is_one_time(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
):
    user = await make_user()
    await verification_token_repo.save_verification_token(user.id, "token-1")
    await user_service.verify_user("token-1")

    with pytest.raises(InvalidVerificationTokenException):
        await user_service.verify_user("token-1")


async def test_verify_user_with_unknown_token_raises(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()

    with pytest.raises(InvalidVerificationTokenException):
        await user_service.verify_user("unknown")

    assert not (await read_user(user.id)).is_verified


async def test_verify_already_verified_user_raises(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
):
    user = await make_user(is_verified=True)
    await verification_token_repo.save_verification_token(user.id, "token-1")

    with pytest.raises(UserAlreadyVerifiedException):
        await user_service.verify_user("token-1")


async def test_verify_user_that_no_longer_exists_raises_not_found(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
    session_maker: async_sessionmaker[AsyncSession],
):
    user = await make_user()
    await verification_token_repo.save_verification_token(user.id, "token-1")
    async with session_maker() as session:
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()

    with pytest.raises(UserNotFoundException):
        await user_service.verify_user("token-1")


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_verify_inactive_user_raises_not_found(
    user_service: UserService,
    verification_token_repo: VerificationTokenRepository,
    make_user,
    read_user,
    state: dict,
):
    # Токен выдан, а потом аккаунт удалили: молча «успешно»
    # ничего не сделать нельзя — вызывающий код должен узнать, что email не подтверждён
    user = await make_user(**state)
    await verification_token_repo.save_verification_token(user.id, "token-1")

    with pytest.raises(UserNotFoundException):
        await user_service.verify_user("token-1")

    assert not (await read_user(user.id)).is_verified


# --------------------------------------------------------------- update_user_password


async def test_update_password_replaces_password(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()

    await user_service.update_user_password(user.id, NEW_PASSWORD)

    persisted = await read_user(user.id)
    assert await _password_matches(NEW_PASSWORD, persisted.password)
    assert not await _password_matches(TEST_PASSWORD, persisted.password)


async def test_update_password_stores_hash_not_plain_password(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()

    await user_service.update_user_password(user.id, NEW_PASSWORD)

    assert NEW_PASSWORD not in (await read_user(user.id)).password


async def test_update_password_accepts_long_password(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()
    long_password = "п" * 100  # 200 байт в UTF-8 — больше лимита bcrypt

    await user_service.update_user_password(user.id, long_password)

    assert await _password_matches(long_password, (await read_user(user.id)).password)


async def test_update_password_to_same_password_raises(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()

    with pytest.raises(NewPasswordMatchWithOldException):
        await user_service.update_user_password(user.id, TEST_PASSWORD)

    assert (await read_user(user.id)).password == user.password


async def test_update_password_of_missing_user_raises_not_found(user_service: UserService):
    with pytest.raises(UserNotFoundException):
        await user_service.update_user_password(MISSING_ID, NEW_PASSWORD)


async def test_update_password_does_not_touch_other_users(
    user_service: UserService,
    make_user,
    read_user,
):
    user = await make_user()
    other = await make_user()

    await user_service.update_user_password(user.id, NEW_PASSWORD)

    assert (await read_user(other.id)).password == other.password
