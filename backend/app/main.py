"""FastAPI app skeleton (BuildPlan.md Task 0.1).

Route modules (search, queue, decisions, saved, zotero, export) are added
in Tier 3 — this file only wires up the app instance, health check, and
(later) the middleware stack from Task 3D. Kept deliberately thin.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
from app.middleware.errors import install_exception_handlers
from app.middleware.ratelimit import install_rate_limiting
from app.middleware.security import install_security
from app.middleware.session import SessionIdentityMiddleware
from app.routes.decisions import router as decisions_router
from app.routes.export import router as export_router
from app.routes.queue import router as queue_router
from app.routes.saved import router as saved_router
from app.routes.search import router as search_router
from app.routes.zotero import router as zotero_router

app = FastAPI(title="LitList API", version="0.1.0")

# Task 3C: CSV export (§8.8, §10.4). Other Wave-1 routers (search, queue,
# decisions, saved, zotero) are registered by their respective owning
# tasks (3A/3B) — each task registers only its own router here to avoid
# clobbering concurrent edits to this file.
app.include_router(export_router, prefix=settings.api_v1_prefix)
# Task 3B: Zotero auth/collections/push/disconnect (§10.4's zotero rows, §8).
app.include_router(zotero_router, prefix=settings.api_v1_prefix)
# Task 3A: core loop — search, queue/abstract, decisions, saved (§10.4).
app.include_router(search_router, prefix=settings.api_v1_prefix)
app.include_router(queue_router, prefix=settings.api_v1_prefix)
app.include_router(decisions_router, prefix=settings.api_v1_prefix)
app.include_router(saved_router, prefix=settings.api_v1_prefix)

# Task 3D: cross-cutting middleware stack (SPEC.md §10.3/§10.5/§10.7).
# Exception handlers aren't part of the ASGI middleware *stack* (they're
# registered on `ExceptionMiddleware`, a fixed inner layer Starlette
# always builds around the router — see `app/middleware/errors.py`'s
# docstring) so their registration order relative to `add_middleware`
# calls below doesn't matter. The `add_middleware` calls below, however,
# are order-sensitive: Starlette wraps each newly-added middleware
# *around* every previously-added one, so the FIRST middleware added ends
# up innermost (closest to routing) and the LAST one added ends up
# outermost (the first thing every request hits, the last thing every
# response passes through). Desired outer-to-inner order for a request:
#
#   SecurityHeaders -> CORS -> CSRFGuard -> SessionIdentity -> RateLimit -> routes
#
# - `SecurityHeaders` outermost so §10.7's baseline headers land on
#   literally every response this app ever sends, including a CORS
#   preflight response, a CSRF-guard 403, a rate-limit 429, or the global
#   exception handler's 500.
# - `CORS` next so a real browser's preflight `OPTIONS` is answered
#   before anything else runs.
# - `CSRFGuard` before `SessionIdentity`/`RateLimit` so a
#   disallowed-origin or non-JSON state-changing request is rejected
#   before a session row is even looked up/created and before the
#   inbound rate limiter does any work for it (§10.7: "a request from a
#   non-allow-listed origin never reaches the route handler at all").
# - `SessionIdentity` before `RateLimit` because §10.5's inbound
#   throttling is keyed primarily by `session_id` (§9.1's only identity
#   in this system) — the rate limiter needs `request.state.session`
#   already resolved.
#
# That means the `add_middleware` calls themselves must run in the
# *reverse* of the list above (innermost/first-added to
# outermost/last-added):
install_rate_limiting(app, settings.api_v1_prefix)  # innermost — first added
app.add_middleware(SessionIdentityMiddleware)
install_security(app)  # adds CSRFGuard, then CORS, then SecurityHeaders (outermost)
install_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe — used by Tier 0's smoke test and Tier 5's
    Render deploy check, deliberately with no DB dependency so it never
    fails purely because the database is briefly unreachable."""
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/health")
def health_v1() -> dict[str, str]:
    """Same probe under the versioned API prefix (§10.3) for parity with
    every real endpoint that will live under /api/v1."""
    return {"status": "ok"}
