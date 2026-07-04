"""Shared pytest fixtures for backend tests.

`db_engine` gives each test an isolated, on-disk SQLite database (mirroring
`app/db.py`'s local-dev fallback) with every SQLModel table created, so
tests that need real rows (Task 1A's rotation/middleware tests, and later
tasks) don't have to hand-roll engine setup per test file.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from app import db

# Import side effect: registers every table on SQLModel.metadata so
# `create_all` below creates them.
from app.models import entities as _entities  # noqa: F401


@pytest.fixture
def db_engine(tmp_path, monkeypatch) -> Iterator[Engine]:
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db.settings, "local_sqlite_path", str(db_path))
    monkeypatch.setattr(db.settings, "turso_database_url", None)
    db.reset_engine_cache()

    engine = db.get_engine()
    SQLModel.metadata.create_all(engine)

    yield engine

    db.reset_engine_cache()
