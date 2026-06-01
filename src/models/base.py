from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs # чтобы можно было подгружать связанные сущности так await table.awaitable_attrs.child


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True
