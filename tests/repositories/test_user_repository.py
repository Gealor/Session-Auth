
import pytest

from src.core.date_now import get_current_datetime
from src.repositories.user_repository import UserRepository
from src.schemas.exceptions.database import UniqueException
from src.schemas.exceptions.users import UserNotFoundException
from src.schemas.user_schemas import UserRegister, UserUpdate
from tests.conftest import TEST_PASSWORD_HASH

MISSING_ID = 999_999


def _register_data(
    nickname: str = "new_user",
    email: str = "new_user@example.com",
) -> UserRegister:
    return UserRegister(nickname=nickname, email=email, password=TEST_PASSWORD_HASH)


# --------------------------------------------------------------------- get_user_by_id


async def test_get_by_id_returns_existing_user(user_repo: UserRepository, make_user):
    user = await make_user()

    fetched = await user_repo.get_user_by_id(user.id)

    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.email == user.email


async def test_get_by_id_returns_none_for_missing_user(user_repo: UserRepository):
    assert await user_repo.get_user_by_id(MISSING_ID) is None


# ------------------------------------------------------------------ get_user_by_email


async def test_get_by_email_returns_existing_user(user_repo: UserRepository, make_user):
    user = await make_user(email="user@example.com")

    fetched = await user_repo.get_user_by_email("user@example.com")

    assert fetched is not None
    assert fetched.id == user.id


async def test_get_by_email_returns_none_for_missing_user(user_repo: UserRepository, make_user):
    await make_user(email="user@example.com")

    assert await user_repo.get_user_by_email("missing@example.com") is None


async def test_get_by_email_is_case_sensitive(user_repo: UserRepository, make_user):
    await make_user(email="user@example.com")

    assert await user_repo.get_user_by_email("User@example.com") is None


# ------------------------------------------------------------- exclude_inactive (get)

INACTIVE_STATES = [
    pytest.param({"is_active": False}, id="inactive-without-deleted-at"),
    pytest.param({"is_active": False, "deleted_at": get_current_datetime()}, id="deleted"),
]


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_get_excludes_inactive_user_when_requested(
    user_repo: UserRepository,
    make_user,
    state: dict,
):
    user = await make_user(**state)

    assert await user_repo.get_user_by_id(user.id, exclude_inactive=True) is None
    assert await user_repo.get_user_by_email(user.email, exclude_inactive=True) is None


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_get_returns_inactive_user_by_default(
    user_repo: UserRepository,
    make_user,
    state: dict,
):
    user = await make_user(**state)

    assert await user_repo.get_user_by_id(user.id) is not None
    assert await user_repo.get_user_by_email(user.email) is not None


async def test_get_returns_active_user_when_excluding_inactive(
    user_repo: UserRepository,
    make_user,
):
    user = await make_user()

    assert await user_repo.get_user_by_id(user.id, exclude_inactive=True) is not None
    assert await user_repo.get_user_by_email(user.email, exclude_inactive=True) is not None


# ------------------------------------------------------------------------ create_user


async def test_create_user_persists_active_unverified_user(
    user_repo: UserRepository,
    read_user,
):
    data = _register_data()

    await user_repo.create_user(data)

    created = await user_repo.get_user_by_email(data.email)
    assert created is not None

    persisted = await read_user(created.id)
    assert persisted is not None
    assert persisted.nickname == data.nickname
    assert persisted.email == data.email
    # Репозиторий не хэширует пароль — сохраняет то, что передал сервис
    assert persisted.password == data.password
    assert persisted.is_active
    assert not persisted.is_verified
    assert persisted.deleted_at is None


@pytest.mark.parametrize(
    ("duplicate", "field"),
    [
        pytest.param({"email": "taken@example.com"}, "email", id="email"),
        pytest.param({"nickname": "taken"}, "nickname", id="nickname"),
    ],
)
async def test_create_user_with_taken_value_raises_unique_exception(
    user_repo: UserRepository,
    make_user,
    duplicate: dict,
    field: str,
):
    await make_user(nickname="taken", email="taken@example.com")

    with pytest.raises(UniqueException) as exc_info:
        await user_repo.create_user(_register_data(**duplicate))

    # Имя поля уходит клиенту в тексте ошибки
    assert str(exc_info.value) == field


async def test_repository_is_usable_after_failed_create(
    user_repo: UserRepository,
    make_user,
):
    await make_user(email="taken@example.com")
    with pytest.raises(UniqueException):
        await user_repo.create_user(_register_data(email="taken@example.com"))

    await user_repo.create_user(_register_data(email="free@example.com"))

    assert await user_repo.get_user_by_email("free@example.com") is not None


# ---------------------------------------------------------------- update_data_by_dict


async def test_update_by_dict_updates_fields_and_returns_user(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(nickname="old")

    updated = await user_repo.update_data_by_dict(
        user.id, {"nickname": "new", "is_verified": True}
    )

    assert updated is not None
    assert updated.id == user.id
    assert updated.nickname == "new"
    assert updated.is_verified

    persisted = await read_user(user.id)
    assert persisted.nickname == "new"
    assert persisted.is_verified


async def test_update_by_dict_does_not_touch_other_users(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(nickname="target")
    other = await make_user(nickname="other")

    await user_repo.update_data_by_dict(user.id, {"nickname": "changed"})

    assert (await read_user(other.id)).nickname == "other"


async def test_update_by_dict_returns_none_for_missing_user(user_repo: UserRepository):
    assert await user_repo.update_data_by_dict(MISSING_ID, {"nickname": "new"}) is None


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_update_by_dict_skips_inactive_user_when_requested(
    user_repo: UserRepository,
    make_user,
    read_user,
    state: dict,
):
    user = await make_user(nickname="old", **state)

    result = await user_repo.update_data_by_dict(
        user.id, {"nickname": "new"}, exclude_inactive=True
    )

    assert result is None
    assert (await read_user(user.id)).nickname == "old"


async def test_update_by_dict_with_taken_value_raises_unique_exception(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    await make_user(nickname="taken")
    user = await make_user(nickname="mine")

    with pytest.raises(UniqueException) as exc_info:
        await user_repo.update_data_by_dict(user.id, {"nickname": "taken"})

    assert str(exc_info.value) == "nickname"
    assert (await read_user(user.id)).nickname == "mine"


async def test_repository_is_usable_after_failed_update(
    user_repo: UserRepository,
    make_user,
):
    await make_user(nickname="taken")
    user = await make_user(nickname="mine")
    with pytest.raises(UniqueException):
        await user_repo.update_data_by_dict(user.id, {"nickname": "taken"})

    updated = await user_repo.update_data_by_dict(user.id, {"nickname": "free"})

    assert updated is not None
    assert updated.nickname == "free"


# ------------------------------------------------------------------------ update_user


async def test_update_user_changes_nickname(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(nickname="old")

    updated = await user_repo.update_user(user.id, UserUpdate(nickname="new"))

    assert updated.nickname == "new"
    assert (await read_user(user.id)).nickname == "new"


async def test_update_user_with_empty_data_keeps_user_unchanged(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(nickname="old")

    updated = await user_repo.update_user(user.id, UserUpdate())

    assert updated.nickname == "old"
    assert (await read_user(user.id)).nickname == "old"


async def test_update_user_raises_for_missing_user(user_repo: UserRepository):
    with pytest.raises(UserNotFoundException):
        await user_repo.update_user(MISSING_ID, UserUpdate(nickname="new"))


@pytest.mark.parametrize("state", INACTIVE_STATES)
async def test_update_user_raises_for_inactive_user_when_requested(
    user_repo: UserRepository,
    make_user,
    state: dict,
):
    user = await make_user(**state)

    with pytest.raises(UserNotFoundException):
        await user_repo.update_user(user.id, UserUpdate(nickname="new"), exclude_inactive=True)


# ------------------------------------------------------------------------ delete_user


async def test_delete_user_soft_deletes(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user()
    before = get_current_datetime()

    await user_repo.delete_user(user.id)

    after = get_current_datetime()
    persisted = await read_user(user.id)
    # Запись остаётся в БД, но помечена удалённой
    assert persisted is not None
    assert not persisted.is_active
    assert persisted.deleted_at is not None
    assert before <= persisted.deleted_at <= after


async def test_deleted_user_is_hidden_when_excluding_inactive(
    user_repo: UserRepository,
    make_user,
):
    user = await make_user()

    await user_repo.delete_user(user.id)

    assert await user_repo.get_user_by_id(user.id, exclude_inactive=True) is None


async def test_delete_user_does_not_touch_other_users(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user()
    other = await make_user()

    await user_repo.delete_user(user.id)

    persisted_other = await read_user(other.id)
    assert persisted_other.is_active
    assert persisted_other.deleted_at is None


async def test_delete_missing_user_is_noop(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    # Существование пользователя проверяет сервис, репозиторий просто ничего не меняет
    other = await make_user()

    await user_repo.delete_user(MISSING_ID)

    persisted_other = await read_user(other.id)
    assert persisted_other.is_active
    assert persisted_other.deleted_at is None


# ----------------------------------------------------------------------- restore_user


async def test_restore_user_reverts_soft_delete(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(is_active=False, deleted_at=get_current_datetime())

    await user_repo.restore_user(user.id)

    persisted = await read_user(user.id)
    assert persisted.is_active
    assert persisted.deleted_at is None
    assert await user_repo.get_user_by_id(user.id, exclude_inactive=True) is not None


async def test_delete_then_restore_round_trip(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    user = await make_user(nickname="keeper")

    await user_repo.delete_user(user.id)
    await user_repo.restore_user(user.id)

    persisted = await read_user(user.id)
    assert persisted.is_active
    assert persisted.deleted_at is None
    # Остальные данные при удалении и восстановлении не теряются
    assert persisted.nickname == "keeper"
    assert persisted.email == user.email


async def test_restore_missing_user_is_noop(
    user_repo: UserRepository,
    make_user,
    read_user,
):
    # Существование пользователя проверяет сервис, репозиторий просто ничего не меняет
    other = await make_user(is_active=False, deleted_at=get_current_datetime())

    await user_repo.restore_user(MISSING_ID)

    persisted_other = await read_user(other.id)
    assert not persisted_other.is_active
    assert persisted_other.deleted_at is not None
