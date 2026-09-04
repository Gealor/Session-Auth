from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins.deleted_at_mixin import DeletedAtMixin
from .mixins.id_pk_mixin import IdPrimaryKeyMixin
from .mixins.updated_at_mixin import UpdatedAtMixin


class User(Base, IdPrimaryKeyMixin, DeletedAtMixin, UpdatedAtMixin):
    __tablename__ = "users"

    nickname: Mapped[str] = mapped_column(nullable=False, unique=True)
    email: Mapped[str] = mapped_column(nullable=False, unique=True)
    password: Mapped[str] = mapped_column(nullable=False)  # тут хранится хэш пароля

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, server_default='false', nullable=False)
