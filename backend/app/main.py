"""FastAPI app skeleton (BuildPlan.md Task 0.1).

Route modules (search, queue, decisions, saved, zotero, export) are added
in Tier 3 — this file only wires up the app instance, health check, and
(later) the middleware stack from Task 3D. Kept deliberately thin.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
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

# NOTE (Task 3A): `SessionIdentityMiddleware` is deliberately NOT added to
# this `app` instance here — per Task 1A's log, wiring the full middleware
# stack (session identity, CORS, inbound rate limiting, security headers)
# into the real app is Task 3D's job (BuildPlan.md's cross-cutting
# middleware task), once all of Wave 1's routes exist to test it against.
# Every Wave-1 route module (3A/3B/3C) already depends on
# `get_current_session`, which requires the middleware to be installed —
# each task's own tests build a local `FastAPI()` instance with
# `SessionIdentityMiddleware` added directly (see `test_zotero_routes.py`
# and this task's `tests/test_search_routes.py` etc. for the pattern)
# rather than testing against this shared `app` object, which will only
# be fully session-aware once Task 3D lands.


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
