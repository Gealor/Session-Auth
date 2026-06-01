from sqlalchemy.orm import Mapped, mapped_column


class IdPrimaryKeyMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
