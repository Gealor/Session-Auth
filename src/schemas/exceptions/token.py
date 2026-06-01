from schemas.exceptions.base import AppBaseException


class SessionTokenBaseException(AppBaseException):
    pass


class SessionTokenNotFoundException(SessionTokenBaseException):
    pass


class TokenMismatchException(SessionTokenBaseException):
    pass


class TokensNotMatchException(SessionTokenBaseException):
    pass
