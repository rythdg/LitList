"""Task 3A tests for `GET /saved` and `DELETE /saved/{pmid}` (SPEC.md
§10.4, §5.4, §4.7)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from app.middleware.session import SessionIdentityMiddleware, reset_fallback_cookie_secret_for_tests
from app.models.entities import DecidedVia, DecisionState, Paper, QueueDecision
from app.models.entities import Session as SessionRow
from app.routes.saved import router as saved_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(saved_router, prefix="/api/v1")
    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _reset_cookie_secret(db_engine):
    reset_fallback_cookie_secret_for_tests()
    SQLModel.metadata.create_all(db_engine)


def _seed(db_engine) -> str:
    with DBSession(db_engine) as db:
        session = SessionRow()
        db.add(session)
        db.add(Paper(pmid="1", title="Interesting paper"))
        db.add(Paper(pmid="2", title="Skipped paper"))
        db.add(
            QueueDecision(
                session_id=session.session_id,
                pmid="1",
                position=0,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session.session_id,
                pmid="2",
                position=1,
                decision=DecisionState.not_interested,
            )
        )
        db.commit()
        return session.session_id


@pytest.mark.asyncio
async def test_get_saved_returns_only_interested_papers(db_engine) -> None:
    session_id = _seed(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.get("/api/v1/saved")

    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == ["1"]


@pytest.mark.asyncio
async def test_delete_saved_sets_not_interested_not_hard_delete(db_engine) -> None:
    session_id = _seed(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.delete("/api/v1/saved/1")

    assert response.status_code == 200

    with DBSession(db_engine) as db:
        row = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session_id, QueueDecision.pmid == "1"
            )
        ).one()
        assert row.decision == DecisionState.not_interested
        assert row.decided_via == DecidedVia.manual_remove


@pytest.mark.asyncio
async def test_delete_saved_not_found_when_not_currently_saved(db_engine) -> None:
    session_id = _seed(db_engine)
    app = _make_app()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.delete("/api/v1/saved/2")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_saved_cross_session_isolation(db_engine) -> None:
    """§9.1/§9.2's session-scoping is the actual security boundary
    between two anonymous users' Saved Lists — mirrors Task 3C's
    `test_export_never_leaks_another_sessions_saved_papers` pattern: two
    independent `httpx.AsyncClient` instances (separate cookie jars, real
    `session_id`s issued by the middleware) against the same app/DB, with
    both sessions saving an *overlapping* PMID so a leak would be as
    visible as possible."""
    app = _make_app()
    with DBSession(db_engine) as db:
        session_a = SessionRow()
        session_b = SessionRow()
        db.add(session_a)
        db.add(session_b)
        db.add(Paper(pmid="1", title="Session A only"))
        db.add(Paper(pmid="2", title="Session B only"))
        db.add(Paper(pmid="3", title="Shared overlapping PMID"))
        db.add(
            QueueDecision(
                session_id=session_a.session_id,
                pmid="1",
                position=0,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_b.session_id,
                pmid="2",
                position=0,
                decision=DecisionState.interested,
            )
        )
        # Both sessions independently saved the SAME PMID — each has its
        # own row (distinct session_id).
        db.add(
            QueueDecision(
                session_id=session_a.session_id,
                pmid="3",
                position=1,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_b.session_id,
                pmid="3",
                position=1,
                decision=DecisionState.interested,
            )
        )
        db.commit()
        session_a_id = session_a.session_id
        session_b_id = session_b.session_id

    from app.middleware.session import _sign

    async with await _client(app) as client_a, await _client(app) as client_b:
        client_a.cookies.set("litlist_session", _sign(session_a_id))
        client_b.cookies.set("litlist_session", _sign(session_b_id))

        response_a = await client_a.get("/api/v1/saved")
        response_b = await client_b.get("/api/v1/saved")

        assert {item["pmid"] for item in response_a.json()["items"]} == {"1", "3"}
        assert {item["pmid"] for item in response_b.json()["items"]} == {"2", "3"}

        # Session A un-saving the shared PMID must not affect session B's
        # own `interested` row for that same PMID.
        delete_response = await client_a.delete("/api/v1/saved/3")
        assert delete_response.status_code == 200

        response_b_after = await client_b.get("/api/v1/saved")
        assert {item["pmid"] for item in response_b_after.json()["items"]} == {"2", "3"}

        # Session A can never delete session B's exclusive saved PMID "2".
        cross_delete = await client_a.delete("/api/v1/saved/2")
        assert cross_delete.status_code == 404

    with DBSession(db_engine) as db:
        b_row = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session_b_id, QueueDecision.pmid == "2"
            )
        ).one()
        assert b_row.decision == DecisionState.interested
