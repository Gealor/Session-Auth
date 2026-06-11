from datetime import datetime

from dateutil.tz import UTC
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from models.sessions import SessionToken
from core.logger import log
from schemas.exceptions.database import DatabaseException
from schemas.exceptions.token import SessionTokenNotFoundException


class TokenRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    def _load_user(self, stmt: Select) -> Select:
        # joinedload подгружает связи с помощью соедниения (join), а selectinload с помощью второго select (зачастую применятся при отношении ...-ко-многим)
        loaded_user_stmt = stmt.options(joinedload(SessionToken.user))
        return loaded_user_stmt


    async def get_token_by_user_id(self, user_id: int, load_user: bool = False) -> str | None:
        stmt = select(SessionToken.session_token).where(SessionToken.user_id == user_id)

        if load_user:
            stmt = self._load_user(stmt)

        token_hash = await self.db_session.scalar(stmt)
        if token_hash is None:
            return None

        return token_hash

    async def get_token_by_hash(self, token_hash: str, load_user: bool = False) -> SessionToken | None:
        stmt = select(SessionToken).where(SessionToken.session_token == token_hash)

        if load_user:
            stmt = self._load_user(stmt)

        record = await self.db_session.scalar(stmt)
        if token_hash is None:
            return None

        return record

    async def create_record(self, user_id: int, token_hash: str, expired_at: datetime) -> None:
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
