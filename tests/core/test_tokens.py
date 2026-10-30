import re

import pytest

from src.core.auth.creation_tokens import create_token, hash_token

URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def test_create_token_returns_token_and_its_hash():
    token, token_hash = create_token()

    assert token_hash == hash_token(token)
    assert token_hash != token


def test_token_is_url_safe():
    token, _ = create_token()

    # Токен кладётся в cookie и в ссылку подтверждения email
    assert URL_SAFE.fullmatch(token)


def test_token_has_at_least_256_bits_of_entropy():
    token, _ = create_token()

    # 32 случайных байта в base64url — минимум 43 символа
    assert len(token) >= 43


def test_tokens_are_unique():
    tokens = {create_token()[0] for _ in range(1000)}

    assert len(tokens) == 1000


def test_hash_is_deterministic():
    assert hash_token("some-token") == hash_token("some-token")


def test_different_tokens_get_different_hashes():
    assert hash_token("token-a") != hash_token("token-b")


@pytest.mark.parametrize("token", ["", "short", "x" * 1000, "токен"])
def test_hash_is_hex_sha256(token: str):
    assert HEX_SHA256.fullmatch(hash_token(token))


def test_hash_matches_known_sha256_vector():
    # Алгоритм — часть контракта: в БД хранятся хэши, его смена обнулит все сессии
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    assert hash_token("abc") == expected
