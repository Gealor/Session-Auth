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
        """Создать исключение нарушения уникальности.

        Args:
            exc (UniqueViolationError): Исходная ошибка asyncpg.
        """
        self.exc = exc

    def _extract_field_name(self) -> str:
        """Извлечь имя поля из detail ошибки PostgreSQL.

        Returns:
            str: Имя поля, нарушившего уникальность, или "unknown".
        """
        detail = self.exc.detail
        field = detail.split("(")[1].split(")")[0] if detail else "unknown"
        return field

    def __str__(self):
        """Вернуть имя поля, нарушившего уникальность.

        Returns:
            str: Имя поля.
        """
        return self._extract_field_name()
    

