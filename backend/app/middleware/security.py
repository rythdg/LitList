"""CORS allow-list, the CSRF guard it underwrites, and baseline security
response headers (BuildPlan.md Task 3D, SPEC.md §10.7).

**CORS is this project's CSRF defense, not just a fetch convenience**
(§10.7). Because there is no login/password layer (§9.1/§10.8), the only
thing that authenticates a request is the `litlist_session` cookie
(§10.2), and that cookie is `SameSite=None` (required for it to be sent
cross-origin at all, since the frontend and backend are different
origins by design). `SameSite=None` also disables the free CSRF
protection `SameSite=Lax`/`Strict` would otherwise give — so what
actually stops a malicious third-party site from making an authenticated
request against LitList's API in a victim's browser is:

1. A strict, explicit CORS origin allow-list (never a wildcard —
   wildcard + `allow_credentials=True` is both disallowed by browsers and
   a real footgun, §10.7's own words) — installed via FastAPI's own
   `CORSMiddleware` (`install_cors` below), which also handles the
   preflight `OPTIONS` dance browsers issue for genuinely cross-origin,
   non-"simple" requests.
2. Every state-changing endpoint requiring a JSON body — this is what
   makes a real cross-origin POST/PATCH/DELETE a non-"simple" request
   under the CORS spec (simple methods are only GET/HEAD/POST, and a
   simple POST loses its "simple" status only if its `Content-Type` is
   something other than `application/x-www-form-urlencoded`,
   `multipart/form-data`, or `text/plain`), which is what actually forces
   the preflight in (1) to run before a browser is allowed to send the
   real request at all.

**Why `CORSMiddleware` alone isn't enough, and `CSRFGuardMiddleware`
exists.** `CORSMiddleware` is a *browser-cooperation* protocol — for a
"simple" request (see above) from a disallowed origin, the browser still
lets the request go out and the server still processes it; the browser
only refuses to let the page's JS *read the response*. That's fine for
protecting response confidentiality, but it does nothing to stop the
request's *side effect* (a DB write) from happening, and it does nothing
at all against a non-browser client that fabricates an `Origin` header
directly (no browser cooperation to rely on in the first place).
`CSRFGuardMiddleware` below is the actual enforcement point: for every
state-changing method (`POST`/`PUT`/`PATCH`/`DELETE`) under the API
prefix, it rejects — before `self.app(...)` is ever called, i.e. before
FastAPI/Starlette have parsed a single byte of the body or the request
has reached any route handler or dependency — a request whose `Origin`
header (when present) isn't on the allow-list, and, for the
body-bearing methods (`POST`/`PUT`/`PATCH`), a request whose
`Content-Type` isn't `application/json`. That second check closes the
gap FastAPI's automatic-body-parsing routes (e.g. `POST /zotero/push`,
which takes its body as a typed Pydantic parameter) would otherwise leave
open: FastAPI's own request-body parsing doesn't care what `Content-Type`
header was actually sent — it just tries `await request.json()`
regardless — so without this explicit check, a "simple" cross-origin
`POST` declaring `Content-Type: text/plain` but carrying a JSON-shaped
body would sail past the browser's preflight requirement *and* still
parse successfully once it reached the route.

A request with no `Origin` header at all (same-origin browser
navigation, or any non-browser client — curl, a test harness, a
server-to-server call) is not rejected on that basis; there's no browser
same-origin boundary being crossed for the origin check to protect
against in that case, and rejecting all headerless requests would also
break this project's own test suite and local `curl`-based debugging for
no security benefit.

**DELETE endpoints and the frontend's actual contract.** `DELETE /saved/
{pmid}` and `DELETE /zotero/connection` (both owned by 3A/3B) never carry
a body — `frontend/src/api/client.ts`'s `apiFetch` only sets
`Content-Type: application/json` when a body is actually passed, and
neither of these calls passes one (see `frontend/src/api/saved.ts`,
`zotero.ts`). `DELETE` is also never a CORS-"simple" method in its own
right (only `GET`/`HEAD`/`POST` are), so it's always preflighted by a
real browser regardless of `Content-Type` — meaning the `Content-Type`
check below deliberately applies only to `POST`/`PUT`/`PATCH`, not
`DELETE`; requiring a JSON `Content-Type` on a `DELETE` with no body
would break this project's own real frontend contract for no CSRF
benefit `DELETE`'s non-simple method status doesn't already provide. The
`Origin` allow-list check still applies to `DELETE`, as defense in depth
against a non-browser client forging the header.

Pure ASGI middleware throughout (not `BaseHTTPMiddleware`), matching
`app/middleware/session.py`'s documented reasoning: avoids that base
class's known interaction issues with streaming responses (`GET
/export.csv`, Task 3C).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.errors import ApiError, api_error_response

logger = logging.getLogger(__name__)

# The methods CORS itself treats as "simple" (never preflighted, so this
# app-level guard is the only thing standing between them and CSRF) are
# GET/HEAD/POST — POST is included below because a "simple" POST with a
# non-JSON-declared Content-Type is exactly the shape a naive CSRF
# payload takes, per this module's docstring.
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BODY_BEARING_METHODS = frozenset({"POST", "PUT", "PATCH"})

# Baseline response headers (§10.7's own list, applied to every response
# — a second, independent layer of defense alongside §6.5/§11.3's
# rendering-level XSS mitigation on the frontend). This backend only ever
# serves JSON/CSV, never HTML, so a maximally conservative
# `default-src 'none'` CSP is safe here (there is no first-party script/
# style/image content for a policy to need to allow).
_SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
)


def _allowed_origins() -> list[str]:
    """Parse `settings.frontend_origins` (comma-separated, §10.7) into a
    list. Re-read from `settings` on every call (rather than cached at
    import time) so tests can monkeypatch `settings.frontend_origins` and
    have both `install_cors` and `CSRFGuardMiddleware` pick up the change
    without needing to reset a module-level cache."""
    return [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]


def install_cors(app: FastAPI) -> None:
    """FastAPI's own `CORSMiddleware`, configured per §10.7: an explicit
    origin allow-list (never a wildcard) plus `allow_credentials=True`
    (required for the session cookie to be sent cross-origin at all)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


class CSRFGuardMiddleware:
    """The actual enforcement point described in the module docstring.
    Runs ahead of routing entirely — a rejected request never reaches
    `SessionIdentityMiddleware`'s session lookup, any route handler, or
    any dependency, and its body is never read (`self.app(...)`, and
    therefore Starlette's request body parsing, is simply never called).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        if method not in _STATE_CHANGING_METHODS:
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}

        origin = headers.get("origin")
        if origin is not None and origin not in _allowed_origins():
            logger.warning(
                "CSRF guard: rejected %s %s from disallowed origin", method, scope["path"]
            )
            await self._reject(
                scope, receive, send, "This origin is not allowed to make this request."
            )
            return

        if method in _BODY_BEARING_METHODS:
            content_type = headers.get("content-type", "")
            # Compare only the media-type portion (ignore a `; charset=...`
            # suffix) case-insensitively — a real JSON client may send
            # `application/json; charset=utf-8`.
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                logger.warning(
                    "CSRF guard: rejected %s %s with non-JSON Content-Type %r",
                    method,
                    scope["path"],
                    content_type,
                )
                await self._reject(
                    scope, receive, send, "This endpoint requires a JSON request body."
                )
                return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send, message: str) -> None:
        response = api_error_response(ApiError(403, "csrf_rejected", message))
        await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Adds §10.7's baseline security headers to every outgoing response,
    including error responses (e.g. `CSRFGuardMiddleware`'s 403s,
    `InboundRateLimitMiddleware`'s 429s, and the global exception
    handler's 500s) — this middleware must therefore be the outermost
    layer in the stack (added last in `app/main.py`) so nothing else in
    the stack can produce a response that skips it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def install_security(app: FastAPI) -> None:
    """Wires all of §10.7 into `app`: the CORS allow-list, the CSRF
    guard, and the baseline security headers. Called once from
    `app/main.py`'s app-assembly. See that module for the required
    ordering relative to `SessionIdentityMiddleware`/
    `InboundRateLimitMiddleware`."""
    app.add_middleware(CSRFGuardMiddleware)
    install_cors(app)
    app.add_middleware(SecurityHeadersMiddleware)


__all__ = [
    "CSRFGuardMiddleware",
    "SecurityHeadersMiddleware",
    "install_cors",
    "install_security",
]
