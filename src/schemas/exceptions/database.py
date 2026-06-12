from asyncpg import UniqueViolationError

from .base import AppBaseException


class BaseDatabaseException(AppBaseException):
    pass

class DatabaseException(BaseDatabaseException):
    pass

class DatabaseStartupException(BaseDatabaseException):
    pass

class UniqueException(BaseDatabaseException):
    def __init__(self, exc: UniqueViolationError):
        self.exc = exc

    def _extract_field_name(self) -> str:
        detail = self.exc.detail
        field = detail.split("(")[1].split(")")[0] if detail else "unknown"
        return field

    def __str__(self):
        return self._extract_field_name()
    

