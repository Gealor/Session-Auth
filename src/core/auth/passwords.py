import asyncio
import hashlib

import bcrypt

def _prehash(password: str | bytes) -> bytes:
    """Привести пароль любой длины к 32 байтам для bcrypt."""
    if isinstance(password, str):
        password = password.encode("utf-8")
    
    hash_pw = hashlib.sha256(password)
    return hash_pw.digest()

async def hash_password(
    password: str,
) -> bytes:
    """Захэшировать пароль с помощью bcrypt в отдельном потоке.

    Args:
        password (str): Пароль в открытом виде.

    Returns:
        bytes: bcrypt-хэш пароля (вместе с солью).
    """
    salt = bcrypt.gensalt()
    pwd_bytes: bytes = _prehash(password)
    return await asyncio.to_thread(bcrypt.hashpw, pwd_bytes, salt) 
# bcrypt имеет относительно медленные операции и тяжеловесные, также является C-расширением, поэтому GIL отпускается


async def compare_hashed_passwords(
    entered_password: str | bytes,
    hashed_password: bytes,
) -> bool:
    """Проверить пароль на соответствие bcrypt-хэшу в отдельном потоке.

    Args:
        entered_password (bytes | str): Введённый пароль в кодировке UTF-8, либо в строке
        hashed_password (bytes): Сохранённый bcrypt-хэш.

    Returns:
        bool: True, если пароль совпадает с хэшем.
    """
    if isinstance(entered_password, str):
        entered_password = entered_password.encode("utf-8")

    entered_password_hash = _prehash(entered_password)
    return await asyncio.to_thread(bcrypt.checkpw, entered_password_hash, hashed_password)
