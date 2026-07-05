"""Regression test for the live-e2e DB-schema-creation bug.

Real bug found in live end-to-end testing (not by this suite): `app.main`
had no startup hook that created the DB schema, so a genuinely fresh
SQLite file (what a real developer's first `uvicorn app.main:app` run, or
Render's first boot against a never-touched Turso database, would get)
had zero tables — every DB-touching request 500'd with
`sqlite3.OperationalError: no such table: session`.

Every *other* test file in this suite was blind to that bug because they
all layer on top of `conftest.py`'s `db_engine` fixture, which calls
`SQLModel.metadata.create_all` itself as test scaffolding — none of them
ever exercised `app.main`'s own `lifespan` hook. This test deliberately
does NOT use that fixture: it points the shared engine at a brand-new,
never-created SQLite file of its own, and uses `TestClient` as a context
manager (`with TestClient(app) as client:`), which is required for
Starlette to actually run `lifespan` at all — a bare
`TestClient(app)` (the pattern almost every other test file in this repo
uses) never triggers `wait_startup`, so it would silently pass even with
the bug still present. See `starlette.testclient.TestClient._portal_factory`:
without `__enter__`, each request gets its own throwaway portal and the
lifespan handler never runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

# Import side effect: registers every table on SQLModel.metadata, mirroring
# what `app.main` itself does — needed so this test's own assertions about
# "no such table" failures are meaningful (the table has to be a real,
# registered model, not just absent because nothing ever defined it).
from app.models import entities as _entities  # noqa: F401


@pytest.fixture
def fresh_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Points the shared `app.db` engine at a brand-new, never-created
    SQLite file — deliberately NOT `conftest.py`'s `db_engine` fixture,
    which pre-creates every table itself and would defeat the point of
    this regression test."""
    db_path = tmp_path / "fresh_lifespan_test.db"
    monkeypatch.setattr(db.settings, "local_sqlite_path", str(db_path))
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()

    assert not db_path.exists(), "test setup bug: db file must not pre-exist"

    yield db_path

    db.reset_engine_cache()


def test_fresh_boot_creates_schema_and_serves_a_real_request(
    fresh_db_path: Path,
) -> None:
    """Booting the real `app.main:app` object (via `lifespan`, using
    `TestClient` as a context manager) against a brand-new empty SQLite
    file must create the schema before serving any request. Before the
    fix, this exact sequence 500'd with `no such table: session`."""
    assert not fresh_db_path.exists()

    with TestClient(app) as client:
        # The file (and its schema) must exist by the time startup
        # completes, before any request is even made.
        assert fresh_db_path.exists()

        response = client.get("/api/v1/search/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["sort"] == "relevance"
