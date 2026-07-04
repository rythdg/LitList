"""Task 3A tests for `POST /search` and `GET /search/settings`
(SPEC.md §10.4, §7.9's zero-result/pagination edge cases, §13.6's
external-downtime handling), per §15.3's backend integration-test
convention: `httpx.AsyncClient` against a real (file-backed, per-test)
SQLite DB, with Task 1B's PubMed/iCite clients replaced by fakes
(`tests/_fakes.py`) rather than any real network call.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from app.clients import get_icite_client, get_pubmed_client
from app.middleware.session import SessionIdentityMiddleware, reset_fallback_cookie_secret_for_tests
from app.models.entities import QueueDecision, SearchSession
from app.routes.search import router as search_router
from tests._fakes import (
    FakeICiteClient,
    FakePubMedClient,
    make_esearch_result,
    make_esummary_record,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(search_router, prefix="/api/v1")
    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _reset_cookie_secret(db_engine):
    reset_fallback_cookie_secret_for_tests()
    SQLModel.metadata.create_all(db_engine)


@pytest.mark.asyncio
async def test_search_happy_path_creates_queue(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=2),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.post("/api/v1/search", json={"query": "cancer"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert [item["pmid"] for item in body["items"]] == ["1", "2"]
    assert body["items"][0]["decision"] == "pending"
    assert body["has_more"] is False

    with DBSession(db_engine) as db:
        decisions = db.exec(select(QueueDecision)).all()
        assert len(decisions) == 2
        search_session = db.exec(select(SearchSession)).one()
        assert search_session.query == "cancer"


@pytest.mark.asyncio
async def test_search_cross_session_isolation(db_engine) -> None:
    """§9.1/§9.2's session-scoping is the actual security boundary
    between two anonymous users — flagged by adversarial review (TASK 3A
    REVIEW finding #1) as the one class of gap tester's earlier rounds
    fixed for queue/saved/decisions but never checked here, even though
    `POST /search` performs the exact same kind of session-scoped
    mutation (wiping/rebuilding `QueueDecision` rows, upserting
    `SearchSession` settings). Mirrors the same two-independent-client,
    overlapping-PMID pattern already used in test_queue_routes.py/
    test_saved_routes.py/test_decisions_routes.py/Task 3C's export test.

    Deliberately exercises the sharpest version of the risk this filter
    guards against: session A re-searching (which wipes and rebuilds
    *its own* `QueueDecision` rows, per §3.5) must never touch session
    B's rows or settings, even though both sessions' PMID sets overlap
    and B searched first."""
    app = _make_app()

    fake_pubmed_b = FakePubMedClient(
        esearch_result=make_esearch_result(["2", "3"], count=2),
        esummary_records=[make_esummary_record("2"), make_esummary_record("3")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed_b
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client_a, await _client(app) as client_b:
        # Session B searches first and saves a settled state.
        await client_b.post("/api/v1/search", json={"query": "diabetes", "sort": "recency"})

        # Session A searches, overlapping PMID "2" with session B.
        app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient(
            esearch_result=make_esearch_result(["1", "2"], count=2),
            esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
        )
        await client_a.post("/api/v1/search", json={"query": "cancer", "sort": "relevance"})

        # Session A re-searches (§3.5's replace-in-place path — this is
        # exactly the delete-then-rebuild step that must stay scoped to
        # session A's own QueueDecision rows).
        app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient(
            esearch_result=make_esearch_result(["4"], count=1),
            esummary_records=[make_esummary_record("4")],
        )
        response_a = await client_a.post(
            "/api/v1/search", json={"query": "cancer round 2", "sort": "relevance"}
        )
        assert response_a.status_code == 200

        settings_a = await client_a.get("/api/v1/search/settings")
        settings_b = await client_b.get("/api/v1/search/settings")

    # Each session's own settings reflect only its own last search.
    assert settings_a.json()["query"] == "cancer round 2"
    assert settings_b.json()["query"] == "diabetes"
    assert settings_b.json()["sort"] == "recency"

    with DBSession(db_engine) as db:
        search_sessions = db.exec(select(SearchSession)).all()
        assert {s.query for s in search_sessions} == {"cancer round 2", "diabetes"}

        all_decisions = db.exec(select(QueueDecision)).all()
        by_session: dict[str, set[str]] = {}
        for decision in all_decisions:
            by_session.setdefault(decision.session_id, set()).add(decision.pmid)

        session_a_id = next(s.session_id for s in search_sessions if s.query == "cancer round 2")
        session_b_id = next(s.session_id for s in search_sessions if s.query == "diabetes")

        # Session A's re-search replaced its OWN queue (["1", "2"] -> ["4"])
        # without touching session B's original PMIDs at all.
        assert by_session[session_a_id] == {"4"}
        assert by_session[session_b_id] == {"2", "3"}


@pytest.mark.asyncio
async def test_search_zero_results_returns_empty_queue_no_further_calls(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(esearch_result=make_esearch_result([], count=0))
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.post("/api/v1/search", json={"query": "no such thing"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total_count": 0, "has_more": False}
    assert fake_pubmed.esummary_calls == []
    assert fake_pubmed.efetch_calls == []


@pytest.mark.asyncio
async def test_search_replaces_prior_queue_decisions(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1"], count=1),
        esummary_records=[make_esummary_record("1")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        first = await client.post("/api/v1/search", json={"query": "first query"})
        cookies = first.cookies

        fake_pubmed.esearch_result = make_esearch_result(["2"], count=1)
        fake_pubmed.esummary_records = [make_esummary_record("2")]
        client.cookies.update(cookies)
        second = await client.post("/api/v1/search", json={"query": "second query"})

    assert second.status_code == 200
    assert [item["pmid"] for item in second.json()["items"]] == ["2"]

    with DBSession(db_engine) as db:
        decisions = db.exec(select(QueueDecision)).all()
        assert [d.pmid for d in decisions] == ["2"]


@pytest.mark.asyncio
async def test_search_pubmed_unavailable_returns_service_unavailable(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(unavailable=True)
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.post("/api/v1/search", json={"query": "cancer"})

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert "PubMed" in body["error"]["message"]
    # No stack trace / exception internals leaked.
    assert "Traceback" not in response.text
    assert "PubMedUnavailableError" not in response.text


@pytest.mark.asyncio
async def test_search_validation_error_on_blank_query(db_engine) -> None:
    app = _make_app()
    app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient()
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.post("/api/v1/search", json={"query": "   "})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_search_validation_error_on_unknown_read_aloud_field(db_engine) -> None:
    app = _make_app()
    app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient()
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search",
            json={"query": "cancer", "read_aloud_fields": ["country"]},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_search_citations_sort_orders_by_citation_count(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=2),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient(counts={"1": 3, "2": 40})

    async with await _client(app) as client:
        response = await client.post(
            "/api/v1/search", json={"query": "cancer", "sort": "citations"}
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == ["2", "1"]
    assert body["items"][0]["citation_count"] == 40


@pytest.mark.asyncio
async def test_search_settings_defaults_when_no_prior_search(db_engine) -> None:
    app = _make_app()

    async with await _client(app) as client:
        response = await client.get("/api/v1/search/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] is None
    assert body["sort"] == "relevance"


@pytest.mark.asyncio
async def test_search_settings_reflects_last_search(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(esearch_result=make_esearch_result([], count=0))
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        await client.post(
            "/api/v1/search",
            json={"query": "diabetes", "sort": "recency", "speed": 1.5},
        )
        response = await client.get("/api/v1/search/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "diabetes"
    assert body["sort"] == "recency"
    assert body["speed"] == 1.5
