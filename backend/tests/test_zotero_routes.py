"""Task 3B tests, SPEC.md §10.4's zotero rows, §8 (all), §9.6, plus
CONTRACTS.md §2/§3/§4 — the actual FastAPI route layer
(`app.routes.zotero`) built on top of Task 1C's already-tested
`app.auth.oauth`/`app.integrations.zotero` modules.

Session-mismatch/encrypted-storage/partial-push/idempotent-disconnect are
this task's four cited test scenarios (BuildPlan.md Task 3B); this file
also covers the `zotero_not_connected` path on every Zotero-authenticated
route and the newly-pinned `DELETE /zotero/connection` (CONTRACTS.md §4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
import responses
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from app.auth import oauth
from app.integrations import zotero as zotero_client
from app.middleware.session import (
    OAuthSessionBinding,
    SessionIdentityMiddleware,
    reset_fallback_cookie_secret_for_tests,
)
from app.models import Paper, ZoteroConnection, ZoteroExport
from app.models import Session as SessionRow
from app.models.crypto import decrypt_token, encrypt_token, reset_fallback_key_for_tests
from app.routes.zotero import router as zotero_router

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "zotero"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture
def item_creation_fixture() -> dict[str, Any]:
    return _load_fixture("item_creation_response.json")


@pytest.fixture(autouse=True)
def _isolated_binding(monkeypatch: pytest.MonkeyPatch) -> OAuthSessionBinding:
    """Fresh `OAuthSessionBinding` per test, matching Task 1C's own test
    isolation convention — `app.routes.zotero` imports `oauth` as a
    module and calls `oauth.start_handshake`/`complete_handshake`, both of
    which reference `app.auth.oauth.oauth_session_binding` directly."""
    binding = OAuthSessionBinding()
    monkeypatch.setattr(oauth, "oauth_session_binding", binding)
    return binding


@pytest.fixture(autouse=True)
def _configured_client_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth.settings, "zotero_client_key", "test-client-key")
    monkeypatch.setattr(oauth.settings, "zotero_client_secret", "test-client-secret")
    monkeypatch.setattr(
        oauth.settings,
        "zotero_callback_url",
        "https://litlist.example/api/v1/zotero/auth/callback",
    )
    monkeypatch.setattr(
        oauth.settings,
        "zotero_post_auth_redirect_url",
        "https://litlist.example/oauth/zotero/callback",
    )


@pytest.fixture(autouse=True)
def _reset_secrets() -> None:
    reset_fallback_cookie_secret_for_tests()
    reset_fallback_key_for_tests()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(zotero_router)
    return app


def _client() -> TestClient:
    return TestClient(_make_app(), base_url="https://testserver")


def _callback_redirect_params(location: str) -> dict[str, str]:
    """Every `GET /zotero/auth/callback` outcome (success and failure
    alike) is a redirect to the frontend's fixed `/oauth/zotero/callback`
    route with `status`/`code`/`message` query params (Task 4B's fix for
    the previously-unpinned redirect contract — see CONTRACTS.md) — this
    parses those params back out for assertions rather than each test
    re-implementing `urlsplit`/`parse_qs`."""
    split = urlsplit(location)
    base = f"{split.scheme}://{split.netloc}{split.path}"
    assert base == oauth.settings.zotero_post_auth_redirect_url
    return {k: v[0] for k, v in parse_qs(split.query).items()}


def _only_session_id(db_engine) -> str:
    with DBSession(db_engine) as db:
        row = db.exec(select(SessionRow)).one()
        return row.session_id


# ---------------------------------------------------------------------
# Session-mismatched OAuth callback rejected
# ---------------------------------------------------------------------


def test_callback_rejects_session_mismatch(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client_a = _client()
    client_b = TestClient(client_a.app, base_url="https://testserver")

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_REQUEST_TOKEN_URL,
            body="oauth_token=req-token-1&oauth_token_secret=req-secret-1",
            status=200,
        )
        start_response = client_a.get("/zotero/auth/start", follow_redirects=False)
    assert start_response.status_code == 302

    # Session B is a different browser/session entirely — hitting any
    # session-scoped endpoint gives it its own cookie via the middleware.
    unrelated = client_b.get("/zotero/collections")
    assert unrelated.status_code == 401

    callback_response = client_b.get(
        "/zotero/auth/callback",
        params={"oauth_token": "req-token-1", "oauth_verifier": "verifier-1"},
        follow_redirects=False,
    )

    # Task 4B fix: this is a real browser navigation (Zotero bounces the
    # user here directly), so failure is a redirect back into the app
    # (carrying the error code/message as query params) rather than a raw
    # JSON body the browser would render as a dead end.
    assert callback_response.status_code == 302
    params = _callback_redirect_params(callback_response.headers["location"])
    assert params["status"] == "error"
    assert params["code"] == "zotero_session_mismatch"

    with DBSession(db_engine) as db:
        assert db.exec(select(ZoteroConnection)).first() is None


# ---------------------------------------------------------------------
# Successful flow stores an ENCRYPTED ZoteroConnection
# ---------------------------------------------------------------------


def test_successful_callback_stores_encrypted_connection_and_rotates_session(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_REQUEST_TOKEN_URL,
            body="oauth_token=req-token-1&oauth_token_secret=req-secret-1",
            status=200,
        )
        start_response = client.get("/zotero/auth/start", follow_redirects=False)
    assert start_response.status_code == 302
    pre_callback_session_id = _only_session_id(db_engine)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_ACCESS_TOKEN_URL,
            body=(
                "oauth_token=access-token-1&oauth_token_secret=access-secret-1&userID=123456"
            ),
            status=200,
        )
        callback_response = client.get(
            "/zotero/auth/callback",
            params={"oauth_token": "req-token-1", "oauth_verifier": "verifier-1"},
            follow_redirects=False,
        )

    assert callback_response.status_code == 302
    params = _callback_redirect_params(callback_response.headers["location"])
    assert params["status"] == "success"
    assert "code" not in params
    assert "message" not in params

    with DBSession(db_engine) as db:
        rows = db.exec(select(ZoteroConnection)).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.zotero_user_id == "123456"

        # Never plaintext: the raw credential strings must not appear in
        # the stored columns at all, and decrypting must recover them.
        assert row.oauth_token != "access-token-1"
        assert row.oauth_token_secret != "access-secret-1"
        assert "access-token-1" not in row.oauth_token
        assert "access-secret-1" not in row.oauth_token_secret
        assert decrypt_token(row.oauth_token) == "access-token-1"
        assert decrypt_token(row.oauth_token_secret) == "access-secret-1"

        # §9.1: the session was rotated on Zotero-connect — the new
        # connection is filed against a *different* session_id than the
        # one that started the handshake, and the old row is gone.
        assert row.session_id != pre_callback_session_id
        assert db.get(SessionRow, pre_callback_session_id) is None
        assert db.get(SessionRow, row.session_id) is not None


def test_callback_failure_between_connection_insert_and_rotation_is_atomic(
    db_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-review fix (adversarial-generalist "TASK 3B REVIEW"): the
    `ZoteroConnection` insert and the session rotation must be one atomic
    transaction, not two separate commits — otherwise a crash between them
    could leave a `ZoteroConnection` durably attached to the pre-rotation
    `session_id`, reopening the exact fixation window §9.1's session
    rotation exists to close. Simulates that crash by making
    `rotate_session` raise *after* the connection has been added to the
    DB session (but only flushed, not committed) and asserts nothing was
    left behind under the pre-rotation session_id — or at all.
    """
    SQLModel.metadata.create_all(db_engine)
    app = _make_app()
    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_REQUEST_TOKEN_URL,
            body="oauth_token=req-token-1&oauth_token_secret=req-secret-1",
            status=200,
        )
        start_response = client.get("/zotero/auth/start", follow_redirects=False)
    assert start_response.status_code == 302
    pre_callback_session_id = _only_session_id(db_engine)

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("simulated crash between connection insert and session rotation")

    monkeypatch.setattr("app.routes.zotero.rotate_session", _boom)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_ACCESS_TOKEN_URL,
            body=(
                "oauth_token=access-token-1&oauth_token_secret=access-secret-1&userID=123456"
            ),
            status=200,
        )
        callback_response = client.get(
            "/zotero/auth/callback",
            params={"oauth_token": "req-token-1", "oauth_verifier": "verifier-1"},
            follow_redirects=False,
        )

    # The simulated crash propagates as an unhandled 500 — the important
    # assertion is what did (not) reach durable storage below.
    assert callback_response.status_code == 500

    with DBSession(db_engine) as db:
        # No ZoteroConnection was left behind at all — not under the
        # pre-rotation session_id, not anywhere — since the insert was
        # only flushed (visible in-transaction) and never committed on
        # its own; the whole transaction rolled back when `rotate_session`
        # raised and the request's DB session closed without a commit.
        assert db.exec(select(ZoteroConnection)).first() is None
        # The pre-rotation session row is untouched — rotation never
        # happened, so it was never deleted.
        assert db.get(SessionRow, pre_callback_session_id) is not None


# ---------------------------------------------------------------------
# service_unavailable / decrypt-failure paths at the route layer
# (Task 1C's own tests already exercise these at the module level; these
# confirm the route handlers actually map them to CONTRACTS.md §2 shapes).
# ---------------------------------------------------------------------


def test_start_auth_redirects_to_frontend_error_when_zotero_request_token_fails(
    db_engine,
) -> None:
    """`GET /zotero/auth/start` is also a real-browser-navigation endpoint
    (the "Connect to Zotero" button does a full navigation here, not a
    `fetch`) — a failure here must redirect back into the app the same
    way `auth/callback`'s failures do, not return a raw JSON body the
    browser would render as a dead end (Task 4B fix)."""
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, oauth.ZOTERO_REQUEST_TOKEN_URL, status=503)
        start_response = client.get("/zotero/auth/start", follow_redirects=False)

    assert start_response.status_code == 302
    params = _callback_redirect_params(start_response.headers["location"])
    assert params["status"] == "error"
    assert params["code"] == "service_unavailable"


def test_callback_returns_service_unavailable_when_zotero_is_unreachable(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            oauth.ZOTERO_REQUEST_TOKEN_URL,
            body="oauth_token=req-token-1&oauth_token_secret=req-secret-1",
            status=200,
        )
        client.get("/zotero/auth/start", follow_redirects=False)

    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, oauth.ZOTERO_ACCESS_TOKEN_URL, status=503)
        callback_response = client.get(
            "/zotero/auth/callback",
            params={"oauth_token": "req-token-1", "oauth_verifier": "verifier-1"},
            follow_redirects=False,
        )

    # Task 4B fix: redirect (with the error carried as query params),
    # not a raw JSON 503 — see `_callback_redirect_params`'s docstring.
    assert callback_response.status_code == 302
    params = _callback_redirect_params(callback_response.headers["location"])
    assert params["status"] == "error"
    assert params["code"] == "service_unavailable"
    with DBSession(db_engine) as db:
        assert db.exec(select(ZoteroConnection)).first() is None


def test_collections_returns_service_unavailable_when_stored_token_fails_to_decrypt(
    db_engine,
) -> None:
    """A corrupted/wrong-key `oauth_token` (`decrypt_token` raising
    `ValueError`, per `app.models.crypto`'s documented behavior) must
    surface as a safe `service_unavailable` — never an unhandled 500 or a
    leaked decryption-internals message."""
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")
    session_id = _only_session_id(db_engine)
    with DBSession(db_engine) as db:
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token="not-actually-encrypted-ciphertext",
                oauth_token_secret="not-actually-encrypted-ciphertext",
            )
        )
        db.commit()

    response = client.get("/zotero/collections")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert "not-actually-encrypted-ciphertext" not in response.text


# ---------------------------------------------------------------------
# zotero_not_connected on every Zotero-authenticated route
# ---------------------------------------------------------------------


def test_collections_requires_connection(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    response = client.get("/zotero/collections")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zotero_not_connected"


def test_create_collection_requires_connection(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    response = client.post("/zotero/collections", json={"name": "Journal Club"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zotero_not_connected"


def test_push_requires_connection(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    response = client.post("/zotero/push", json={"collection_key": "ABCD1234", "pmids": ["1"]})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "zotero_not_connected"


# ---------------------------------------------------------------------
# GET/POST collections against a connected session
# ---------------------------------------------------------------------


def test_list_collections_returns_key_and_name_when_connected(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")  # establishes a session cookie
    session_id = _only_session_id(db_engine)
    with DBSession(db_engine) as db:
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token=encrypt_token("access-token-1"),
                oauth_token_secret=encrypt_token("access-secret-1"),
            )
        )
        db.commit()

    raw_collections = _load_fixture("collections_response.json")["collections"]
    with patch.object(zotero_client.Zotero, "everything", return_value=raw_collections):
        with patch.object(zotero_client.Zotero, "collections", return_value=None):
            response = client.get("/zotero/collections")

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["collections"] == [
        {"key": "ABCD1234", "name": "Journal Club"},
        {"key": "WXYZ5678", "name": "To Read"},
    ]


def test_create_collection_returns_new_key_when_connected(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")
    session_id = _only_session_id(db_engine)
    with DBSession(db_engine) as db:
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token=encrypt_token("access-token-1"),
                oauth_token_secret=encrypt_token("access-secret-1"),
            )
        )
        db.commit()

    write_response = {
        "successful": {
            "0": {"key": "NEWKEY99", "data": {"key": "NEWKEY99", "name": "Journal Club"}}
        },
        "success": {"0": "NEWKEY99"},
        "unchanged": {},
        "failed": {},
    }
    with patch.object(zotero_client.Zotero, "create_collections", return_value=write_response):
        response = client.post("/zotero/collections", json={"name": "Journal Club"})

    assert response.status_code == 200
    assert response.json() == {"collection": {"key": "NEWKEY99", "name": "Journal Club"}}


# ---------------------------------------------------------------------
# Push returns per-PMID status, never all-or-nothing
# ---------------------------------------------------------------------


def test_push_returns_per_pmid_results_never_all_or_nothing(
    db_engine, item_creation_fixture
) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")
    session_id = _only_session_id(db_engine)

    with DBSession(db_engine) as db:
        db.add(
            Paper(
                pmid="38279812",
                title="Effects of early intervention on outcomes in a mixed-methods cohort study",
                authors=[{"first_name": "Sofia", "last_name": "Alvarez"}],
                journal="Journal of Applied Clinical Research",
                pub_date="2024 Feb",
                doi="10.1234/jacr.2024.001812",
            )
        )
        db.add(Paper(pmid="38279813", title="A second paper that fails to save"))
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token=encrypt_token("access-token-1"),
                oauth_token_secret=encrypt_token("access-secret-1"),
            )
        )
        db.commit()

    with patch.object(zotero_client.Zotero, "create_items", return_value=item_creation_fixture):
        response = client.post(
            "/zotero/push",
            json={"collection_key": "ABCD1234", "pmids": ["38279812", "38279813"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["collection_key"] == "ABCD1234"
    results_by_pmid = {r["pmid"]: r for r in body["results"]}
    assert results_by_pmid["38279812"]["status"] == "success"
    assert results_by_pmid["38279812"]["zotero_item_key"] == "XJ2K9F3P"
    assert results_by_pmid["38279813"]["status"] == "failure"
    assert results_by_pmid["38279813"]["error"]["code"] == "service_unavailable"

    with DBSession(db_engine) as db:
        exports = db.exec(select(ZoteroExport)).all()
        assert len(exports) == 1
        assert exports[0].pmid == "38279812"
        assert exports[0].zotero_item_key == "XJ2K9F3P"
        assert exports[0].zotero_collection_key == "ABCD1234"


def test_push_reports_not_found_for_a_pmid_missing_from_the_paper_cache(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")
    session_id = _only_session_id(db_engine)

    with DBSession(db_engine) as db:
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token=encrypt_token("access-token-1"),
                oauth_token_secret=encrypt_token("access-secret-1"),
            )
        )
        db.commit()

    response = client.post(
        "/zotero/push", json={"collection_key": "ABCD1234", "pmids": ["99999999"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == [
        {
            "pmid": "99999999",
            "status": "failure",
            "error": {
                "code": "not_found",
                "message": "This paper is no longer available to export.",
            },
        }
    ]
    with DBSession(db_engine) as db:
        assert db.exec(select(ZoteroExport)).first() is None


# ---------------------------------------------------------------------
# DELETE /zotero/connection actually removes the row and is idempotent
# ---------------------------------------------------------------------


def test_disconnect_removes_connection_and_is_idempotent(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()
    client.get("/zotero/collections")
    session_id = _only_session_id(db_engine)
    with DBSession(db_engine) as db:
        db.add(
            ZoteroConnection(
                session_id=session_id,
                zotero_user_id="123456",
                oauth_token=encrypt_token("t"),
                oauth_token_secret=encrypt_token("s"),
            )
        )
        db.commit()

    first = client.delete("/zotero/connection")
    assert first.status_code == 204
    assert first.content == b""

    with DBSession(db_engine) as db:
        assert db.exec(select(ZoteroConnection)).first() is None

    # Idempotent: calling it again with nothing to delete is still a
    # clean 204, never an error.
    second = client.delete("/zotero/connection")
    assert second.status_code == 204


def test_disconnect_on_a_session_with_no_connection_is_a_no_op_204(db_engine) -> None:
    SQLModel.metadata.create_all(db_engine)
    client = _client()

    response = client.delete("/zotero/connection")

    assert response.status_code == 204
