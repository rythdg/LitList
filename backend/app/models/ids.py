"""Tiny, dependency-free helpers shared across `app/models/*` — split out on
its own so `entities.py` (SQLModel tables) and `identity.py` (rotation logic,
which needs the tables) don't form an import cycle: entities need
`generate_session_id` as a field default, identity needs the entities
themselves.

SPEC.md §9.1 pins the concrete requirements this module satisfies:
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware UTC now — used for every `created_at`/`updated_at`-style
    field so stored timestamps are unambiguous regardless of server locale."""
    return datetime.now(UTC)


def generate_session_id() -> str:
    """CSPRNG-sourced opaque session token (SPEC.md §9.1).

    `secrets.token_urlsafe(32)` draws from `os.urandom` (a CSPRNG), yielding
    32 bytes / 256 bits of entropy, url-safe-base64-encoded. This is the
    *only* acceptable source for `session_id` per §9.1 — never a sequential
    ID, a timestamp-derived value, or `random`/`uuid4` (uuid4 also uses a
    CSPRNG under the hood on CPython, but `secrets` is the stdlib's explicit,
    documented "use this for security tokens" API, so it's the one this
    project standardizes on to make the intent unambiguous at every call
    site).
    """
    return secrets.token_urlsafe(32)
