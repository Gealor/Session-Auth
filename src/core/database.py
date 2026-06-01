from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from .config import settings

engine = create_async_engine(
    url=settings.database.db_url,
    echo=settings.database.db_echo,
)

async_session_maker = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False
)


async def db_session_getter():
    async with async_session_maker() as session:
        yield session
