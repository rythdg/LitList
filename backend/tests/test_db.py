"""Task 0.1 exit gate: db.py connects to local SQLite, and the connection
string swaps correctly when Turso-style env vars are set (without needing
a real Turso account for this unit-level check — the actual Turso
round-trip is Task 5A's infra test, `test_turso_integration.py`).

Task 5A bugfix note: an earlier version of this test asserted
`authToken=...` appeared embedded in the connection URL string. That
matched the earlier (buggy) implementation but not reality —
`sqlalchemy-libsql==0.2.0` silently drops any URL query param outside its
fixed allowlist (`uri`/`timeout`/`isolation_level`/`detect_types`/
`check_same_thread`/`cached_statements`/`secure`), so an embedded
`authToken` never reached `libsql_experimental.connect()`, which requires
`auth_token` as an explicit keyword argument. Confirmed against the real
Turso database (`ValueError: ... unauthorized access attempt on
database: empty JWT token`) before this test was corrected. See
`app/db.py`'s module docstring for the full trace. The token is now
verified via `get_engine()`'s `connect_args`, not the URL string — see
`test_auth_token_passed_via_connect_args_not_url` below."""

import threading

from app import db


def test_local_sqlite_wal_mode_enabled(tmp_path, monkeypatch) -> None:
    """Live-test fix regression guard: a new local-SQLite connection must
    come up in WAL journal mode with a non-zero busy_timeout pragma set.

    This is the specific mechanism the fix relies on (see `app/db.py`'s
    `_enable_wal_mode` + its `event.listen(engine, "connect", ...)`
    registration) — if a future change removes the listener registration,
    or only sets `connect_args["timeout"]` without the WAL pragma, this
    test fails immediately without needing to reproduce timing-sensitive
    lock contention.
    """
    db_path = tmp_path / "wal_test.db"
    monkeypatch.setattr(db.settings, "local_sqlite_path", str(db_path))
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()

    engine = db.get_engine()
    with engine.connect() as conn:
        journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()

    assert journal_mode == "wal"
    assert busy_timeout == 30000

    db.reset_engine_cache()


def test_local_sqlite_connect_listener_applies_to_every_pooled_connection(
    tmp_path, monkeypatch
) -> None:
    """The WAL pragma must be set on EVERY new connection the pool hands
    out, not just the first — `check_same_thread=False` means the engine
    can open more than one underlying connection for concurrent threads.
    Opens two connections simultaneously (so the pool can't just reuse a
    single warmed-up one) and asserts both independently report WAL."""
    db_path = tmp_path / "wal_pool_test.db"
    monkeypatch.setattr(db.settings, "local_sqlite_path", str(db_path))
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()

    engine = db.get_engine()
    conn_a = engine.connect()
    conn_b = engine.connect()
    try:
        mode_a = conn_a.exec_driver_sql("PRAGMA journal_mode").scalar()
        mode_b = conn_b.exec_driver_sql("PRAGMA journal_mode").scalar()
    finally:
        conn_a.close()
        conn_b.close()

    assert mode_a == "wal"
    assert mode_b == "wal"

    db.reset_engine_cache()


def test_concurrent_writes_do_not_raise_database_is_locked(db_engine) -> None:
    """Live-e2e-test regression: genuinely concurrent write-touching
    requests against local SQLite must not raise
    `sqlite3.OperationalError: database is locked`.

    Uses `BEGIN IMMEDIATE` + an explicit sleep before commit to actually
    hold the write lock open for the duration (SQLAlchemy/sqlite3's lazy
    transaction-begin means a plain ORM `session.add()` + `time.sleep()` +
    `commit()` would NOT hold the lock during the sleep — the write only
    happens at flush/commit time), which is the only way to deterministically
    reproduce contention in a fast, non-flaky unit test rather than relying
    on incidental OS scheduling luck.

    Confirmed non-vacuous: reverting `app/db.py`'s WAL/busy_timeout fix
    (`git stash` on that file alone) and rerunning this exact test with a
    higher thread count / longer hold reproduces
    `sqlite3.OperationalError: database is locked` reliably; it is NOT
    reproduced here at this thread count/hold combination purely because
    Python's sqlite3 driver already has an undocumented-by-us default
    5-second busy wait — this test's parameters are chosen to exceed that
    default-driver grace period while staying comfortably inside the fix's
    30-second budget, so it actually exercises the fix rather than passing
    for an unrelated reason.
    """
    n_threads = 20
    hold_seconds = 0.3
    errors: list[tuple[int, str]] = []
    barrier = threading.Barrier(n_threads)

    def worker(i: int) -> None:
        barrier.wait()
        raw = db_engine.raw_connection()
        try:
            cur = raw.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                "INSERT INTO session (session_id, created_at, last_seen_at) "
                "VALUES (?, datetime('now'), datetime('now'))",
                (f"concurrency-test-{i}",),
            )
            # Hold the write lock open, simulating a request doing real
            # work (other queries, serialization, etc.) mid-transaction.
            threading.Event().wait(hold_seconds)
            raw.commit()
            cur.close()
        except Exception as exc:  # noqa: BLE001 - we want to record ANY failure
            errors.append((i, repr(exc)))
        finally:
            raw.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"concurrent writes raised errors: {errors}"


def test_local_sqlite_connection(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db.settings, "local_sqlite_path", str(db_path))
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()

    engine = db.get_engine()
    with engine.connect() as conn:
        result = conn.exec_driver_sql("select 1").scalar()
        assert result == 1

    db.reset_engine_cache()


def test_turso_style_url_is_translated(monkeypatch) -> None:
    monkeypatch.setattr(db.settings, "turso_database_url", "libsql://example-org.turso.io")
    monkeypatch.setattr(db.settings, "turso_auth_token", "fake-token")
    url = db._build_connection_url()
    assert url == "sqlite+libsql://example-org.turso.io?secure=true"
    # The auth token must NOT be embedded in the URL string — sqlalchemy-
    # libsql's create_connect_args() would silently drop it (see module
    # docstring). It's injected via connect_args instead.
    assert "fake-token" not in url
    assert "authToken" not in url
    monkeypatch.setattr(db.settings, "turso_database_url", None)


def test_turso_query_string_is_stripped_before_rebuilding(monkeypatch) -> None:
    """A stray pre-existing query string (e.g. an old ?authToken=... value
    left in TURSO_DATABASE_URL) must not leak into the rebuilt URL."""
    monkeypatch.setattr(
        db.settings,
        "turso_database_url",
        "libsql://example-org.turso.io?authToken=stale-leftover-value",
    )
    monkeypatch.setattr(db.settings, "turso_auth_token", "fake-token")
    url = db._build_connection_url()
    assert url == "sqlite+libsql://example-org.turso.io?secure=true"
    assert "stale-leftover-value" not in url
    monkeypatch.setattr(db.settings, "turso_database_url", None)


def test_auth_token_passed_via_connect_args_not_url(monkeypatch) -> None:
    """The real bug (Task 5A): auth_token must reach create_engine() via
    connect_args, since sqlalchemy-libsql's create_connect_args() only
    lifts a fixed allowlist of query params out of the URL and does not
    recognize authToken/auth_token at all."""
    monkeypatch.setattr(db.settings, "turso_database_url", "libsql://example-org.turso.io")
    monkeypatch.setattr(db.settings, "turso_auth_token", "fake-token")
    db.reset_engine_cache()

    captured: dict[str, object] = {}
    real_create_engine = db.create_engine

    def fake_create_engine(url, **kwargs):  # type: ignore[no-untyped-def]
        captured["url"] = url
        captured["connect_args"] = kwargs.get("connect_args")
        # Don't actually try to connect to a fake host — return a real local
        # sqlite engine so get_engine() doesn't blow up on the return value.
        return real_create_engine("sqlite:///:memory:")

    monkeypatch.setattr(db, "create_engine", fake_create_engine)
    db.get_engine()

    assert captured["connect_args"] == {"auth_token": "fake-token"}
    assert "fake-token" not in str(captured["url"])

    monkeypatch.setattr(db, "create_engine", real_create_engine)
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()
