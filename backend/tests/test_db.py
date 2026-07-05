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

from app import db


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
