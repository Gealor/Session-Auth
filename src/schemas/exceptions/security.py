from .base import AppBaseException


class SecurityAuthBaseException(AppBaseException):
    pass


class PasswordsNotMatchException(SecurityAuthBaseException):
    pass


class UserEmailAlreadyExistsException(SecurityAuthBaseException):
    pass


class UserNotActiveException(SecurityAuthBaseException):
    pass
