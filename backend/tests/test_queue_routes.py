"""Task 3A tests for `GET /queue` and `GET /papers/{pmid}/abstract`
(SPEC.md §10.4, §7.9's transparent pagination follow-up, §9.2/§13.6's
cached-Paper-keeps-serving-during-downtime contract)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel

from app.clients import get_icite_client, get_pubmed_client
from app.integrations.pubmed import PubMedParseError
from app.middleware.session import SessionIdentityMiddleware, reset_fallback_cookie_secret_for_tests
from app.models.entities import Paper, SearchSession
from app.models.entities import Session as SessionRow
from app.routes.queue import router as queue_router
from app.routes.search import router as search_router
from tests._fakes import (
    FakeICiteClient,
    FakePubMedClient,
    make_efetch_article,
    make_esearch_result,
    make_esummary_record,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(queue_router, prefix="/api/v1")
    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _reset_cookie_secret(db_engine):
    reset_fallback_cookie_secret_for_tests()
    SQLModel.metadata.create_all(db_engine)


async def _run_search(client: httpx.AsyncClient, query: str = "cancer") -> None:
    response = await client.post("/api/v1/search", json={"query": query})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_queue_with_no_prior_search_is_empty(db_engine) -> None:
    app = _make_app()
    app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient()
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.get("/api/v1/queue")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total_count": 0, "has_more": False}


@pytest.mark.asyncio
async def test_queue_returns_existing_decisions_without_calling_pubmed_again(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=2),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        await _run_search(client)
        calls_before = len(fake_pubmed.esearch_calls)
        response = await client.get("/api/v1/queue")

    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == ["1", "2"]
    assert body["total_count"] == 2
    assert body["has_more"] is False
    # 2 results total, both already fetched — no follow-up ESearch call.
    assert len(fake_pubmed.esearch_calls) == calls_before


@pytest.mark.asyncio
async def test_queue_cross_session_isolation(db_engine) -> None:
    """§9.1/§9.2's session-scoping is the actual security boundary
    between two anonymous users' queues — session A's `GET /queue` must
    never see session B's `QueueDecision` rows, even when both ran a
    search that happens to return an overlapping PMID. Uses two
    independent `httpx.AsyncClient` instances (separate cookie jars)
    against the *same* app/DB so each genuinely gets its own
    `session_id` via the middleware (mirrors Task 3C's
    `test_export_never_leaks_another_sessions_saved_papers` pattern),
    rather than asserting this from reading the query alone."""
    app = _make_app()
    fake_pubmed_a = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=2),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed_a
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client_a, await _client(app) as client_b:
        await _run_search(client_a, query="cancer")

        # Session B's own search returns a different page, but
        # deliberately overlaps PMID "2" with session A's — the sharpest
        # version of the cross-session leak this test guards against.
        app.dependency_overrides[get_pubmed_client] = lambda: FakePubMedClient(
            esearch_result=make_esearch_result(["2", "3"], count=2),
            esummary_records=[make_esummary_record("2"), make_esummary_record("3")],
        )
        await _run_search(client_b, query="diabetes")

        response_a = await client_a.get("/api/v1/queue")
        response_b = await client_b.get("/api/v1/queue")

    assert {item["pmid"] for item in response_a.json()["items"]} == {"1", "2"}
    assert {item["pmid"] for item in response_b.json()["items"]} == {"2", "3"}
    # Neither response leaks the other session's exclusive PMID.
    assert "3" not in {item["pmid"] for item in response_a.json()["items"]}
    assert "1" not in {item["pmid"] for item in response_b.json()["items"]}


@pytest.mark.asyncio
async def test_queue_item_reflects_persisted_retracted_flag(db_engine) -> None:
    """SPEC.md §13.4's "Retracted" badge (StackScreen.tsx) needs a real
    data path from `Paper.retracted` through to the queue response — this
    is the regression test for that field actually surviving DB -> API."""
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1"], count=1),
        esummary_records=[make_esummary_record("1")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        await _run_search(client)

        # Simulate the abstract endpoint having already run EFetch for
        # this PMID and found it retracted (§13.4) — same DB row a real
        # `GET /papers/1/abstract` cache-miss would update.
        with DBSession(db_engine) as db:
            paper = db.get(Paper, "1")
            assert paper is not None
            paper.retracted = True
            db.add(paper)
            db.commit()

        response = await client.get("/api/v1/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["retracted"] is True


@pytest.mark.asyncio
async def test_queue_pagination_follow_up_when_running_low(db_engine) -> None:
    app = _make_app()
    # Page 1: only 2 results returned even though 10 exist total, so the
    # queue is immediately "running low" (< LOW_WATERMARK=5 pending).
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=10),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        await _run_search(client)

        fake_pubmed.esearch_result = make_esearch_result(["3", "4"], count=10)
        fake_pubmed.esummary_records = [make_esummary_record("3"), make_esummary_record("4")]
        response = await client.get("/api/v1/queue")

    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == ["1", "2", "3", "4"]
    assert len(fake_pubmed.esearch_calls) == 2
    assert fake_pubmed.esearch_calls[1]["retstart"] == 20


@pytest.mark.asyncio
async def test_queue_serves_cached_decisions_when_pagination_follow_up_fails(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        esearch_result=make_esearch_result(["1", "2"], count=10),
        esummary_records=[make_esummary_record("1"), make_esummary_record("2")],
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        await _run_search(client)
        fake_pubmed.unavailable = True
        response = await client.get("/api/v1/queue")

    # Already-cached decisions still serve normally (§9.2/§13.6) even
    # though the pagination follow-up itself failed.
    assert response.status_code == 200
    body = response.json()
    assert [item["pmid"] for item in body["items"]] == ["1", "2"]


@pytest.mark.asyncio
async def test_queue_returns_service_unavailable_when_nothing_cached_and_pubmed_down(
    db_engine,
) -> None:
    app = _make_app()
    with DBSession(db_engine) as db:
        session = SessionRow()
        db.add(session)
        db.add(
            SearchSession(
                session_id=session.session_id,
                query="cancer",
                total_result_count=10,
                next_retstart=0,
            )
        )
        db.commit()
        session_id = session.session_id

    fake_pubmed = FakePubMedClient(unavailable=True)
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        from app.middleware.session import _sign

        client.cookies.set("litlist_session", _sign(session_id))
        response = await client.get("/api/v1/queue")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


@pytest.mark.asyncio
async def test_abstract_cache_miss_fetches_and_persists(db_engine) -> None:
    app = _make_app()
    article = make_efetch_article("1")
    fake_pubmed = FakePubMedClient(efetch_articles=[article])
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.get("/api/v1/papers/1/abstract")

    assert response.status_code == 200
    body = response.json()
    assert body["pmid"] == "1"
    assert body["narration_unavailable"] is False
    assert body["segments"][0]["kind"] == "section_header"
    assert fake_pubmed.efetch_calls == [["1"]]

    with DBSession(db_engine) as db:
        paper = db.get(Paper, "1")
        assert paper is not None
        assert paper.display_abstract
        assert paper.spoken_abstract
        assert paper.abstract_sections is not None


@pytest.mark.asyncio
async def test_abstract_cache_hit_is_a_genuine_round_trip_of_the_first_fetch(db_engine) -> None:
    """Strengthened per tester's TASK 3A VERIFY note: rather than seeding
    `Paper.abstract_sections` directly via a DB insert and only spot-
    checking one field, this issues two real HTTP requests through the
    live API — request 1 is a genuine cache miss (calls the fake EFetch),
    request 2 must be an exact cache hit (zero further EFetch calls) —
    and asserts the two full JSON response bodies are byte-for-byte
    identical, proving the cached reconstruction really does reproduce
    what a fresh fetch would have produced, not just "some" response."""
    app = _make_app()
    article = make_efetch_article("1")
    fake_pubmed = FakePubMedClient(efetch_articles=[article])
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        first = await client.get("/api/v1/papers/1/abstract")
        assert first.status_code == 200
        assert fake_pubmed.efetch_calls == [["1"]]  # genuine cache miss

        second = await client.get("/api/v1/papers/1/abstract")
        assert second.status_code == 200
        # No second EFetch call — this really was a cache hit, not a
        # second live fetch that happened to agree.
        assert fake_pubmed.efetch_calls == [["1"]]

    assert first.json() == second.json()
    assert second.json()["segments"][0]["display_text"] == "Background"


@pytest.mark.asyncio
async def test_abstract_pubmed_unavailable_on_cache_miss_returns_service_unavailable(
    db_engine,
) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(unavailable=True)
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.get("/api/v1/papers/999/abstract")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_abstract_not_found_when_pubmed_has_no_record(db_engine) -> None:
    app = _make_app()
    fake_pubmed = FakePubMedClient(efetch_articles=[])
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.get("/api/v1/papers/999/abstract")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_abstract_systemic_parse_failure_is_internal_error_not_not_found(
    db_engine,
) -> None:
    """Adversarial review (TASK 3A REVIEW finding #2): a `PubMedParseError`
    (every article in an EFetch response failing to parse — a likely
    schema-drift bug) must surface as `internal_error` (500), never the
    same `not_found` (404) a genuinely nonexistent PMID gets — otherwise
    a real, systemic backend bug would be indistinguishable from routine
    404 traffic to any monitoring watching status codes."""
    app = _make_app()
    fake_pubmed = FakePubMedClient(
        efetch_exception=PubMedParseError("EFetch returned 1 article(s) but none could be parsed.")
    )
    app.dependency_overrides[get_pubmed_client] = lambda: fake_pubmed
    app.dependency_overrides[get_icite_client] = lambda: FakeICiteClient()

    async with await _client(app) as client:
        response = await client.get("/api/v1/papers/1/abstract")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    # No raw exception text/internals leaked in the client-facing message.
    assert "PubMedParseError" not in response.text
    assert "Traceback" not in response.text
