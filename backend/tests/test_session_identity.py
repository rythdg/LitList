"""Task 1A tests, SPEC.md §15.1: "`session_id` generation is CSPRNG-sourced
and rotates on privilege escalation (§9.1) — not just 'a cookie gets set.'"
"""

from __future__ import annotations

import secrets as _secrets

from sqlmodel import Session as DBSession

from app.models.entities import QueueDecision, SearchSession, ZoteroConnection
from app.models.entities import Session as SessionRow
from app.models.identity import rotate_session
from app.models.ids import generate_session_id


def test_generate_session_id_uses_csprng(monkeypatch) -> None:
    """Asserts the CSPRNG *source*, not just "looks random" — patches
    `secrets.token_urlsafe` and confirms `generate_session_id` actually
    calls through to it rather than e.g. `random`/`uuid1`/a counter."""
    calls: list[int] = []

    def fake_token_urlsafe(nbytes: int) -> str:
        calls.append(nbytes)
        return "fixed-value-for-test"

    monkeypatch.setattr(_secrets, "token_urlsafe", fake_token_urlsafe)
    # generate_session_id imports `secrets` at module scope in ids.py, so
    # patch the same attribute it actually calls.
    from app.models import ids

    monkeypatch.setattr(ids.secrets, "token_urlsafe", fake_token_urlsafe)

    result = ids.generate_session_id()

    assert result == "fixed-value-for-test"
    assert calls == [32]  # >=256 bits of entropy per §9.1


def test_generate_session_id_is_high_entropy_and_unique() -> None:
    ids_seen = {generate_session_id() for _ in range(200)}
    assert len(ids_seen) == 200  # no collisions across 200 draws
    for sid in list(ids_seen)[:5]:
        # token_urlsafe(32) => 43 chars of base64url, well above any
        # sequential/timestamp-derived identifier's length/shape.
        assert len(sid) >= 40


def test_rotate_session_issues_new_id_and_migrates_linked_rows(db_engine) -> None:
    with DBSession(db_engine) as db:
        old_session = SessionRow()
        db.add(old_session)
        db.commit()
        db.refresh(old_session)
        old_id = old_session.session_id

        search_session = SearchSession(session_id=old_id, query="ketamine depression")
        decision = QueueDecision(session_id=old_id, pmid="12345", position=0)
        db.add(search_session)
        db.add(decision)
        db.commit()

        # The moment of privilege escalation: a ZoteroConnection is created.
        connection = ZoteroConnection(
            session_id=old_id,
            zotero_user_id="999",
            oauth_token="ciphertext-token",
            oauth_token_secret="ciphertext-secret",
        )
        db.add(connection)
        db.commit()

        new_session = rotate_session(db, old_session)

        assert new_session.session_id != old_id
        assert len(new_session.session_id) >= 40

        # Old session row is gone — rotation invalidates the fixation target.
        assert db.get(SessionRow, old_id) is None

        # Every FK-linked row now points at the new id.
        from sqlmodel import select

        refreshed_connection = db.exec(
            select(ZoteroConnection).where(ZoteroConnection.session_id == new_session.session_id)
        ).first()
        refreshed_search_session = db.exec(
            select(SearchSession).where(SearchSession.session_id == new_session.session_id)
        ).first()
        refreshed_decision = db.exec(
            select(QueueDecision).where(QueueDecision.session_id == new_session.session_id)
        ).first()

        assert refreshed_connection is not None
        assert refreshed_connection.zotero_user_id == "999"
        assert refreshed_search_session is not None
        assert refreshed_search_session.query == "ketamine depression"
        assert refreshed_decision is not None
        assert refreshed_decision.pmid == "12345"

        # Nothing is left behind under the old id.
        assert (
            db.exec(select(ZoteroConnection).where(ZoteroConnection.session_id == old_id)).first()
            is None
        )
