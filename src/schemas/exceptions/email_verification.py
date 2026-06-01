from schemas.exceptions.base import AppBaseException


class BaseEmailVerificationException(AppBaseException):
    pass


class InvalidVerificationTokenException(BaseEmailVerificationException):
    pass