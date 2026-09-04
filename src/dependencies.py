from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.repositories.session_repository import TokenRepository
from src.repositories.user_repository import UserRepository
from src.core.database import db_session_getter
from src.core.redis_client import get_redis_client
from src.services.auth_service import AuthService
from src.services.email_verification import EmailVerificationService
from src.services.user_service import UserService


def get_user_repo(db: AsyncSession = Depends(db_session_getter)) -> UserRepository:
    return UserRepository(db_session=db)

def get_session_repo(db: AsyncSession = Depends(db_session_getter)) -> TokenRepository:
    return TokenRepository(db_session=db)

def get_verification_token_repo(redis: Redis = Depends(get_redis_client)) -> VerificationTokenRepository:
    return VerificationTokenRepository(redis=redis)


def get_email_verification_service(
    verification_token_repo: VerificationTokenRepository = Depends(get_verification_token_repo),
) -> EmailVerificationService:
    return EmailVerificationService(verification_token_repo=verification_token_repo)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
    token_repo: TokenRepository = Depends(get_session_repo),
) -> AuthService:
    return AuthService(user_repo=user_repo, token_repo=token_repo)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repo),
    token_repo: TokenRepository = Depends(get_session_repo),
    verification_token_repo: VerificationTokenRepository = Depends(get_verification_token_repo)
) -> UserService:
    return UserService(
        user_repo=user_repo, 
        verification_token_repo=verification_token_repo, 
        token_repo=token_repo
    )
