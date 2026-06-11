from schemas.exceptions.base import AppBaseException


class BaseUserException(AppBaseException):
    pass


class UserNotFoundException(BaseUserException):
    pass


class UserNotDeletedException(BaseUserException):
    pass


class UserAlreadyVerifiedException(BaseUserException):
    pass


class NewPasswordMatchWithOldException(BaseUserException):
    pass