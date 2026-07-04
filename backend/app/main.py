"""FastAPI app skeleton (BuildPlan.md Task 0.1).

Route modules (search, queue, decisions, saved, zotero, export) are added
in Tier 3 — this file only wires up the app instance, health check, and
(later) the middleware stack from Task 3D. Kept deliberately thin.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="LitList API", version="0.1.0")


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
