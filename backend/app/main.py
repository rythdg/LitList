"""FastAPI app skeleton (BuildPlan.md Task 0.1).

Route modules (search, queue, decisions, saved, zotero, export) are added
in Tier 3 — this file only wires up the app instance, health check, and
(later) the middleware stack from Task 3D. Kept deliberately thin.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from app.clients import get_icite_client, get_pubmed_client
from app.config import settings
from app.db import get_engine
from app.middleware.errors import install_exception_handlers
from app.middleware.ratelimit import install_rate_limiting
from app.middleware.security import install_security
from app.middleware.session import SessionIdentityMiddleware

# Import side effect: registers every table on SQLModel.metadata so the
# `create_all` call in `lifespan` below actually has tables to create —
# without this import, `app.models.entities` may never have been loaded by
# the time `lifespan` runs (SPEC.md/BuildPlan.md don't call out a migration
# tool anywhere — grepped both, no Alembic/"migration tool" mention — so
# `create_all` on every boot, which is idempotent and only creates missing
# tables, is the right level of sophistication for this project's stated
# scope).
from app.models import entities as _entities  # noqa: F401
from app.routes.decisions import router as decisions_router
from app.routes.export import router as export_router
from app.routes.queue import router as queue_router
from app.routes.saved import router as saved_router
from app.routes.search import router as search_router
from app.routes.zotero import router as zotero_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Creates the app's DB schema on boot (real bug found in live e2e
    testing: nothing previously called `create_all` against the real
    `app.main:app` object — only `tests/conftest.py`'s fixture did, so a
    fresh local SQLite file, and almost certainly the real Turso database,
    had zero tables and 500'd on first request).

    `SQLModel.metadata.create_all` is idempotent (only creates missing
    tables), so this is safe to run on every process start, including
    every Render boot against the same persistent Turso database.

    Two known limitations of this approach, flagged by adversarial review
    — deliberately left as-is (no migration tool exists in this project's
    scope; see the grep note on the `app.models.entities` import above),
    but documented here so a future change doesn't assume `create_all` is
    a full migration solution:

    1. **Not safe under concurrent first boot against a genuinely EMPTY
       database.** `create_all`'s checkfirst logic is `has_table()` then
       a plain `CREATE TABLE` as two separate, unsynchronized steps (no
       `IF NOT EXISTS`, no shared transaction/lock). If two processes run
       this `lifespan` concurrently against a database with zero tables
       (e.g. a rolling redeploy with overlapping old/new instances, or
       two replicas cold-starting together), both can see "table
       missing" and race to create it — the loser gets an unhandled
       `OperationalError`. Harmless today (the real Turso database
       already has every table, so every future boot's `create_all` is a
       no-op), but a real landmine the first time this app is deployed
       fresh, or to a new empty database, with more than one replica.
    2. **Does not diff or migrate columns.** `create_all` only checks
       whether a table NAME already exists — it never compares columns,
       so adding/changing a field on an existing model in
       `app/models/entities.py` later will silently NOT be applied to an
       already-existing table in any persistent database (Turso), and
       would reproduce this exact bug class (missing column instead of
       missing table) one schema change from now. If/when that need
       arises, this needs a real migration tool (e.g. Alembic), not a
       bigger `create_all`.
    """
    SQLModel.metadata.create_all(get_engine())
    yield
    # PERF-2: the outbound wrapper clients (§10.5) each hold one
    # long-lived pooled `httpx.AsyncClient` (keep-alive connection reuse
    # to NCBI/iCite instead of a per-request TCP+TLS handshake) — close
    # them on shutdown so pooled connections don't dangle. Both `aclose`
    # calls are no-ops if the lazily-created pool was never used, and the
    # clients transparently re-create their pool if used again after a
    # close (relevant to repeated `TestClient` contexts in the suite,
    # since `app/clients.py`'s providers are process-wide `lru_cache`
    # singletons).
    await get_pubmed_client().aclose()
    await get_icite_client().aclose()


app = FastAPI(title="LitList API", version="0.1.0", lifespan=lifespan)

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
