"""Inbound per-IP (primary) / per-session (secondary) rate limiting
(BuildPlan.md Task 3D, SPEC.md §10.5's inbound half).

**Distinct from Task 1B's outbound pacing — different direction,
different mechanism, tested separately.** §10.5 draws this line
explicitly: `app/integrations/pubmed.py`/`icite.py`/`zotero.py` each pace
*this backend's own outbound calls* to a shared, per-service ceiling
(e.g. 10 req/sec for PubMed, across every concurrent LitList user) — that
governs how fast *we* call *them*. This module governs the opposite
direction: how fast an individual caller may call *us*, independent of
whether any outbound call even happens. A client hammering `/search` in
a tight loop is a problem for LitList's own API layer regardless of
PubMed's ceiling — it can single-handedly exhaust the *shared* outbound
budget before any other session gets a turn, or (once Zotero is
connected) use LitList as a free, unauthenticated write-proxy against a
user's own Zotero library. Neither problem is solved by outbound pacing
alone (§10.5's own reasoning) and this module's tests live in a separate
file from 1B's outbound-pacing tests for exactly that reason.

**Why the key is IP-primary, not session-primary (corrected after
adversarial review — see "PIVOT" in this task's build log entry).** An
earlier version of this module keyed strictly off `request.state.session.
session_id`, falling back to IP only when no session was resolved. That
fallback was **dead in the real request path**: `SessionIdentityMiddleware`
(wired ahead of this one, §10.2) transparently mints a brand-new `Session`
row and `session_id` for *any* request lacking a valid cookie — so a
caller can trivially get a fresh, never-before-seen rate-limit bucket on
every single request simply by not sending a cookie, defeating the limit
completely (adversarial review reproduced this with 30 cookie-less
requests against a 10/minute cap, all returning 200). A `session_id` is
free to mint and does not identify *the caller* in any way an attacker
can't cheaply launder around — it's a per-visit identity (§9.1), not an
accountability mechanism. The caller's IP address is comparatively
expensive to rotate (not free, unlike a cookie) and is the actual
resource contended for here (§10.5's "shared... across all concurrent
LitList users" framing is fundamentally about network-level callers, not
which cookie they happen to present), so **IP is now the primary,
unconditionally-enforced key** for every gated route below.
`session_id` is layered on top as a *secondary*, additional, finer-
grained check — both must pass for a request to proceed. This gives a
legitimate multi-tab/multi-device user behind a shared IP (e.g. an
office/campus NAT) their own individual session-level budget, while
still bounding the aggregate any single IP can consume regardless of how
many session cookies it cycles through, which is what actually stops the
two abuse shapes §10.5 names.

**Why this isn't slowapi's usual `@limiter.limit(...)` decorator.**
BuildPlan.md gives Task 3D exactly three files to own — none of them are
the Wave-1 route modules (`search.py`, `queue.py`, `zotero.py`,
`export.py`) that slowapi's decorator would need to be added to. Rather
than reach into files owned by 3A/3B/3C to add per-route decorators, this
module still uses slowapi's own `Limiter` class (its `RateLimitExceeded`
type, its `_inject_asgi_headers` helper, and — for the actual check — the
public `Limiter.limiter.hit(...)` property, the same underlying
`limits`-library call slowapi's decorator/middleware forms use
internally) — just driven from a small path/method lookup table in one
place here, checked from a plain ASGI middleware, rather than the
decorator form. §10.5 explicitly calls for *different* endpoints (search,
the abstract endpoint, Zotero push, export) to have their own thresholds
rather than one blanket number for the whole API, which is why each
gated route below carries its own `(session_limit, ip_limit)` pair rather
than a single global default.

Pure ASGI (not `starlette.middleware.base.BaseHTTPMiddleware`), matching
`app/middleware/session.py`'s own documented reason: avoiding that base
class's known interaction issues with streaming responses — `GET
/export.csv` streams (BuildPlan Task 3C), so this middleware must not
force-buffer it.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from limits import RateLimitItem, parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import ApiError, api_error_response

logger = logging.getLogger(__name__)


def _ip_key(request: Request) -> str:
    """The primary, unconditionally-enforced rate-limit dimension — the
    caller's IP address (`request.client.host`, via slowapi's own
    `get_remote_address`). Unlike a `session_id`, this isn't free for a
    caller to mint fresh on every request, which is exactly why it (not
    `session_id`) has to be the key that's actually load-bearing for
    §10.5's "prevent shared-budget exhaustion / free proxy abuse" goal.

    Not proxy-aware (doesn't consult `X-Forwarded-For`) — correct for
    this project's current single-process, direct-to-Render deployment
    shape (§12.2); if a reverse proxy is ever introduced in front of this
    backend, this would need to switch to trusting a specific,
    proxy-set header instead of blindly trusting a client-supplied one
    (an attacker-controlled `X-Forwarded-For` would otherwise let them
    pick their own rate-limit bucket just as freely as a fresh cookie
    does today) — flagging this now rather than leaving it as an
    unstated assumption for whoever does that deployment work.
    """
    return f"ip:{get_remote_address(request)}"


def _session_key(request: Request) -> str | None:
    """The secondary, additional rate-limit dimension — the resolved
    session's `session_id` (§9.1), or `None` if no session has been
    resolved (shouldn't happen in the real request path, since
    `SessionIdentityMiddleware` always resolves one ahead of this
    middleware, but this module makes no assumption that it's the only
    thing ever wrapping a request calling into `_matching_limit`'s
    matched routes)."""
    session = getattr(request.state, "session", None)
    session_id = getattr(session, "session_id", None)
    if session_id:
        return f"session:{session_id}"
    return None


# `key_func` here is only used if some future code reaches for slowapi's
# own decorator form (`@limiter.limit(...)`) directly on a route it owns
# — this module's own enforcement (`InboundRateLimitMiddleware` below)
# calls `limiter.limiter.hit(...)` with explicit `_ip_key`/`_session_key`
# values, not through this `key_func`. IP is the sane default here for
# the same reason it's the primary key everywhere else in this module.
limiter = Limiter(key_func=get_remote_address)

# §10.5's own worked examples (`/search`, `/papers/{pmid}/abstract`,
# `/zotero/push`) plus BuildPlan.md Task 3D's explicit minimum
# ("search, push, export") — every entry here is either a route that
# always makes a live external call (search, abstract, push) or one
# BuildPlan.md separately flags as "expensive" despite being local-only
# (`export.csv` streams a potentially-large Saved List). `GET /queue`,
# `GET /saved`, `GET /search/settings`, and the Zotero collections/OAuth
# routes are deliberately left ungated here — they're cheap, cached, or
# (OAuth start/callback) not JSON-body endpoints subject to the same
# abuse shape.
#
# Each entry is `(session_limit, ip_limit)`. `session_limit` is generous
# for a single real user (a person swiping through a queue triggers the
# abstract endpoint roughly once per card, and searches/pushes/exports
# only a handful of times per session); `ip_limit` is set to roughly 3x
# that — enough headroom for a handful of genuinely distinct legitimate
# sessions sharing one IP (an office/campus NAT, a household) without
# meaningfully loosening the actual defense, since `ip_limit` is what
# unconditionally caps how much any single network-level caller can
# consume regardless of how many fresh session cookies it cycles
# through.
_RATE_LIMITED_ROUTES: tuple[tuple[str, str, RateLimitItem, RateLimitItem], ...] = (
    ("POST", "/search", parse("10/minute"), parse("30/minute")),
    ("POST", "/zotero/push", parse("10/minute"), parse("30/minute")),
    ("GET", "/export.csv", parse("20/minute"), parse("60/minute")),
)
# `/papers/{pmid}/abstract` has a path parameter, so it's matched by
# prefix/suffix below rather than an exact string, alongside the table
# above.
_ABSTRACT_METHOD = "GET"
_ABSTRACT_PREFIX = "/papers/"
_ABSTRACT_SUFFIX = "/abstract"
_ABSTRACT_SESSION_LIMIT = parse("60/minute")
_ABSTRACT_IP_LIMIT = parse("180/minute")


def _matching_limit(
    method: str, path: str, api_prefix: str
) -> tuple[RateLimitItem, RateLimitItem] | None:
    """Return the `(session_limit, ip_limit)` pair that applies to
    `method`/`path`, or `None` if this request isn't one of §10.5's gated
    endpoints. `path` is the full request path (e.g. `/api/v1/search`);
    `api_prefix` (e.g. `/api/v1`) is stripped before matching against the
    table above so the table itself stays prefix-agnostic."""
    if not path.startswith(api_prefix):
        return None
    suffix = path[len(api_prefix) :]
    for table_method, table_path, session_limit, ip_limit in _RATE_LIMITED_ROUTES:
        if method == table_method and suffix == table_path:
            return session_limit, ip_limit
    if (
        method == _ABSTRACT_METHOD
        and suffix.startswith(_ABSTRACT_PREFIX)
        and suffix.endswith(_ABSTRACT_SUFFIX)
    ):
        return _ABSTRACT_SESSION_LIMIT, _ABSTRACT_IP_LIMIT
    return None


class InboundRateLimitMiddleware:
    """Plain ASGI middleware (see module docstring for why not
    `BaseHTTPMiddleware`). For each request, checks whether it matches
    one of `_RATE_LIMITED_ROUTES`/the abstract-endpoint pattern and, if
    so, checks the caller's IP-keyed bucket (primary, unconditional) and
    then — only if a session has actually been resolved — the caller's
    session-keyed bucket (secondary, finer-grained); either one being
    over threshold is enough to reject. A caller over threshold gets
    CONTRACTS.md §2's `rate_limited` (429) shape immediately —
    `self.app(...)` (routing, and therefore the route handler and any
    body parsing it does) is never called at all, so an over-threshold
    request never reaches PubMed/iCite/Zotero, matching §10.5's "enforced
    before a request is even allowed to reach the outbound wrappers."
    """

    def __init__(self, app: ASGIApp, api_prefix: str) -> None:
        self.app = app
        self.api_prefix = api_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        matched = _matching_limit(method, path, self.api_prefix)
        if matched is None:
            await self.app(scope, receive, send)
            return
        session_limit, ip_limit = matched

        request = Request(scope, receive=receive)

        ip_key = _ip_key(request)
        if not limiter.limiter.hit(ip_limit, ip_key):
            logger.warning(
                "Inbound rate limit exceeded (IP): %s %s (key=%s)", method, path, ip_key
            )
            await self._reject(scope, receive, send)
            return

        session_key = _session_key(request)
        if session_key is not None and not limiter.limiter.hit(session_limit, session_key):
            logger.warning(
                "Inbound rate limit exceeded (session): %s %s (key=%s)",
                method,
                path,
                session_key,
            )
            await self._reject(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = api_error_response(
            ApiError(
                429,
                "rate_limited",
                "Too many requests. Please wait a moment and try again.",
            )
        )
        await response(scope, receive, send)


def install_rate_limiting(app: FastAPI, api_prefix: str) -> None:
    """Register `InboundRateLimitMiddleware` on `app` via the standard
    `add_middleware` mechanism (matching `SessionIdentityMiddleware`'s own
    wiring in `app/main.py`) and stash the shared `Limiter` on
    `app.state.limiter` per slowapi's usual convention. See `app/main.py`
    for why this must be added *after* `SessionIdentityMiddleware` in
    call order (so it executes with a session already resolved, for the
    secondary session-keyed check)."""
    app.state.limiter = limiter
    app.add_middleware(InboundRateLimitMiddleware, api_prefix=api_prefix)


def reset_rate_limit_storage_for_tests() -> None:
    """Test helper — clears every counter slowapi's in-memory storage has
    accumulated, so one test's requests never bleed into the next test's
    threshold."""
    limiter.reset()


__all__ = [
    "InboundRateLimitMiddleware",
    "install_rate_limiting",
    "limiter",
    "reset_rate_limit_storage_for_tests",
]
