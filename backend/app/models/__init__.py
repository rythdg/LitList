"""SQLModel entities + session-identity primitives (BuildPlan.md Task 1A,
SPEC.md §9). Re-exports the public surface so callers can do
`from app.models import Session, ZoteroConnection, rotate_session, ...`
without needing to know the internal module split (`entities.py` for
tables, `ids.py` for CSPRNG/timestamp helpers, `identity.py` for rotation,
`crypto.py` for Fernet token encryption).
"""

from __future__ import annotations

from app.models.crypto import decrypt_token, encrypt_token
from app.models.entities import (
    DecidedVia,
    DecisionState,
    Paper,
    QueueDecision,
    SearchSession,
    Session,
    SortOrder,
    SwipeBehavior,
    ZoteroConnection,
    ZoteroExport,
)
from app.models.identity import rotate_session
from app.models.ids import generate_session_id, utcnow

__all__ = [
    "DecidedVia",
    "DecisionState",
    "Paper",
    "QueueDecision",
    "SearchSession",
    "Session",
    "SortOrder",
    "SwipeBehavior",
    "ZoteroConnection",
    "ZoteroExport",
    "decrypt_token",
    "encrypt_token",
    "generate_session_id",
    "rotate_session",
    "utcnow",
]
