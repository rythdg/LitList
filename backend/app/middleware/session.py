"""Session identity middleware (SPEC.md §10.2, BuildPlan.md Task 1A).

Implements §9.1's anonymous-session design as middleware, not a per-endpoint
concern:

- Any request without a valid, signed `session_id` cookie gets a brand-new
  `Session` row created transparently and the cookie set on the response —
  no endpoint ever requires the cookie to pre-exist, which is what makes
  "no login screen" (§3.2.A) true at the API level, not just the UI level.
- Every route handler resolves the current `Session` (and, if present,
  `ZoteroConnection`) via the `get_current_session`/`get_current_zotero_
  connection` FastAPI dependencies below, rather than re-reading the cookie
  itself.

This module is NOT wired into `app/main.py` here — that's Task 3D's job
(BuildPlan.md's cross-cutting middleware task, which assembles the full
middleware stack: this session middleware, CORS, inbound rate limiting,
security headers). Task 1A's scope is to make this a correct, importable,
independently-testable unit.

**The OAuth request-token-to-session binding primitive** (§10.2's OAuth
addendum, §9.6) also lives here: `oauth_session_binding`, a small in-process
store that Task 1C's OAuth handshake imports directly. See its docstring
for why in-process (rather than a DB table) is the right call for this
piece specifically.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import Request, Response
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.config import settings
from app.db import get_engine
from app.models.entities import Session as SessionRow
from app.models.entities import ZoteroConnection
from app.models.ids import utcnow

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "litlist_session"
# 400 days is the practical browser-enforced ceiling on `Max-Age` (Chrome
# clamps anything longer) — used here to keep "sticky settings" (§3.5)
# genuinely persistent across visits without pretending we can set a cookie
# that outlives that ceiling.
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 400

_fallback_cookie_secret: bytes | None = None


def _get_cookie_secret() -> bytes:
    """Key used to HMAC-sign the cookie value. See `backend/.env.example`
    for how `SESSION_COOKIE_SECRET` is generated; falls back to an ephemeral
    per-process key (loudly logged) when unset, same trade-off as
    `app.models.crypto`'s `TOKEN_ENCRYPTION_KEY` fallback — fine for local
    dev/tests, not for a deployment that needs cookies to survive a restart
    (every existing cookie would fail signature verification and simply be
    treated as absent, silently reissuing a fresh session — not a security
    bug, just a UX papercut worth setting the real env var to avoid).
    """
    if settings.session_cookie_secret:
        return settings.session_cookie_secret.encode()

    global _fallback_cookie_secret
    if _fallback_cookie_secret is None:
        logger.warning(
            "SESSION_COOKIE_SECRET is not set — generating an ephemeral "
            "per-process signing key. Fine for local dev/tests; sessions "
            "won't survive a process restart in this mode. Set "
            "SESSION_COOKIE_SECRET in the environment for any persistent "
            "deployment (see backend/.env.example)."
        )
        _fallback_cookie_secret = secrets.token_bytes(32)
    return _fallback_cookie_secret


def reset_fallback_cookie_secret_for_tests() -> None:
    """Test helper only — mirrors `crypto.reset_fallback_key_for_tests`."""
    global _fallback_cookie_secret
    _fallback_cookie_secret = None


def _sign(session_id: str) -> str:
    """Cookie value = `<session_id>.<hmac-sha256 hex digest>`. The
    `session_id` itself remains the real database key (opaque, CSPRNG,
    looked up directly, §9.1) — the signature is a cheap, defense-in-depth
    check that lets the middleware reject a tampered/forged cookie value
    before it ever reaches a DB lookup, rather than silently treating junk
    input as "session not found" and issuing a new one (still safe, but
    noisier and slower under a hostile client deliberately sending garbage
    cookie values).
    """
    key = _get_cookie_secret()
    signature = hmac.new(key, session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{signature}"


def _verify(cookie_value: str) -> str | None:
    """Return the embedded `session_id` if the signature is valid, else
    `None`. Never raises on malformed input — malformed/tampered cookies are
    treated identically to "no cookie at all"."""
    try:
        session_id, signature = cookie_value.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(_get_cookie_secret(), session_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return session_id


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set the signed session cookie on `response`. Exposed as a standalone
    function (not just inlined in the middleware) because Task 1C's OAuth
    callback handler must call this again after `rotate_session` (§9.1) to
    push the rotated id to the browser.

    `HttpOnly`+`Secure`+`SameSite=None` per §10.2: `SameSite=None` is
    required (not optional) because the frontend and backend are different
    origins; `Secure` is required for browsers to honor `SameSite=None` at
    all; `HttpOnly` keeps the value unreadable to any frontend JS (defense
    against XSS reading/exfiltrating it, matching §9.6's "never sent to the
    frontend" principle for the more sensitive Zotero token, applied here
    too even though this value is comparatively lower-stakes).
    """
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_sign(session_id),
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


class SessionIdentityMiddleware:
    """ASGI middleware implementing §10.2. Written as a plain ASGI middleware
    (not `starlette.middleware.base.BaseHTTPMiddleware`) to avoid that
    class's known interaction issues with streaming responses/background
    tasks — this app will stream the CSV export (§8.8, §10.4) later, so
    avoiding that footgun now is cheaper than migrating away from it later.
    """

    # Paths deliberately exempt from session resolution — Task 0.1's
    # `/health` and `/api/v1/health` liveness/readiness probes are
    # documented (see `app/main.py`) as having "no DB dependency so it
    # never fails purely because the database is briefly unreachable."
    # Discovered as a regression while wiring this middleware into the
    # shared `app` for the first time (BuildPlan.md Task 3D): without this
    # exemption, every request — including the health check — triggers a
    # `Session` row lookup/insert, silently reintroducing exactly the DB
    # dependency that endpoint was written to avoid (and breaking
    # `tests/test_health.py`, which never provisions a schema). Kept as a
    # fixed, hardcoded set rather than a settings-driven exemption list
    # since it's a narrow, load-bearing exception to "every request gets a
    # session," not a general-purpose bypass mechanism.
    _EXEMPT_PATHS = frozenset({"/health", f"{settings.api_v1_prefix}/health"})

    def __init__(self, app):  # type: ignore[no-untyped-def]
        self.app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in self._EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        session_id = _verify(raw_cookie) if raw_cookie else None

        issue_new_cookie = False
        with DBSession(get_engine()) as db:
            session_row = db.get(SessionRow, session_id) if session_id else None
            if session_row is None:
                session_row = SessionRow()
                issue_new_cookie = True
            else:
                session_row.last_seen_at = utcnow()
            db.add(session_row)
            db.commit()
            db.refresh(session_row)

            zotero_connection = db.exec(
                select(ZoteroConnection).where(
                    ZoteroConnection.session_id == session_row.session_id
                )
            ).first()

        resolved_session_id = session_row.session_id
        scope.setdefault("state", {})
        scope["state"]["session"] = session_row
        scope["state"]["zotero_connection"] = zotero_connection

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if issue_new_cookie and message["type"] == "http.response.start":
                response = Response()
                set_session_cookie(response, resolved_session_id)
                cookie_header = next(
                    (v for k, v in response.raw_headers if k == b"set-cookie"), None
                )
                if cookie_header is not None:
                    headers = message.setdefault("headers", [])
                    headers.append((b"set-cookie", cookie_header))
            await send(message)

        await self.app(scope, receive, send_wrapper)


def get_current_session(request: Request) -> SessionRow:
    """FastAPI dependency: the resolved `Session` for this request, per
    §10.2. Requires `SessionIdentityMiddleware` to be installed — raises
    `RuntimeError` (a programming error, not a client-facing one) if not,
    rather than silently returning `None` and pushing a null-check onto
    every route."""
    session = request.state.session if hasattr(request.state, "session") else None
    if session is None:
        raise RuntimeError(
            "get_current_session used without SessionIdentityMiddleware installed."
        )
    return session  # type: ignore[no-any-return]


def get_current_zotero_connection(request: Request) -> ZoteroConnection | None:
    """FastAPI dependency: the current session's `ZoteroConnection`, or
    `None` if not yet connected (§9.2). Routes needing Zotero access check
    for `None` and return the `zotero_not_connected` error (CONTRACTS.md
    §2) rather than this dependency raising."""
    return getattr(request.state, "zotero_connection", None)


class OAuthSessionBinding:
    """Binds a pending Zotero OAuth request token to the `session_id` that
    initiated the handshake (§10.2's OAuth addendum, §9.6) — closes the gap
    where OAuth 1.0a's request-token step is not itself bound to any
    particular LitList session, which would otherwise let a stale/replayed
    callback URL attach the wrong `ZoteroConnection` to the wrong `Session`.

    **In-process, not a DB table — a deliberate choice, not an oversight.**
    §10.2 describes this as "a short-lived row/cache entry, not a permanent
    one." This project has no Redis/background-queue layer (§10.6) and runs
    as a single small always-on backend process (§12.2), so an in-process
    dict with a short TTL gives the same correctness guarantee (bound to
    the initiating session, expires quickly, single-use) without adding
    infrastructure or a migration for a table that only ever holds
    minutes-old rows. If this backend ever runs as multiple concurrent
    worker processes, this would need to move to a shared store (DB table
    or Redis) instead — flagging that explicitly so it isn't silently
    load-bearing on a single-process assumption forever.
    """

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl_seconds = ttl_seconds
        # request_token -> (session_id, request_token_secret, expires_at)
        self._pending: dict[str, tuple[str, str, float]] = {}

    def store(self, session_id: str, request_token: str, request_token_secret: str) -> None:
        """Record that `request_token` was issued to `session_id` (§8.2
        step 2). Called by Task 1C's `/zotero/auth/start` handler."""
        expires_at = time.monotonic() + self._ttl_seconds
        self._pending[request_token] = (session_id, request_token_secret, expires_at)

    def resolve(self, session_id: str, request_token: str) -> str | None:
        """Consume and return the bound `request_token_secret` if
        `request_token` was issued to exactly `session_id` and hasn't
        expired; otherwise `None`.

        Single-use by design: the entry is removed on the *first* lookup
        attempt regardless of outcome, so a replayed/second callback for the
        same token — whether or not it matches — can never succeed, per
        §10.2's "rejecting the callback otherwise." Called by Task 1C's
        `/zotero/auth/callback` handler; a `None` result maps to the
        `zotero_session_mismatch` error code (CONTRACTS.md §2).
        """
        entry = self._pending.pop(request_token, None)
        if entry is None:
            return None
        bound_session_id, request_token_secret, expires_at = entry
        if time.monotonic() > expires_at:
            return None
        if not secrets.compare_digest(bound_session_id, session_id):
            return None
        return request_token_secret


# Process-wide singleton — see `OAuthSessionBinding`'s docstring for why a
# module-level instance (rather than a DB-backed dependency) is the right
# shape for this specific, short-lived piece of state.
oauth_session_binding = OAuthSessionBinding()
