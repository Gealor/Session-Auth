from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins.deleted_at_mixin import DeletedAtMixin
from models.mixins.id_pk_mixin import IdPrimaryKeyMixin
from models.mixins.updated_at_mixin import UpdatedAtMixin


class User(Base, IdPrimaryKeyMixin, DeletedAtMixin, UpdatedAtMixin):
    __tablename__ = "users"

    nickname: Mapped[str] = mapped_column(nullable=False, unique=True)
    email: Mapped[str] = mapped_column(nullable=False, unique=True)
    password: Mapped[str] = mapped_column(nullable=False)  # тут хранится хэш пароля

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, server_default='false', nullable=False)
