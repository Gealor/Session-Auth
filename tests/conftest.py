import asyncio
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from datetime import datetime

import bcrypt
import pytest
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from src.models import Base
from src.models.user import User

TEST_PASSWORD = "TestPassword123!"
# hash_password из приложения асинхронный, на уровне модуля хэшируем напрямую через bcrypt
TEST_PASSWORD_HASH = bcrypt.hashpw(
    TEST_PASSWORD.encode("utf-8"),
    bcrypt.gensalt()
).decode("utf-8")


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:17") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def db_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url(driver="asyncpg")


@pytest.fixture(scope="session")
def db_schema(db_url: str) -> None:
    """Схема создаётся один раз на весь прогон."""

    async def _create_schema() -> None:
        engine = create_async_engine(db_url, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create_schema())


@pytest.fixture(scope="function")
async def engine(db_url: str, db_schema: None) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(db_url)

    yield engine

    await engine.dispose()


# На маленьких данных DELETE будет быстрее TRUNCATE
@pytest.fixture(scope="function")
async def clean_db(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(table.delete())


@pytest.fixture(scope="function")
def session_maker(
    engine: AsyncEngine,
    clean_db: None,
) -> async_sessionmaker[AsyncSession]:
    # Те же параметры, что у async_session_maker в src/core/database.py
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest.fixture(scope="function")
async def async_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
        yield session


@pytest.fixture()
def make_user(async_session: AsyncSession) -> Callable[..., Awaitable[User]]:
    async def _make_user(
        *,
        nickname: str | None = None,
        email: str | None = None,
        password_hash: str = TEST_PASSWORD_HASH,
        is_active: bool = True,
        is_verified: bool = False,
        deleted_at: datetime | None = None,
    ) -> User:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            nickname=nickname or f"user-{suffix}",
            email=email or f"user-{suffix}@example.com",
            password=password_hash,
            is_active=is_active,
            is_verified=is_verified,
            deleted_at=deleted_at,
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        return user

    return _make_user
