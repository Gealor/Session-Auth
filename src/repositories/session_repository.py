from datetime import datetime

from dateutil.tz import UTC
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from src.models.sessions import SessionToken
from src.core.logger import log
from src.schemas.exceptions.database import DatabaseException
from src.schemas.exceptions.token import SessionTokenNotFoundException


class TokenRepository:
    def __init__(self, db_session: AsyncSession):
        """Инициализировать репозиторий сессионных токенов.

        Args:
            db_session (AsyncSession): Асинхронная сессия SQLAlchemy.
        """
        self.db_session = db_session

    def _load_user(self, stmt: Select) -> Select:
        # joinedload подгружает связи с помощью соедниения (join), а selectinload с помощью второго select (зачастую применятся при отношении ...-ко-многим)
        """Добавить к запросу подгрузку связанного пользователя через JOIN.

        Args:
            stmt (Select): Исходный SELECT-запрос по SessionToken.

        Returns:
            Select: Запрос с опцией joinedload(SessionToken.user).
        """
        loaded_user_stmt = stmt.options(joinedload(SessionToken.user))
        return loaded_user_stmt


    async def get_token_by_user_id(self, user_id: int, load_user: bool = False) -> str | None:
        """Получить хэш сессионного токена пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            load_user (bool, optional): Подгрузить связанного пользователя.
                Defaults to False.

        Returns:
            str | None: Хэш токена или None, если сессии нет.
        """
        stmt = select(SessionToken.session_token).where(SessionToken.user_id == user_id)

        if load_user:
            stmt = self._load_user(stmt)

        token_hash = await self.db_session.scalar(stmt)
        if token_hash is None:
            return None

        return token_hash

    async def get_token_by_hash(self, token_hash: str, load_user: bool = False) -> SessionToken | None:
        """Получить запись сессии по хэшу токена.

        Args:
            token_hash (str): Хэш сессионного токена.
            load_user (bool, optional): Подгрузить связанного пользователя тем же
                запросом. Defaults to False.

        Returns:
            SessionToken | None: Запись сессии или None, если не найдена.
        """
        stmt = select(SessionToken).where(SessionToken.session_token == token_hash)

        if load_user:
            stmt = self._load_user(stmt)

        record = await self.db_session.scalar(stmt)
        if token_hash is None:
            return None

        return record

    async def create_record(self, user_id: int, token_hash: str, expired_at: datetime) -> None:
        """Создать запись сессионного токена.

        Args:
            user_id (int): Идентификатор пользователя.
            token_hash (str): Хэш сессионного токена.
            expired_at (datetime): Момент истечения сессии.

        Raises:
            DatabaseException: Ошибка целостности при сохранении записи.
        """
        record = SessionToken(
            user_id=user_id,
            session_token=token_hash,
            expired_at=expired_at,
        )
        self.db_session.add(record)
        try:
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            log.error("Failed to add session_token: %s", e)
            raise DatabaseException

        await self.db_session.refresh(record)
        log.info("Add session token for user with id: %s", record.user_id)

    async def update_record(
        self, user_id: int, token: str, expired_at: datetime
    ) -> str:
        """Обновить сессионный токен пользователя.

        Args:
            user_id (int): Идентификатор пользователя.
            token (str): Новый хэш сессионного токена.
            expired_at (datetime): Новый момент истечения сессии.

        Raises:
            SessionTokenNotFoundException: У пользователя нет записи сессии.
            DatabaseException: Ошибка целостности при сохранении записи.

        Returns:
            str: Сохранённый хэш токена.
        """
        stmt = (
            update(SessionToken)
            .values(session_token=token, expired_at=expired_at)
            .where(SessionToken.user_id == user_id)
            .returning(SessionToken)
        )

        record = await self.db_session.scalar(stmt)
        if record is None:
            raise SessionTokenNotFoundException

        try:
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            log.error("Failed to update session_token: %s", e)
            raise DatabaseException

        await self.db_session.refresh(record)
        log.info("Update session token for user_id=%d", record.user_id)
        return record.session_token

    async def delete_token(self, user_id: int) -> None:
        """Удалить сессионный токен пользователя.

        Args:
            user_id (int): Идентификатор пользователя.

        Raises:
            DatabaseException: Ошибка целостности при удалении записи.
        """
        stmt = delete(SessionToken).where(SessionToken.user_id == user_id)
        await self.db_session.execute(stmt)

        try:
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            log.error("Failed to delete session token: %s", e)
            raise DatabaseException

        log.info("Deleted session token with user_id=%d", user_id)
    
    async def delete_expired_at_tokens(self) -> int:
        """Удалить все сессионные токены с истёкшим сроком действия.

        Raises:
            DatabaseException: Ошибка целостности при удалении записей.

        Returns:
            int: Количество удалённых записей.
        """
        now = datetime.now(tz=UTC)
        stmt = (
            delete(SessionToken)
            .where(SessionToken.expired_at <= now)
            .returning(SessionToken.session_token)
        )

        try:
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
        except IntegrityError as e:
            await self.db_session.rollback()
            log.error("Failed to delete session token: %s", e)
            raise DatabaseException
        
        count = len(result.all()) if result else 0
        log.info("Deleted expired tokens. Count records: %d", count)
        return count
