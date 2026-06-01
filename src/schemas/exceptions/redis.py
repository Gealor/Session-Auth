from schemas.exceptions.base import AppBaseException


class BaseRedisException(AppBaseException):
    pass


class RedisStartupException(BaseRedisException):
    pass