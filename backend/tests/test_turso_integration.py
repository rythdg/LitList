"""BuildPlan.md Task 5A — real Turso round-trip integration test.

This is deliberately NOT a mock/respx test: it connects to the actual
Turso database identified by `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` (read
from the environment/`.env`, values never touched or logged by this file)
through the *same* `app/db.py` module the rest of the backend uses — no ad
hoc connection script, per BuildPlan.md's explicit instruction that 5A and
1A must not build two different DB-connection paths.

Skipped automatically when `TURSO_DATABASE_URL` isn't set, so this file is
safe in CI and for any other developer's machine that has no real Turso
credentials configured — the rest of the suite (213+ other tests) never
touches a real network and keeps using local SQLite by default.

Two things are proven here, matching Task 5A's test gate:

1. `db.get_engine()` can actually authenticate against the real Turso
   database and write/read a row (this is the literal bug this task fixed
   — the auth token was previously silently dropped, producing
   `unauthorized access attempt on database: empty JWT token`).
2. The written row survives being read back from a completely separate,
   freshly-started Python process (`subprocess`) — the closest thing to
   proving Turso persistence across a Render spin-down/restart cycle that
   can be done without an actual Render deployment, which requires the
   human to click through the Render dashboard (see BuildPlan.md 5A and
   this task's build-log COMPLETE entry for exactly what's still manual).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import uuid

import pytest

from app.config import settings

# `TURSO_DATABASE_URL` is loaded via pydantic-settings' `env_file=".env"`
# (see app/config.py), not necessarily exported into `os.environ` — so the
# skip condition checks the parsed setting, not the raw environment, or
# this would always skip locally even with a real `.env` present. CI (no
# `.env` file, no real env var either way) correctly skips either way.
pytestmark = pytest.mark.skipif(
    not settings.turso_database_url,
    reason="TURSO_DATABASE_URL not configured — skipping real Turso integration test",
)

_PROBE_TABLE = "_litlist_task5a_probe"


def _run_python(code: str) -> str:
    """Run `code` in a brand-new `python` subprocess (a real cold-start-like
    fresh interpreter, not just a cleared in-process cache) and return
    stdout, raising if it exits non-zero."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"subprocess failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout


@pytest.fixture(autouse=True)
def _cleanup_probe_table():
    yield
    from app import db

    db.reset_engine_cache()
    engine = db.get_engine()
    with engine.connect() as conn:
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {_PROBE_TABLE}")
        conn.commit()
    db.reset_engine_cache()


def test_real_turso_write_and_read_via_db_module() -> None:
    """In-process: app.db.get_engine() authenticates and round-trips a row
    against the real Turso database (the literal fix for Task 5A's bug)."""
    from app import db

    db.reset_engine_cache()
    engine = db.get_engine()

    marker = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.exec_driver_sql(
            f"CREATE TABLE IF NOT EXISTS {_PROBE_TABLE} "
            "(id INTEGER PRIMARY KEY, note TEXT)"
        )
        conn.commit()
        conn.exec_driver_sql(
            f"INSERT INTO {_PROBE_TABLE} (note) VALUES ('{marker}')"
        )
        conn.commit()
        row = conn.exec_driver_sql(
            f"SELECT note FROM {_PROBE_TABLE} WHERE note = '{marker}'"
        ).fetchone()

    assert row is not None
    assert row[0] == marker


def test_real_turso_row_survives_a_fresh_process(capsys) -> None:
    """Cross-process: write a row from this test process, then read it back
    from a completely separate `python -c ...` invocation (fresh interpreter,
    fresh engine, fresh connection) — the closest available proxy for
    surviving a Render spin-down/restart without an actual Render deploy."""
    from app import db

    db.reset_engine_cache()
    engine = db.get_engine()
    marker = str(uuid.uuid4())

    with engine.connect() as conn:
        conn.exec_driver_sql(
            f"CREATE TABLE IF NOT EXISTS {_PROBE_TABLE} "
            "(id INTEGER PRIMARY KEY, note TEXT)"
        )
        conn.commit()
        conn.exec_driver_sql(
            f"INSERT INTO {_PROBE_TABLE} (note) VALUES ('{marker}')"
        )
        conn.commit()
    db.reset_engine_cache()

    reader_code = textwrap.dedent(
        f"""
        from app import db
        db.reset_engine_cache()
        engine = db.get_engine()
        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT note FROM {_PROBE_TABLE} WHERE note = '{marker}'"
            ).fetchone()
        print(row[0] if row else "MISSING")
        """
    )
    stdout = _run_python(reader_code)
    read_back = stdout.strip().splitlines()[-1]

    assert read_back == marker, (
        f"Row written by this process was not visible from a fresh "
        f"subprocess — got {read_back!r}, expected {marker!r}"
    )
