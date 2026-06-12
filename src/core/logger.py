import logging
from .config import settings


logging.basicConfig(
    level=settings.log.level,
    format=settings.log.LOG_DEFAULT_FORMAT,
    datefmt=settings.log.datefmt,
)
logging.getLogger("sqlalchemy").propagate = False # чтобы SQLAlchemy не дублировал логи в основной логгер приложения

log = logging.getLogger(__name__)
log_uvicorn = logging.getLogger("uvicorn.error")
