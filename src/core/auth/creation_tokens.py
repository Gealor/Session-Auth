import hashlib
import secrets
from typing import Tuple

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token() -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)
