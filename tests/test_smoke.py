"""Проверки самой обвязки тестов: БД поднимается, данные сохраняются и изолируются между тестами."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.user import User

SMOKE_EMAIL = "smoke@example.com"


async def test_database_is_reachable(async_session: AsyncSession) -> None:
    assert await async_session.scalar(text("SELECT 1")) == 1


async def test_schema_is_created(async_session: AsyncSession) -> None:
    tables = await async_session.scalars(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )

    assert {"users", "session_tokens"} <= set(tables)


async def test_make_user_persists_user(
    make_user,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    user = await make_user(email=SMOKE_EMAIL)

    # Читаем из отдельной сессии, чтобы убедиться, что данные закоммичены в БД
    async with session_maker() as other_session:
        persisted = await other_session.get(User, user.id)

    assert persisted is not None
    assert persisted.email == SMOKE_EMAIL
    assert persisted.is_active
    assert not persisted.is_verified


async def test_data_is_isolated_between_tests(async_session: AsyncSession) -> None:
    # Пользователь из предыдущего теста удалён фикстурой clean_db
    count = await async_session.scalar(select(func.count()).select_from(User))

    assert count == 0
