"""Task 3A tests for `PATCH /decisions/{pmid}` (SPEC.md §10.4, §4.1/§4.6/
§4.7). Purely local DB state — no PubMed/iCite fakes needed."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from app.middleware.session import SessionIdentityMiddleware, reset_fallback_cookie_secret_for_tests
from app.models.entities import DecisionState, Paper, QueueDecision
from app.models.entities import Session as SessionRow
from app.routes.decisions import router as decisions_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(decisions_router, prefix="/api/v1")
    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _reset_cookie_secret(db_engine):
    reset_fallback_cookie_secret_for_tests()
    SQLModel.metadata.create_all(db_engine)


def _seed_decision(db_engine) -> str:
    with DBSession(db_engine) as db:
        session = SessionRow()
        db.add(session)
        db.add(Paper(pmid="1", title="Some paper"))
        db.add(QueueDecision(session_id=session.session_id, pmid="1", position=0))
        db.commit()
        return session.session_id


@pytest.mark.asyncio
async def test_patch_decision_updates_state(db_engine) -> None:
    session_id = _seed_decision(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.patch(
            "/api/v1/decisions/1",
            json={"decision": "interested", "decided_via": "swipe"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "interested"
    assert body["decided_via"] == "swipe"
    assert body["decided_at"] is not None

    with DBSession(db_engine) as db:
        row = db.exec(select(QueueDecision).where(QueueDecision.pmid == "1")).one()
        assert row.decision == DecisionState.interested


@pytest.mark.asyncio
async def test_patch_decision_not_found_for_unknown_pmid(db_engine) -> None:
    session_id = _seed_decision(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.patch(
            "/api/v1/decisions/does-not-exist",
            json={"decision": "interested", "decided_via": "swipe"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_patch_decision_not_found_for_other_sessions_pmid(db_engine) -> None:
    """A decision belonging to a *different* session must not be
    updatable — session scoping (§9.1/§10.2), not global by PMID."""
    _seed_decision(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        # Fresh, unrelated session (no cookie set) — brand new visitor.
        response = await client.patch(
            "/api/v1/decisions/1",
            json={"decision": "interested", "decided_via": "swipe"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "insert_actor_row_first",
    [True, False],
    ids=["actor_row_inserted_first", "other_session_row_inserted_first"],
)
async def test_decisions_cross_session_isolation_with_overlapping_pmid(
    db_engine, insert_actor_row_first: bool
) -> None:
    """Stronger version of the above, per tester's TASK 3A VERIFY note:
    two genuinely *established* sessions (real cookies from the
    middleware, not "no cookie at all") each hold their own
    `QueueDecision` row on the SAME overlapping PMID — session A patching
    "its" PMID must only ever mutate its own row, never session B's, and
    session B's independent read must be completely unaffected
    (mirrors Task 3C's cross-session export test pattern).

    **Direction-independence (per tester's follow-up review):** a first
    version of this test always inserted session A's row before session
    B's, which meant `.first()` would happen to return the correct row
    even if the `session_id` filter in `decisions.py` were deleted
    entirely (SQLite's default row order follows insertion/rowid) — the
    test would pass for the wrong reason. Parametrizing over which
    session's row is inserted first closes that blind spot: with the
    filter removed, the `other_session_row_inserted_first` case would
    patch session B's row instead and this test would correctly fail
    regardless of insertion order. (Verified manually: temporarily
    deleting the `QueueDecision.session_id == session.session_id` clause
    from `update_decision` makes exactly this parametrized case fail,
    while leaving the filter in place keeps both cases green.)"""
    app = _make_app()
    with DBSession(db_engine) as db:
        session_a = SessionRow()
        session_b = SessionRow()
        db.add(Paper(pmid="1", title="Shared overlapping PMID"))
        if insert_actor_row_first:
            db.add(session_a)
            db.add(session_b)
            db.add(QueueDecision(session_id=session_a.session_id, pmid="1", position=0))
            db.add(QueueDecision(session_id=session_b.session_id, pmid="1", position=0))
        else:
            db.add(session_b)
            db.add(session_a)
            db.add(QueueDecision(session_id=session_b.session_id, pmid="1", position=0))
            db.add(QueueDecision(session_id=session_a.session_id, pmid="1", position=0))
        db.commit()
        session_a_id = session_a.session_id
        session_b_id = session_b.session_id

    from app.middleware.session import _sign

    # The actor is always session A — only the row insertion order varies.
    async with await _client(app) as client_a, await _client(app) as client_b:
        client_a.cookies.set("litlist_session", _sign(session_a_id))
        client_b.cookies.set("litlist_session", _sign(session_b_id))

        response = await client_a.patch(
            "/api/v1/decisions/1",
            json={"decision": "interested", "decided_via": "swipe"},
        )
        assert response.status_code == 200

    with DBSession(db_engine) as db:
        row_a = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session_a_id, QueueDecision.pmid == "1"
            )
        ).one()
        row_b = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session_b_id, QueueDecision.pmid == "1"
            )
        ).one()
        assert row_a.decision == DecisionState.interested
        # Session B's identical-PMID row is untouched — still pending —
        # regardless of which row was inserted first.
        assert row_b.decision == DecisionState.pending
        assert row_b.decided_via is None


@pytest.mark.asyncio
async def test_patch_decision_validation_error_on_bad_body(db_engine) -> None:
    session_id = _seed_decision(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.patch(
            "/api/v1/decisions/1",
            json={"decision": "not-a-real-state", "decided_via": "swipe"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "Traceback" not in response.text
