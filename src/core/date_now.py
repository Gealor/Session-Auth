from datetime import UTC, datetime

def get_current_datetime() -> datetime:
    """Возвращает текущую дату в UTC

    Returns:
        datetime: Дата и время в формате UTC
    """
    return datetime.now(tz=UTC)