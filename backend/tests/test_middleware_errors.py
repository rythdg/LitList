"""Task 3D tests, SPEC.md §10.3 (CONTRACTS.md §2's error shape) and
§15.8's inbound half — `app/middleware/errors.py`'s global exception-shape
guarantee.

Builds a minimal standalone app (not `app.main.app`) with a handful of
deliberately-broken routes wired to `install_exception_handlers`, so this
file is self-contained and doesn't depend on any Wave-1 route's specific
behavior. Covers §10.3's core promise across *multiple* distinct
exception types (a bare `Exception`, a SQLAlchemy error, a `KeyError`)
per this task's brief — a handler that only special-cased one exception
type would be a real gap here specifically.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from app.middleware.errors import install_exception_handlers

_SECRET = "sk-super-secret-ncbi-api-key-should-never-leak"


def _make_app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom/generic")
    def boom_generic() -> None:
        raise Exception(f"raw internal detail: {_SECRET}")  # noqa: TRY002

    @app.get("/boom/sqlalchemy")
    def boom_sqlalchemy() -> None:
        raise OperationalError(
            f"SELECT * FROM secrets WHERE key='{_SECRET}'", {}, Exception("no such table")
        )

    @app.get("/boom/keyerror")
    def boom_keyerror() -> None:
        raise KeyError(_SECRET) from None  # simulate a dict access that embeds sensitive data

    @app.get("/items/{item_id}")
    def get_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


@pytest.mark.parametrize("path", ["/boom/generic", "/boom/sqlalchemy", "/boom/keyerror"])
async def test_unhandled_exceptions_never_leak_details(path: str) -> None:
    """§10.3: "message" must always be a safe, pre-written string — never
    raw exception text or a stack trace — regardless of exception type."""
    app = _make_app()
    async with await _client(app) as client:
        response = await client.get(path)

    assert response.status_code == 500
    body = response.json()
    assert body == {
        "error": {
            "code": "internal_error",
            "message": "Something went wrong on our end. Please try again shortly.",
        }
    }
    # The secret/internal detail must not appear anywhere in the raw
    # response body, under any key.
    assert _SECRET not in response.text
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()


async def test_validation_error_normalized_to_pinned_shape() -> None:
    """A FastAPI/Pydantic automatic validation failure (422 by default)
    is normalized to CONTRACTS.md §2's shape and status, not FastAPI's
    own `{"detail": [...]}` body."""
    app = _make_app()
    async with await _client(app) as client:
        response = await client.get("/items/not-an-int")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "The request was invalid. Please check your input and try again.",
        }
    }
    # FastAPI's default validation error echoes back the submitted value
    # and field location — neither should appear here.
    assert "not-an-int" not in response.text
    assert "loc" not in response.json()["error"]


async def test_successful_request_is_unaffected() -> None:
    """The global handlers must not interfere with a normal, successful
    response — only unhandled/validation failures should be touched."""
    app = _make_app()
    async with await _client(app) as client:
        response = await client.get("/items/42")

    assert response.status_code == 200
    assert response.json() == {"item_id": 42}


class _BoomMiddleware:
    """A plain ASGI middleware that raises directly from its own
    `__call__` — i.e. before/instead of ever delegating to `self.app` —
    standing in for a bug inside `InboundRateLimitMiddleware`/
    `CSRFGuardMiddleware`/`SecurityHeadersMiddleware` themselves, not a
    route handler they wrap."""

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raise Exception(f"raw internal detail from middleware: {_SECRET}")  # noqa: TRY002


def test_exception_from_middleware_itself_is_still_safe() -> None:
    """Pins tester's TASK 3D VERIFY finding: a bare `Exception` raised
    from inside this app's own ASGI middleware (not a route handler it
    wraps) — the layer this module's docstring previously (incorrectly)
    claimed sat outside `install_exception_handlers`' reach — still comes
    back as CONTRACTS.md §2's safe shape, never the raw exception text.

    This is because `Starlette.build_middleware_stack` promotes whichever
    handler is registered for the bare `Exception` class to also serve as
    `ServerErrorMiddleware`'s handler — and `ServerErrorMiddleware` is the
    *outermost* layer of the whole stack, wrapping every `add_middleware`
    call (including a middleware that raises directly, before ever
    calling into the app it wraps). `ServerErrorMiddleware` re-raises
    after sending the response (so servers/test harnesses can still log
    it) — `TestClient(..., raise_server_exceptions=False)` is required
    here for exactly that reason, mirroring what `test_zotero_routes.py`
    already does for its own deliberately-raising scenario.
    """
    from fastapi.testclient import TestClient

    app = _make_app()
    app.add_middleware(_BoomMiddleware)

    client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    response = client.get("/items/42")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Something went wrong on our end. Please try again shortly.",
        }
    }
    assert _SECRET not in response.text
    assert "Traceback" not in response.text
