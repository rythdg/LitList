"""Shared DB-connection module (BuildPlan.md Task 0.1).

This module is deliberately the *single* place a SQLAlchemy/SQLModel
engine gets constructed for the whole backend — Task 1A's data model and
Task 5A's infra provisioning both import `get_engine()`/`engine` from
here rather than each inventing their own connection path, which is the
exact gap BuildPlan.md flags as a first-draft mistake to avoid.

Connection string is env-var-driven (SPEC.md §12.3):

- If `TURSO_DATABASE_URL` is set, we connect to Turso via the
  `sqlalchemy-libsql` dialect (`sqlite+libsql://<host>?secure=true`).
  Otherwise, we fall back to a local SQLite file
  (`LOCAL_SQLITE_PATH`, default `./litlist_dev.db`) for local dev and
  tests — no code changes needed to switch between the two, only env
  vars.

**BuildPlan.md Task 5A bugfix (2026-07-05):** the auth token is
deliberately NOT embedded in the connection URL string. Reading the
installed `sqlalchemy-libsql==0.2.0` driver source
(`sqlalchemy_libsql/libsql.py::create_connect_args`) shows it only lifts
a fixed allowlist of query params out of the URL into the kwargs passed
to `libsql_experimental.connect()` — `uri`, `timeout`,
`isolation_level`, `detect_types`, `check_same_thread`,
`cached_statements`, `secure`. `authToken`/`auth_token` is NOT in that
allowlist, so an `?authToken=...`-style query param silently never
reaches `connect()`, which requires `auth_token` as an explicit keyword
argument (confirmed via `help(libsql_experimental.connect)`) —
reproducible as `ValueError: ... unauthorized access attempt on
database: empty JWT token`. `secure=true`, by contrast, MUST stay a URL
query param: it's in the dialect's allowlist, used internally to choose
the `https`/`wss` scheme, then popped before building the final connect
kwargs — the real driver has no `secure=` parameter on `connect()`
itself, so passing it via `connect_args` would raise a `TypeError`.
The fix: build the URL as scheme+host+`?secure=true` only, and pass
`auth_token` via SQLAlchemy's `connect_args=` to `create_engine()`.
Tracing `sqlalchemy/engine/create.py::create_engine()` confirms
`connect_args` passed there is unconditionally unioned on top of
whatever `dialect.create_connect_args(url)` extracted from the URL
(`cparams = dialect_cparams.union(connect_args)`), so a key the dialect
never recognizes (`auth_token`) still reaches `libsql_experimental.
connect()` correctly via this path, bypassing the URL-parsing allowlist
entirely.

Kept simple on purpose per BuildPlan.md's instruction: this is
scaffolding for Task 1A (data model) and Task 5A (infra) to build on, not
the final word on session/connection-pooling behavior.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.config import settings


def _build_connection_url() -> str:
    """Build the SQLAlchemy connection URL from env-driven settings.

    Deliberately does NOT embed the auth token — see the module docstring's
    Task 5A bugfix note. `secure=true` is the one query param that must stay
    in the URL (it's in sqlalchemy-libsql's allowlist and selects the
    https/wss scheme internally); the auth token is injected separately via
    `connect_args` in `get_engine()`.
    """
    if settings.turso_database_url:
        # Turso URLs typically look like libsql://<db>-<org>.turso.io
        # sqlalchemy-libsql expects the sqlite+libsql:// scheme.
        url = settings.turso_database_url
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "sqlite+libsql://", 1)
        # Strip any existing query string (e.g. a stray ?authToken=... from
        # an older/misconfigured value) so we control it explicitly below.
        url = url.split("?", 1)[0]
        return f"{url}?secure=true"

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
    is_local_sqlite = connection_url.startswith("sqlite:///")
    if is_local_sqlite:
        # Needed for SQLite when the engine is shared across threads, which
        # FastAPI's threadpool-backed sync routes do.
        connect_args["check_same_thread"] = False
        # Local SQLite is single-writer; FastAPI's threadpool-backed sync
        # routes mean genuinely concurrent requests (e.g. a page load's
        # parallel /search/settings, /queue, /saved, /zotero/collections
        # fetches, each touching the session row) can otherwise raise
        # `sqlite3.OperationalError: database is locked` — reproduced live
        # during manual end-to-end testing. A busy-timeout alone (waiting
        # rather than failing immediately) wasn't sufficient under real
        # concurrent load; SQLite's default rollback-journal mode holds an
        # exclusive lock for the whole duration of any write. WAL mode
        # (below) is the standard fix for this exact "many small
        # concurrent reads/writes" pattern, since it lets readers proceed
        # without blocking on a writer. Not a concern for Turso (a real
        # client-server DB, not file-level locking), only the local-dev
        # SQLite fallback. Note this raises the failure threshold to ~30s
        # of *sustained serialized write time*, not an unlimited one — at
        # very high concurrency (dozens of simultaneous writers, far
        # beyond realistic local single-user traffic) SQLAlchemy's default
        # connection pool (5 + 10 overflow = 15) will itself raise
        # `QueuePool ... timed out` before the busy-timeout budget is
        # exhausted; this is a separate, pre-existing pool-sizing limit,
        # not something this fix changes or needs to address for local
        # dev's actual usage pattern.
        connect_args["timeout"] = 30
    elif settings.turso_database_url and settings.turso_auth_token:
        # Bypasses sqlalchemy-libsql's URL-query allowlist entirely — see
        # the module docstring's Task 5A bugfix note. `create_engine()`
        # unions this dict on top of whatever `create_connect_args()`
        # extracted from the URL, so `auth_token` reaches
        # `libsql_experimental.connect()` even though the dialect itself
        # never looks for it in the URL.
        connect_args["auth_token"] = settings.turso_auth_token
    engine = create_engine(connection_url, echo=False, connect_args=connect_args)
    if is_local_sqlite:
        event.listen(engine, "connect", _enable_wal_mode)
    return engine


def _enable_wal_mode(dbapi_connection: object, _connection_record: object) -> None:
    """Set on every new local-SQLite connection (see `get_engine()` above).

    Both pragmas matter: WAL lets readers proceed without blocking on an
    in-progress writer, but SQLite still allows only one writer at a time
    even under WAL — two genuinely concurrent write transactions (e.g. two
    requests both touching the session row's `last_seen_at`) still need
    one to wait for the other. `busy_timeout` is set directly via pragma
    here rather than relying solely on the `timeout` kwarg passed to
    `sqlite3.connect()` in `get_engine()` above, since that Python-driver-
    level setting was observed (live, during manual testing) to not fully
    prevent `database is locked` under real concurrent load on its own.
    """
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


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
