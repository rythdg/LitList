"""Application-level Fernet encryption for `ZoteroConnection.oauth_token` /
`oauth_token_secret` (SPEC.md §9.6, BuildPlan.md Task 1A).

Deliberately *not* "database encryption" — these two fields are encrypted
before insert and decrypted after read, using a `TOKEN_ENCRYPTION_KEY` that
is a completely separate secret from the Turso database credentials. This
is the property §9.6 calls out explicitly: a Turso-only leak does not by
itself expose usable Zotero tokens, since the attacker would additionally
need this key, which is never colocated with DB credentials.

Key sourcing: `TOKEN_ENCRYPTION_KEY` is a local-dev/prod secret that is
generated once (via `Fernet.generate_key()`) and set as a real environment
variable for any deployment that needs encrypted data to survive a process
restart (see `backend/.env.example`). It is intentionally never hand-authored
or committed. If it's unset (fresh local checkout, CI), this module falls
back to a per-process ephemeral key generated at first use, logged loudly as
a warning — this keeps `pytest`/local dev usable out of the box without ever
writing a real secret into source control, at the cost of that ephemeral
key (and anything encrypted under it) not surviving a process restart. That
trade-off is fine for dev/test and explicitly NOT fine for any persistent
deployment, which is why it's a loud warning, not a silent default.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_fallback_key: bytes | None = None


def _get_key() -> bytes:
    if settings.token_encryption_key:
        return settings.token_encryption_key.encode()

    global _fallback_key
    if _fallback_key is None:
        logger.warning(
            "TOKEN_ENCRYPTION_KEY is not set — generating an ephemeral "
            "per-process Fernet key. Fine for local dev/tests; NOT fine for "
            "any deployment where encrypted Zotero tokens must survive a "
            "restart (a fresh ephemeral key cannot decrypt data written "
            "under a previous one). Set TOKEN_ENCRYPTION_KEY in the "
            "environment for any persistent deployment (see "
            "backend/.env.example)."
        )
        _fallback_key = Fernet.generate_key()
    return _fallback_key


def reset_fallback_key_for_tests() -> None:
    """Test helper only — clears the cached ephemeral key so a test can
    exercise the "two independent keys yield independent ciphertext"
    property without a real env var configured."""
    global _fallback_key
    _fallback_key = None


def get_cipher(key: bytes | None = None) -> Fernet:
    """Return a `Fernet` instance for the given key, or the configured/
    fallback `TOKEN_ENCRYPTION_KEY` if none is given."""
    return Fernet(key if key is not None else _get_key())


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext OAuth token/secret for storage (§9.6). Returns an
    opaque, ASCII-safe string suitable for a text column."""
    return get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a value previously produced by `encrypt_token`. Raises
    `ValueError` (never leaks the underlying `InvalidToken`/key details) if
    the ciphertext is corrupted or was encrypted under a different key —
    callers surface this as a safe, pre-written error per §10.3, never the
    raw exception."""
    try:
        return get_cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt token: wrong key or corrupted ciphertext.") from exc
