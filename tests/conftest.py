import asyncio
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from datetime import datetime, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.redis import RedisContainer
from testcontainers.postgres import PostgresContainer

from src.core.auth.passwords import hash_password
from src.core.date_now import get_current_datetime
from src.models import Base
from src.models.sessions import SessionToken
from src.models.user import User
from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.repositories.session_repository import TokenRepository
from src.repositories.user_repository import UserRepository

TEST_PASSWORD = "TestPassword123!"
# Хэшируем функцией приложения, чтобы хэш не разъехался с её форматом (пре-хэш и т.п.).
# На уровне модуля цикла событий ещё нет, поэтому asyncio.run безопасен
TEST_PASSWORD_HASH = asyncio.run(hash_password(TEST_PASSWORD)).decode("utf-8")


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
def make_user(session_maker: async_sessionmaker[AsyncSession]) -> Callable[..., Awaitable[User]]:
    # Своя сессия: подготовка данных не делит identity map с проверяемым кодом,
    # и rollback внутри репозитория не протухает объекты, созданные в тесте
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
        async with session_maker() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user

    return _make_user


@pytest.fixture()
def make_session_token(
    session_maker: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[SessionToken]]:
    async def _make_session_token(
        *,
        user_id: int,
        token_hash: str | None = None,
        expired_at: datetime | None = None,
    ) -> SessionToken:
        record = SessionToken(
            user_id=user_id,
            session_token=token_hash or f"hash-{uuid.uuid4().hex}",
            expired_at=expired_at or get_current_datetime() + timedelta(days=1),
        )
        async with session_maker() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

        return record

    return _make_session_token


@pytest.fixture()
def user_repo(async_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session=async_session)


@pytest.fixture()
def token_repo(async_session: AsyncSession) -> TokenRepository:
    return TokenRepository(db_session=async_session)


# ----------------------------------------------------------------------------- Redis


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture(scope="function")
async def redis_client(redis_container: RedisContainer) -> AsyncGenerator[Redis, None]:
    # Как в src/core/redis_client.py: без decode_responses, значения приходят в bytes
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(redis_container.port)),
    )
    await client.flushdb()

    yield client

    await client.aclose()


@pytest.fixture()
def verification_token_repo(redis_client: Redis) -> VerificationTokenRepository:
    return VerificationTokenRepository(redis=redis_client)
