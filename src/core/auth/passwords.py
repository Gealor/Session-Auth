import asyncio

import bcrypt


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
    pwd_bytes: bytes = password.encode("utf-8")
    return await asyncio.to_thread(bcrypt.hashpw, pwd_bytes, salt) 
# bcrypt имеет относительно медленные операции и тяжеловесные, также является C-расширением, поэтому GIL отпускается


async def compare_hashed_passwords(
    entered_password: bytes,
    hashed_password: bytes,
) -> bool:
    """Проверить пароль на соответствие bcrypt-хэшу в отдельном потоке.

    Args:
        entered_password (bytes): Введённый пароль в кодировке UTF-8.
        hashed_password (bytes): Сохранённый bcrypt-хэш.

    Returns:
        bool: True, если пароль совпадает с хэшем.
    """
    return await asyncio.to_thread(bcrypt.checkpw, entered_password, hashed_password)
