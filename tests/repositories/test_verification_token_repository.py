import asyncio

import pytest
from redis.asyncio import Redis

from src.core.config import settings
from src.repositories.redis.verification_token_repository import VerificationTokenRepository
from src.schemas.exceptions.email_verification import InvalidVerificationTokenException

USER_ID = 1
OTHER_USER_ID = 2


async def _ttls(redis: Redis) -> list[int]:
    """TTL всех ключей в Redis — без знания о том, как репозиторий их называет."""
    return [await redis.ttl(key) async for key in redis.scan_iter()]


# ------------------------------------------------------------ save + verify (happy path)


async def test_saved_token_returns_its_user(verification_token_repo: VerificationTokenRepository):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    assert await verification_token_repo.verify_and_consume_token("token-1") == USER_ID


async def test_tokens_of_different_users_are_independent(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    await verification_token_repo.save_verification_token(OTHER_USER_ID, "token-2")

    assert await verification_token_repo.verify_and_consume_token("token-2") == OTHER_USER_ID
    assert await verification_token_repo.verify_and_consume_token("token-1") == USER_ID


# ------------------------------------------------------------------------- invalid token


async def test_unknown_token_is_rejected(verification_token_repo: VerificationTokenRepository):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token("unknown")


async def test_unknown_token_does_not_consume_valid_one(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token("unknown")

    assert await verification_token_repo.verify_and_consume_token("token-1") == USER_ID


async def test_empty_storage_rejects_any_token(
    verification_token_repo: VerificationTokenRepository,
):
    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token("token-1")


# ---------------------------------------------------------------------------- one-time


async def test_token_cannot_be_used_twice(verification_token_repo: VerificationTokenRepository):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    await verification_token_repo.verify_and_consume_token("token-1")

    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token("token-1")


async def test_concurrent_verification_succeeds_only_once(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    results = await asyncio.gather(
        *(verification_token_repo.verify_and_consume_token("token-1") for _ in range(10)),
        return_exceptions=True,
    )

    successes = [result for result in results if result == USER_ID]
    failures = [r for r in results if isinstance(r, InvalidVerificationTokenException)]
    assert len(successes) == 1
    assert len(failures) == len(results) - 1


async def test_consumed_token_leaves_no_data(
    verification_token_repo: VerificationTokenRepository,
    redis_client: Redis,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    await verification_token_repo.verify_and_consume_token("token-1")

    assert await redis_client.dbsize() == 0


async def test_user_can_get_new_token_after_consuming(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    await verification_token_repo.verify_and_consume_token("token-1")

    await verification_token_repo.save_verification_token(USER_ID, "token-2")

    assert await verification_token_repo.verify_and_consume_token("token-2") == USER_ID


# ------------------------------------------------------------------------- replacement


async def test_new_token_invalidates_previous_one(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "old")
    await verification_token_repo.save_verification_token(USER_ID, "new")

    with pytest.raises(InvalidVerificationTokenException):
        await verification_token_repo.verify_and_consume_token("old")
    assert await verification_token_repo.verify_and_consume_token("new") == USER_ID


async def test_replacing_token_does_not_touch_other_users(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    await verification_token_repo.save_verification_token(OTHER_USER_ID, "token-2")

    await verification_token_repo.save_verification_token(USER_ID, "token-3")

    assert await verification_token_repo.verify_and_consume_token("token-2") == OTHER_USER_ID


async def test_replaced_tokens_leave_no_data_after_consuming(
    verification_token_repo: VerificationTokenRepository,
    redis_client: Redis,
):
    for token in ("token-1", "token-2", "token-3"):
        await verification_token_repo.save_verification_token(USER_ID, token)

    await verification_token_repo.verify_and_consume_token("token-3")

    assert await redis_client.dbsize() == 0


async def test_concurrent_saves_leave_only_one_valid_token(
    verification_token_repo: VerificationTokenRepository,
):
    # Пользователь дважды быстро нажал «отправить письмо»
    tokens = [f"token-{i}" for i in range(10)]
    await asyncio.gather(
        *(verification_token_repo.save_verification_token(USER_ID, token) for token in tokens)
    )

    valid = []
    for token in tokens:
        try:
            await verification_token_repo.verify_and_consume_token(token)
        except InvalidVerificationTokenException:
            continue
        valid.append(token)

    assert len(valid) == 1


async def test_saving_same_token_again_keeps_it_valid(
    verification_token_repo: VerificationTokenRepository,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    assert await verification_token_repo.verify_and_consume_token("token-1") == USER_ID


# --------------------------------------------------------------------------------- TTL


async def test_all_stored_data_expires(
    verification_token_repo: VerificationTokenRepository,
    redis_client: Redis,
):
    await verification_token_repo.save_verification_token(USER_ID, "token-1")

    ttls = await _ttls(redis_client)

    # -1 — ключ без срока жизни, такой мусор остался бы в Redis навсегда
    assert ttls
    assert all(0 < ttl <= settings.mailing.ttl_seconds for ttl in ttls)


async def test_replacing_token_refreshes_expiration(
    verification_token_repo: VerificationTokenRepository,
    redis_client: Redis,
):
    await verification_token_repo.save_verification_token(USER_ID, "old")
    await verification_token_repo.save_verification_token(USER_ID, "new")

    ttls = await _ttls(redis_client)

    assert ttls
    assert all(0 < ttl <= settings.mailing.ttl_seconds for ttl in ttls)
