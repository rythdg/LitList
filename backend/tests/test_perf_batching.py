"""TASK PERF-1 regression tests: the search/queue path must issue a
BOUNDED number of DB statements per request, never one-per-pmid.

Live diagnosis (user-reported 33-46s searches): the deployed backend
talks to a remote Turso database where every statement is a full network
round-trip (~200-300ms from Render), and the search path was issuing
~50-100 SEQUENTIAL round-trips — per-pmid `db.get(Paper, ...)` loops in
`_shared.py`, a per-row stale-decision delete loop in `search.py`, a
per-decision `db.get` loop in `queue.py`, and an unconditional
UPDATE+COMMIT+refresh+ZoteroConnection-SELECT in the session middleware
on every request.

These tests count actual cursor executions via SQLAlchemy's
`before_cursor_execute` hook (one event per statement, including a
single event for an executemany batch), so a reintroduced N+1 loop
fails loudly instead of only showing up as production latency.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel

from app.clients import get_icite_client, get_pubmed_client
from app.middleware.session import (
    SessionIdentityMiddleware,
    get_current_session,
    reset_fallback_cookie_secret_for_tests,
)
from app.models.entities import Paper
from app.routes._shared import apply_citation_counts, upsert_papers_from_esummary
from app.routes.search import router as search_router
from tests._fakes import (
    FakeICiteClient,
    FakePubMedClient,
    make_esearch_result,
    make_esummary_record,
)

PAGE_PMIDS = [str(1000 + i) for i in range(20)]


@contextmanager
def count_statements(engine: Engine) -> Iterator[list[str]]:
    """Collect every statement executed on `engine` (an executemany batch
    counts once — which is exactly the round-trip semantics we care
    about)."""
    statements: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]  # noqa: E501
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


def _selects(statements: list[str], table: str) -> list[str]:
    return [s for s in statements if s.lstrip().upper().startswith("SELECT") and table in s]


@pytest.fixture(autouse=True)
def _fresh(db_engine: Engine) -> None:
    reset_fallback_cookie_secret_for_tests()
    SQLModel.metadata.create_all(db_engine)


# ---------------------------------------------------------------------
# Helper-level batching (`_shared.py`)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_papers_issues_one_select_for_the_whole_batch(db_engine: Engine) -> None:
    # Seed a few pre-existing rows so both the update and insert branches run.
    with DBSession(db_engine) as db:
        for pmid in PAGE_PMIDS[:5]:
            db.add(Paper(pmid=pmid, title="stale title"))
        db.commit()

    records = [make_esummary_record(pmid) for pmid in PAGE_PMIDS]
    with DBSession(db_engine) as db, count_statements(db_engine) as statements:
        papers = await upsert_papers_from_esummary(db, records)
        db.commit()

    # Exactly one SELECT against paper for all 20 pmids — not 20.
    assert len(_selects(statements, "paper")) == 1
    # Same result contract as the per-pmid version: every pmid mapped,
    # existing rows refreshed in place, new rows created.
    assert set(papers) == set(PAGE_PMIDS)
    with DBSession(db_engine) as db:
        refreshed = db.get(Paper, PAGE_PMIDS[0])
        assert refreshed is not None
        assert refreshed.title == f"Title for {PAGE_PMIDS[0]}"


@pytest.mark.asyncio
async def test_apply_citation_counts_available_branch_is_batched(db_engine: Engine) -> None:
    with DBSession(db_engine) as db:
        records = [make_esummary_record(pmid) for pmid in PAGE_PMIDS]
        await upsert_papers_from_esummary(db, records)
        db.commit()

    icite = FakeICiteClient(counts={pmid: int(pmid) for pmid in PAGE_PMIDS[:10]})
    with DBSession(db_engine) as db, count_statements(db_engine) as statements:
        counts = await apply_citation_counts(db, icite, PAGE_PMIDS)
        db.commit()

    assert len(_selects(statements, "paper")) == 1
    # §7.6 semantics preserved: counted pmids get their count, uncounted
    # pmids fall back to the Paper row's existing (None) value.
    assert counts[PAGE_PMIDS[0]] == int(PAGE_PMIDS[0])
    assert counts[PAGE_PMIDS[-1]] is None
    with DBSession(db_engine) as db:
        persisted = db.get(Paper, PAGE_PMIDS[0])
        assert persisted is not None
        assert persisted.citation_count == int(PAGE_PMIDS[0])


@pytest.mark.asyncio
async def test_apply_citation_counts_unavailable_branch_is_batched_and_writes_nothing(
    db_engine: Engine,
) -> None:
    """§7.6's graceful degradation: iCite down leaves existing (possibly
    stale-but-real) counts untouched — and now does it in one SELECT with
    zero writes."""
    with DBSession(db_engine) as db:
        db.add(Paper(pmid=PAGE_PMIDS[0], title="t", citation_count=7))
        db.add(Paper(pmid=PAGE_PMIDS[1], title="t"))
        db.commit()

    icite = FakeICiteClient(available=False)
    with DBSession(db_engine) as db, count_statements(db_engine) as statements:
        counts = await apply_citation_counts(db, icite, PAGE_PMIDS[:3])

    assert len(_selects(statements, "paper")) == 1
    assert not [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE"))]
    assert counts == {PAGE_PMIDS[0]: 7, PAGE_PMIDS[1]: None, PAGE_PMIDS[2]: None}


# ---------------------------------------------------------------------
# Whole-request budget (`POST /search`)
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_request_statement_count_is_bounded_not_per_pmid(
    db_engine: Engine,
) -> None:
    """A 20-result `POST /search` must stay within a small fixed
    statement budget. Before PERF-1 this path executed 60+ statements
    (20 Paper gets in the upsert, 20 per-row decision INSERTs, per-row
    stale-decision handling, middleware refresh + Zotero SELECT)."""
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(search_router, prefix="/api/v1")
    app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient(
        esearch_result=make_esearch_result(PAGE_PMIDS, count=40),
        esummary_records=[make_esummary_record(pmid) for pmid in PAGE_PMIDS],
    )
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        with count_statements(db_engine) as statements:
            response = await client.post("/api/v1/search", json={"query": "cancer"})

    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == PAGE_PMIDS
    assert body["total_count"] == 40

    # One batched Paper SELECT, one bulk stale-decision DELETE, one
    # executemany decision INSERT — never one statement per pmid.
    assert len(_selects(statements, "paper")) == 1
    assert len([s for s in statements if s.lstrip().upper().startswith("DELETE")]) == 1
    assert (
        len([s for s in statements if "INSERT" in s.upper() and "queue_decision" in s]) == 1
    )
    # Generous fixed ceiling for the whole request (middleware included):
    # far below the ~60+ statements of the per-pmid version, and safe
    # headroom against dialect-level differences.
    assert len(statements) <= 12, statements


# ---------------------------------------------------------------------
# Middleware round-trips
# ---------------------------------------------------------------------


def _session_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)

    @app.get("/whoami")
    def whoami(request: Request) -> dict[str, str]:
        return {"session_id": get_current_session(request).session_id}

    return app


def test_repeat_request_within_last_seen_window_issues_no_writes(db_engine: Engine) -> None:
    client = TestClient(_session_app(), base_url="https://testserver")

    first = client.get("/whoami")
    assert first.status_code == 200

    with count_statements(db_engine) as statements:
        second = client.get("/whoami")

    assert second.status_code == 200
    assert second.json() == first.json()
    # Same session, no rotation — and, within the 60s last_seen window,
    # no INSERT/UPDATE at all: the request is a single session SELECT.
    writes = [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE"))]
    assert writes == []


def test_non_zotero_route_never_queries_zotero_connection(db_engine: Engine) -> None:
    """The ZoteroConnection lookup is lazy (dependency-driven) now — a
    route that never uses `get_current_zotero_connection` must not pay
    for the SELECT."""
    client = TestClient(_session_app(), base_url="https://testserver")

    with count_statements(db_engine) as statements:
        response = client.get("/whoami")

    assert response.status_code == 200
    assert not [s for s in statements if "zotero_connection" in s]
