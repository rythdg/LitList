"""Task 0.1 exit gate: db.py connects to local SQLite, and the connection
string swaps correctly when Turso-style env vars are set (without needing
a real Turso account for this unit-level check — the actual Turso
round-trip is Task 5A's infra test)."""

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
    assert url.startswith("sqlite+libsql://example-org.turso.io")
    assert "authToken=fake-token" in url
    monkeypatch.setattr(db.settings, "turso_database_url", None)
