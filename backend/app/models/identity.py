"""Session rotation-on-privilege-escalation (SPEC.md §9.1, BuildPlan.md
Task 1A).

`generate_session_id`/`utcnow` live in `app/models/ids.py` (imported by
`entities.py` as field defaults); this module holds the one function that
actually needs both the ID generator *and* the entity tables together:
`rotate_session`, called the moment a `ZoteroConnection` is created for a
`Session` (§9.1, §8.2 step 5). Rotation reissues the `session_id`, moves
every FK-linked row onto the new id, and deletes the old `Session` row —
closing the session-fixation gap §9.1 describes: without rotation, an
attacker who got a victim to use an attacker-known `session_id` before the
victim connected Zotero would inherit that connection once the victim
connects it, since the identifier would never have changed across the trust
boundary.

Task 1C's OAuth callback handler (Wave 2) is the intended caller: after
inserting the new `ZoteroConnection` row, it calls `rotate_session` and then
`app.middleware.session.set_session_cookie` with the returned session's new
id, so the response the victim's browser sees carries the rotated cookie.
"""

from __future__ import annotations

from sqlmodel import Session as DBSession
from sqlmodel import select

from app.models.entities import (
    QueueDecision,
    SearchSession,
    Session,
    ZoteroConnection,
    ZoteroExport,
)
from app.models.ids import generate_session_id, utcnow

# Every entity FK-scoped to `Session.session_id` (§9.3) that must be
# repointed during rotation. Kept as an explicit tuple (rather than
# introspecting the schema) so adding a new session-scoped entity later is a
# deliberate, visible edit here, not an implicit side effect.
_SESSION_SCOPED_MODELS = (ZoteroConnection, SearchSession, QueueDecision, ZoteroExport)


def rotate_session(db_session: DBSession, old_session: Session) -> Session:
    """Reissue `old_session`'s `session_id` under a new CSPRNG value,
    migrating every session-scoped row (`ZoteroConnection`, `SearchSession`,
    `QueueDecision`, `ZoteroExport`) onto the new id, then deleting the old
    `Session` row. Returns the new `Session` row.

    Callers are responsible for committing the cookie update to the HTTP
    response (`app.middleware.session.set_session_cookie`) — this function
    only touches the database.
    """
    new_session = Session(
        session_id=generate_session_id(),
        created_at=old_session.created_at,
        last_seen_at=utcnow(),
    )
    db_session.add(new_session)
    db_session.flush()  # new_session.session_id must exist before FK repoints

    for model in _SESSION_SCOPED_MODELS:
        rows = db_session.exec(
            select(model).where(model.session_id == old_session.session_id)
        ).all()
        for row in rows:
            row.session_id = new_session.session_id
            db_session.add(row)

    db_session.delete(old_session)
    db_session.commit()
    db_session.refresh(new_session)
    return new_session
