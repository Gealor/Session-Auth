import hashlib
import secrets
from typing import Tuple

def hash_token(token: str) -> str:
    """Захэшировать токен алгоритмом SHA-256.

    Args:
        token (str): Токен в открытом виде.

    Returns:
        str: Хэш токена в шестнадцатеричном виде.
    """
    hash_bytes = hashlib.sha256(token.encode("utf-8")) # быстрая операция, очень быстрая

    return hash_bytes.hexdigest()


def create_token() -> Tuple[str, str]:
    """Сгенерировать случайный URL-safe токен и его хэш.

    Returns:
        Tuple[str, str]: Токен в открытом виде и его SHA-256 хэш.
    """
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)

    return token, token_hash
