import re

import pytest
from redis.asyncio import Redis

from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.schemas.exceptions.email_verification import InvalidVerificationTokenException
from src.schemas.exceptions.users import UserAlreadyVerifiedException
from src.services.email_verification import EmailVerificationService
from src.services.user_service import UserService

USER_ID = 1
OTHER_USER_ID = 2
URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


async def test_issued_token_verifies_its_user(
    email_verification_service: EmailVerificationService,
    verification_token_repo: VerificationTokenRepository,
):
    token = await email_verification_service.save_verification_token(USER_ID, is_verified=False)

    assert await verification_token_repo.verify_and_consume_token(token) == USER_ID


async def test_issued_token_is_url_safe_and_long_enough(
    email_verification_service: EmailVerificationService,
):
    token = await email_verification_service.save_verification_token(USER_ID, is_verified=False)

    # Токен уходит в ссылку из письма и вводится вручную
    assert URL_SAFE.fullmatch(token)
    assert len(token) >= 43  # не меньше 256 бит случайности


async def test_already_verified_user_gets_no_token(
    email_verification_service: EmailVerificationService,
    redis_client: Redis,
):
    with pytest.raises(UserAlreadyVerifiedException):
        await email_verification_service.save_verification_token(USER_ID, is_verified=True)

    assert await redis_client.dbsize() == 0


async def test_new_token_invalidates_previous_one(
    email_verification_service: EmailVerificationService,
    verification_token_repo: VerificationTokenRepository,
):
    first = await email_verification_service.save_verification_token(USER_ID, is_verified=False)
    second = await email_verification_service.save_verification_token(USER_ID, is_verified=False)

    assert first != second
    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token(first)
    assert await verification_token_repo.verify_and_consume_token(second) == USER_ID


async def test_tokens_of_different_users_are_independent(
    email_verification_service: EmailVerificationService,
    verification_token_repo: VerificationTokenRepository,
):
    token = await email_verification_service.save_verification_token(USER_ID, is_verified=False)
    other = await email_verification_service.save_verification_token(
        OTHER_USER_ID, is_verified=False
    )

    assert token != other
    assert await verification_token_repo.verify_and_consume_token(other) == OTHER_USER_ID
    assert await verification_token_repo.verify_and_consume_token(token) == USER_ID


async def test_full_flow_issue_token_then_verify_user(
    email_verification_service: EmailVerificationService,
    user_service: UserService,
    make_user,
    read_user,
):
    # Сквозной сценарий: письмо с токеном → переход по ссылке → email подтверждён
    user = await make_user()

    token = await email_verification_service.save_verification_token(
        user.id, is_verified=user.is_verified
    )
    await user_service.verify_user(token)

    assert (await read_user(user.id)).is_verified
