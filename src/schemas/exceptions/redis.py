from .base import AppBaseException


class BaseRedisException(AppBaseException):
    pass


class RedisStartupException(BaseRedisException):
    pass