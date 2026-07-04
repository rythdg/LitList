"""Task 3D tests, SPEC.md §10.7 — CORS allow-list, the `CSRFGuard
Middleware` it underwrites, and §10.7's baseline security headers.

Two layers of test here, matching this task's brief:

1. A minimal standalone app (fast, isolated) covering the guard's own
   logic: disallowed origin, non-JSON content-type, the DELETE/no-body
   exemption from the content-type check, and header presence.
2. One integration test against the *real* `app.main.app` — a
   disallowed-origin, non-JSON-content-type `POST /api/v1/search` — that
   asserts a real Wave-1 route's side effect (a `SearchSession` DB row)
   never happened, not just that the HTTP response looks like a
   rejection. This is the literal adversarial scenario this task's brief
   calls out.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from app.clients import get_icite_client, get_pubmed_client
from app.middleware.ratelimit import reset_rate_limit_storage_for_tests
from app.middleware.security import CSRFGuardMiddleware, SecurityHeadersMiddleware, install_cors
from app.middleware.session import _sign, reset_fallback_cookie_secret_for_tests
from app.models.entities import DecisionState, Paper, QueueDecision, SearchSession
from app.models.entities import Session as SessionRow
from tests._fakes import FakeICiteClient, FakePubMedClient, make_esearch_result

_ALLOWED_ORIGIN = "http://localhost:5173"
_DISALLOWED_ORIGIN = "https://evil.example"


def _make_minimal_app() -> FastAPI:
    app = FastAPI()
    # Same order as `app/main.py`: CSRFGuard added first (innermost of
    # these three), CORS next, SecurityHeaders last (outermost) — a
    # request hits SecurityHeaders -> CORS -> CSRFGuard on the way in.
    app.add_middleware(CSRFGuardMiddleware)
    install_cors(app)
    app.add_middleware(SecurityHeadersMiddleware)

    calls = {"n": 0}
    app.state.calls = calls

    @app.post("/api/v1/search")
    def fake_post() -> dict[str, int]:
        calls["n"] += 1
        return {"n": calls["n"]}

    @app.delete("/api/v1/saved/1")
    def fake_delete() -> dict[str, int]:
        calls["n"] += 1
        return {"n": calls["n"]}

    @app.get("/api/v1/queue")
    def fake_get() -> dict[str, bool]:
        return {"ok": True}

    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


async def test_disallowed_origin_is_rejected_before_handler_runs() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search",
            json={"query": "x"},
            headers={"Origin": _DISALLOWED_ORIGIN},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"
    assert app.state.calls["n"] == 0


async def test_non_json_content_type_is_rejected_before_handler_runs() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search",
            content=b'{"query": "x"}',
            headers={"Content-Type": "text/plain", "Origin": _ALLOWED_ORIGIN},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"
    assert app.state.calls["n"] == 0


async def test_disallowed_origin_and_non_json_together_is_rejected() -> None:
    """The realistic CSRF shape: a cross-site "simple" POST with a
    disallowed origin *and* a non-JSON-declared Content-Type."""
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search",
            content=b'{"query": "x"}',
            headers={"Content-Type": "text/plain", "Origin": _DISALLOWED_ORIGIN},
        )

    assert response.status_code == 403
    assert app.state.calls["n"] == 0


async def test_allowed_origin_with_json_body_reaches_the_handler() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search",
            json={"query": "x"},
            headers={"Origin": _ALLOWED_ORIGIN},
        )

    assert response.status_code == 200
    assert app.state.calls["n"] == 1


async def test_request_with_no_origin_header_is_not_rejected() -> None:
    """No `Origin` header (same-origin navigation, curl, a server-to-
    server call) isn't a cross-origin browser request in the first place
    — nothing for the CSRF guard to protect against, so it must pass
    through on that basis (still subject to the Content-Type check)."""
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.post("/api/v1/search", json={"query": "x"})

    assert response.status_code == 200


async def test_delete_with_no_body_and_no_content_type_is_allowed() -> None:
    """§10.7's own note: `DELETE /saved/{pmid}` and `DELETE /zotero/
    connection` never carry a body in this project's real frontend
    contract (`frontend/src/api/client.ts` only sets `Content-Type` when
    a body is passed) — the Content-Type check must not apply to
    `DELETE`, only the Origin allow-list."""
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.delete(
            "/api/v1/saved/1", headers={"Origin": _ALLOWED_ORIGIN}
        )

    assert response.status_code == 200
    assert app.state.calls["n"] == 1


async def test_delete_from_disallowed_origin_is_still_rejected() -> None:
    """Even though `DELETE` is never a CORS-"simple" method (so a real
    browser always preflights it), the Origin allow-list check still
    applies as defense in depth against a non-browser client forging the
    header."""
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.delete(
            "/api/v1/saved/1", headers={"Origin": _DISALLOWED_ORIGIN}
        )

    assert response.status_code == 403
    assert app.state.calls["n"] == 0


async def test_get_requests_are_never_csrf_gated() -> None:
    """Read-only endpoints are exempt from both checks (§10.7's own
    "every *state-changing* endpoint" framing) — a GET from a disallowed
    origin isn't rejected by this guard (though the CORS middleware will
    still withhold `Access-Control-Allow-Origin`, so a real browser can't
    read the response body)."""
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.get("/api/v1/queue", headers={"Origin": _DISALLOWED_ORIGIN})

    assert response.status_code == 200


async def test_security_headers_present_on_success_and_rejection() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        ok_response = await client.get("/api/v1/queue")
        rejected_response = await client.post(
            "/api/v1/search",
            content=b"not json",
            headers={"Content-Type": "text/plain"},
        )

    for response in (ok_response, rejected_response):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in response.headers["content-security-policy"]


async def test_cors_preflight_allows_the_configured_origin() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.options(
            "/api/v1/search",
            headers={
                "Origin": _ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_preflight_omits_headers_for_disallowed_origin() -> None:
    app = _make_minimal_app()
    async with await _client(app) as client:
        response = await client.options(
            "/api/v1/search",
            headers={
                "Origin": _DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------
# Integration test against the real `app.main.app` — the literal
# adversarial scenario this task's brief calls out: a real Wave-1 route's
# DB-write side effect must never happen for a rejected request.
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_shared_state(db_engine):
    reset_fallback_cookie_secret_for_tests()
    reset_rate_limit_storage_for_tests()
    SQLModel.metadata.create_all(db_engine)


async def test_real_search_route_side_effect_never_happens_when_rejected(db_engine) -> None:
    from app.main import app as real_app

    real_app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"])
    )
    real_app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()
    try:
        async with await _client(real_app) as client:
            response = await client.post(
                "/api/v1/search",
                content=b'{"query": "cancer"}',
                headers={"Content-Type": "text/plain", "Origin": _DISALLOWED_ORIGIN},
            )
        assert response.status_code == 403

        with DBSession(db_engine) as db:
            rows = db.exec(select(SearchSession)).all()
        assert rows == []
    finally:
        real_app.dependency_overrides.clear()


def _seed_decision(db_engine, *, decision: DecisionState = DecisionState.pending) -> str:
    """Mirrors `test_decisions_routes.py`'s own seeding helper — a
    `Session` + `Paper` + `QueueDecision` row for a single PMID, returning
    the new session's id so the caller can sign a cookie for it."""
    with DBSession(db_engine) as db:
        session = SessionRow()
        db.add(session)
        db.add(Paper(pmid="1", title="Some paper"))
        db.add(
            QueueDecision(session_id=session.session_id, pmid="1", position=0, decision=decision)
        )
        db.commit()
        return session.session_id


async def test_real_decisions_route_side_effect_never_happens_when_rejected(db_engine) -> None:
    """Tester's TASK 3D VERIFY spot-checked `PATCH /decisions/{pmid}`
    against the real app and found it correctly rejects — pinned here as
    a committed regression test rather than relying on that manual
    verification happening again in the future."""
    from app.main import app as real_app

    session_id = _seed_decision(db_engine)

    async with await _client(real_app) as client:
        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.patch(
            "/api/v1/decisions/1",
            content=b'{"decision": "interested", "decided_via": "swipe"}',
            headers={"Content-Type": "text/plain", "Origin": _DISALLOWED_ORIGIN},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"

    with DBSession(db_engine) as db:
        row = db.exec(select(QueueDecision).where(QueueDecision.pmid == "1")).one()
    assert row.decision == DecisionState.pending
    assert row.decided_via is None


async def test_real_saved_delete_route_side_effect_never_happens_when_rejected(db_engine) -> None:
    """Tester's TASK 3D VERIFY spot-checked `DELETE /saved/{pmid}`
    against the real app and found it correctly rejects — pinned here.
    `DELETE` never carries a body/`Content-Type` in this project's real
    frontend contract (see `security.py`'s docstring), so only the
    disallowed-origin path is exercised for this one."""
    from app.main import app as real_app

    session_id = _seed_decision(db_engine, decision=DecisionState.interested)

    async with await _client(real_app) as client:
        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.delete(
            "/api/v1/saved/1",
            headers={"Origin": _DISALLOWED_ORIGIN},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"

    with DBSession(db_engine) as db:
        row = db.exec(select(QueueDecision).where(QueueDecision.pmid == "1")).one()
    # Still `interested` — `DELETE /saved/{pmid}` would have flipped this
    # to `not_interested` (§4.7) had the request actually reached the
    # handler.
    assert row.decision == DecisionState.interested
