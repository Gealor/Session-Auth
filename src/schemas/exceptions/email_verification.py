from .base import AppBaseException


class BaseEmailVerificationException(AppBaseException):
    pass


class InvalidVerificationTokenException(BaseEmailVerificationException):
    pass