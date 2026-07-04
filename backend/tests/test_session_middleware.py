"""Task 1A middleware tests, SPEC.md §10.2: cookie issuance for a
brand-new visitor, reuse of an existing valid cookie, and rejection of a
tampered cookie value (falls back to issuing a fresh session rather than
trusting unsigned/forged input).

Uses `https://testserver` as the base URL so httpx's cookie jar will
actually store/replay the `Secure` cookie the middleware sets (§10.2
requires `Secure`, which most HTTP clients — including httpx — refuse to
persist over a plain `http://` origin).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.middleware.session import (
    SESSION_COOKIE_NAME,
    SessionIdentityMiddleware,
    get_current_session,
    reset_fallback_cookie_secret_for_tests,
)
from app.models.entities import Session as SessionRow


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)

    @app.get("/whoami")
    def whoami(request: Request) -> dict[str, str]:
        session = get_current_session(request)
        return {"session_id": session.session_id}

    return app


def _client(db_engine) -> TestClient:
    SQLModel.metadata.create_all(db_engine)
    return TestClient(_make_app(), base_url="https://testserver")


def test_first_request_issues_a_new_session_cookie(db_engine, monkeypatch) -> None:
    reset_fallback_cookie_secret_for_tests()
    client = _client(db_engine)

    response = client.get("/whoami")

    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.cookies
    session_id = response.json()["session_id"]

    with _open_db(db_engine) as db_session:
        row = db_session.get(SessionRow, session_id)
        assert row is not None


def _open_db(engine):
    from sqlmodel import Session as DBSession

    return DBSession(engine)


def test_existing_valid_cookie_is_reused_not_replaced(db_engine) -> None:
    reset_fallback_cookie_secret_for_tests()
    client = _client(db_engine)

    first = client.get("/whoami")
    first_session_id = first.json()["session_id"]
    # TestClient's session persists cookies across requests automatically.
    second = client.get("/whoami")
    second_session_id = second.json()["session_id"]

    assert first_session_id == second_session_id
    # No new Set-Cookie on the second request — the existing one was valid.
    assert SESSION_COOKIE_NAME not in second.cookies


def test_tampered_cookie_is_rejected_and_a_new_session_is_issued(db_engine) -> None:
    reset_fallback_cookie_secret_for_tests()
    client = _client(db_engine)

    first = client.get("/whoami")
    first_session_id = first.json()["session_id"]

    # Tamper with the cookie value client-side.
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-session.deadbeef")
    second = client.get("/whoami")

    assert second.json()["session_id"] != first_session_id
    assert SESSION_COOKIE_NAME in second.cookies
