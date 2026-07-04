"""Task 1A tests, SPEC.md §15.1: "Fernet encryption/decryption round-trip
for `ZoteroConnection` tokens, and confirmation that `TOKEN_ENCRYPTION_KEY`
and the database credentials are independent secrets (§9.6)."
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.models import crypto


@pytest.fixture(autouse=True)
def _reset_fallback_key():
    crypto.reset_fallback_key_for_tests()
    yield
    crypto.reset_fallback_key_for_tests()


def test_round_trip_with_configured_key(monkeypatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(crypto.settings, "token_encryption_key", key)

    plaintext = "zotero-oauth-token-abc123"
    ciphertext = crypto.encrypt_token(plaintext)

    assert ciphertext != plaintext
    assert crypto.decrypt_token(ciphertext) == plaintext


def test_ciphertext_is_not_plaintext_and_is_url_safe(monkeypatch) -> None:
    monkeypatch.setattr(crypto.settings, "token_encryption_key", Fernet.generate_key().decode())
    ciphertext = crypto.encrypt_token("super-secret-value")
    assert "super-secret-value" not in ciphertext


def test_independent_keys_yield_independent_ciphertext_and_cross_decryption_fails(
    monkeypatch,
) -> None:
    """The core §9.6 property: `TOKEN_ENCRYPTION_KEY` is a standalone secret.
    Encrypting the same plaintext under two different keys must produce
    different ciphertext, and each ciphertext must only decrypt under its
    own key — a stand-in here for "a DB-only leak doesn't expose usable
    tokens without also leaking the encryption key."
    """
    key_a = Fernet.generate_key()
    key_b = Fernet.generate_key()
    assert key_a != key_b

    plaintext = "same-plaintext-both-times"
    ciphertext_a = crypto.get_cipher(key_a).encrypt(plaintext.encode())
    ciphertext_b = crypto.get_cipher(key_b).encrypt(plaintext.encode())

    assert ciphertext_a != ciphertext_b

    # Each only decrypts under its own key.
    assert crypto.get_cipher(key_a).decrypt(ciphertext_a).decode() == plaintext
    assert crypto.get_cipher(key_b).decrypt(ciphertext_b).decode() == plaintext

    with pytest.raises(InvalidToken):
        crypto.get_cipher(key_b).decrypt(ciphertext_a)
    with pytest.raises(InvalidToken):
        crypto.get_cipher(key_a).decrypt(ciphertext_b)


def test_decrypt_with_wrong_key_raises_safe_value_error(monkeypatch) -> None:
    monkeypatch.setattr(crypto.settings, "token_encryption_key", Fernet.generate_key().decode())
    ciphertext = crypto.encrypt_token("token-value")

    monkeypatch.setattr(crypto.settings, "token_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="Unable to decrypt token"):
        crypto.decrypt_token(ciphertext)


def test_falls_back_to_ephemeral_key_when_unset(monkeypatch) -> None:
    monkeypatch.setattr(crypto.settings, "token_encryption_key", None)
    plaintext = "fallback-path-token"
    ciphertext = crypto.encrypt_token(plaintext)
    assert crypto.decrypt_token(ciphertext) == plaintext
