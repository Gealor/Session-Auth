import asyncio

import pytest

from src.core.auth.passwords import compare_hashed_passwords, hash_password

PASSWORD = "TestPassword123!"


async def _verify(password: str, password_hash: bytes) -> bool:
    return await compare_hashed_passwords(password.encode("utf-8"), password_hash)


async def test_hash_does_not_contain_plain_password():
    password_hash = await hash_password(PASSWORD)

    assert PASSWORD.encode("utf-8") not in password_hash


async def test_hash_verifies_against_original_password():
    password_hash = await hash_password(PASSWORD)

    assert await _verify(PASSWORD, password_hash)


async def test_same_password_gets_different_hashes():
    first_hash = await hash_password(PASSWORD)
    second_hash = await hash_password(PASSWORD)

    assert first_hash != second_hash
    # Оба хэша при этом остаются валидными для одного и того же пароля
    assert await _verify(PASSWORD, first_hash)
    assert await _verify(PASSWORD, second_hash)


@pytest.mark.parametrize(
    "wrong_password",
    [
        pytest.param("WrongPassword123!", id="other-password"),
        pytest.param(PASSWORD.lower(), id="different-case"),
        pytest.param(PASSWORD[:-1], id="missing-last-char"),
        pytest.param(PASSWORD + " ", id="trailing-space"),
        pytest.param("", id="empty"),
    ],
)
async def test_wrong_password_is_rejected(wrong_password: str):
    password_hash = await hash_password(PASSWORD)

    assert not await _verify(wrong_password, password_hash)


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("ПарольНаКириллице1", id="cyrillic"),
        pytest.param("pässwörd-ñ-✓-🔑", id="unicode-symbols"),
    ],
)
async def test_non_ascii_password_round_trip(password: str):
    password_hash = await hash_password(password)

    assert await _verify(password, password_hash)


async def test_long_passwords_with_common_prefix_are_distinguished():
    # bcrypt учитывает только первые 72 байта; пароли, различающиеся дальше,
    # не должны считаться одинаковыми
    prefix = "a" * 72
    password_hash = await hash_password(prefix + "-first")

    assert not await _verify(prefix + "-second", password_hash)


async def test_hashing_does_not_block_event_loop():
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.005)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    try:
        password_hash = await hash_password(PASSWORD)
        await _verify(PASSWORD, password_hash)
    finally:
        ticker_task.cancel()

    # Пока считается bcrypt, цикл событий продолжает обслуживать другие задачи
    assert ticks > 0
