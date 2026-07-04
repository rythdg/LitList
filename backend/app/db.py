"""Shared DB-connection module (BuildPlan.md Task 0.1).

This module is deliberately the *single* place a SQLAlchemy/SQLModel
engine gets constructed for the whole backend — Task 1A's data model and
Task 5A's infra provisioning both import `get_engine()`/`engine` from
here rather than each inventing their own connection path, which is the
exact gap BuildPlan.md flags as a first-draft mistake to avoid.

Connection string is env-var-driven (SPEC.md §12.3):

- If `TURSO_DATABASE_URL` is set, we connect to Turso via the
  `sqlalchemy-libsql` dialect (`sqlite+libsql://...`), optionally with
  `TURSO_AUTH_TOKEN` appended as a query param, per that driver's
  documented usage for remote libSQL/Turso databases.
- Otherwise, we fall back to a local SQLite file
  (`LOCAL_SQLITE_PATH`, default `./litlist_dev.db`) for local dev and
  tests — no code changes needed to switch between the two, only env
  vars.

Kept simple on purpose per BuildPlan.md's instruction: this is
scaffolding for Task 1A (data model) and Task 5A (infra) to build on, not
the final word on session/connection-pooling behavior.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.config import settings


def _build_connection_url() -> str:
    """Build the SQLAlchemy connection URL from env-driven settings."""
    if settings.turso_database_url:
        # Turso URLs typically look like libsql://<db>-<org>.turso.io
        # sqlalchemy-libsql expects the sqlite+libsql:// scheme.
        url = settings.turso_database_url
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "sqlite+libsql://", 1)
        if settings.turso_auth_token:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}authToken={settings.turso_auth_token}&secure=true"
        return url

    # Local dev / test fallback — plain local SQLite file, no libsql needed.
    return f"sqlite:///{settings.local_sqlite_path}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a process-wide singleton engine, built from env vars.

    `lru_cache` keeps this a single-construction singleton without module-
    level side effects at import time (important for tests that want to
    override env vars before the engine is first built).
    """
    connection_url = _build_connection_url()
    connect_args: dict[str, object] = {}
    if connection_url.startswith("sqlite:///"):
        # Needed for SQLite when the engine is shared across threads, which
        # FastAPI's threadpool-backed sync routes do.
        connect_args["check_same_thread"] = False
    return create_engine(connection_url, echo=False, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a SQLModel session bound to the shared engine."""
    with Session(get_engine()) as session:
        yield session


def reset_engine_cache() -> None:
    """Test helper: clears the cached engine so a new one is built on next call.

    Useful when a test changes env vars mid-run and needs `get_engine()` to
    pick up the new connection string instead of returning the cached one.
    """
    get_engine.cache_clear()
