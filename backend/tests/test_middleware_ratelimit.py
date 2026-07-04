"""Task 3D tests, SPEC.md §10.5's inbound half — `app/middleware/
ratelimit.py`'s per-IP (primary) / per-session (secondary) inbound
throttling.

**Deliberately a separate test file from Task 1B's outbound-pacing
tests** (`tests/test_pubmed_client.py`/`test_icite_client.py`), per this
task's brief: outbound pacing governs how fast *this backend* calls
PubMed/iCite/Zotero; this module governs how fast an individual caller
may call *LitList's own* API, independent of any outbound call. Nothing
here touches `app/integrations/*`, and nothing there is re-tested here.

Builds a minimal app assembled the same way `app/main.py` does (session
identity, then the rate limiter) rather than importing the real Wave-1
routers, so these tests exercise the threshold/keying logic in isolation
and don't need a live PubMed/iCite fake.

**Why IP-primary, not session-primary — see `ratelimit.py`'s own
docstring for the full account.** An earlier version of this module
keyed strictly off `session_id`, which adversarial review proved
trivially bypassable: `SessionIdentityMiddleware` mints a brand-new,
free session for any cookie-less request, so a caller could get an
unlimited number of fresh rate-limit buckets simply by never sending a
cookie. `test_ip_cap_engages_even_when_every_request_uses_a_fresh_
session_and_no_cookie` below reproduces that exact attack (many
requests, each with its own brand-new session, all from the same source
IP — which is what every request in this test file naturally is, since
`TestClient`/`httpx.ASGITransport` all originate from the same fixed
test-client IP) and asserts the limiter now actually engages, unlike the
dead-end IP-*fallback* test this replaces.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.middleware.ratelimit import (
    InboundRateLimitMiddleware,
    reset_rate_limit_storage_for_tests,
)
from app.middleware.session import SessionIdentityMiddleware, reset_fallback_cookie_secret_for_tests

_API_PREFIX = "/api/v1"


def _make_app() -> FastAPI:
    app = FastAPI()
    # Same relative order as `app/main.py`: rate limiting added first
    # (innermost), session identity added second — so at request time,
    # per Starlette's outer-wraps-inner semantics, session resolution
    # actually runs *before* the rate limiter reads `request.state.session`.
    app.add_middleware(InboundRateLimitMiddleware, api_prefix=_API_PREFIX)
    app.add_middleware(SessionIdentityMiddleware)

    call_count = {"n": 0}
    app.state.call_count = call_count

    @app.post(f"{_API_PREFIX}/search")
    def fake_search() -> dict[str, int]:
        call_count["n"] += 1
        return {"n": call_count["n"]}

    @app.get(f"{_API_PREFIX}/search/settings")
    def fake_unlimited() -> dict[str, bool]:
        call_count["n"] += 1
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset_state(db_engine):
    reset_fallback_cookie_secret_for_tests()
    reset_rate_limit_storage_for_tests()
    SQLModel.metadata.create_all(db_engine)
    yield
    reset_rate_limit_storage_for_tests()


def _client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def test_requests_past_the_per_session_threshold_get_429() -> None:
    """`/search` is capped at 10/minute per session, on top of the
    30/minute per-IP ceiling (§10.5). A single, persistent session
    making 11 requests trips the *session*-level cap well before the
    shared IP-level one, and the 11th request must never reach the route
    handler at all (the handler's own side effect — here, incrementing
    `call_count` — must stop growing once the limit hits)."""
    app = _make_app()
    client = _client(app)

    statuses = [client.post(f"{_API_PREFIX}/search").status_code for _ in range(11)]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429

    final = client.post(f"{_API_PREFIX}/search")
    assert final.status_code == 429
    assert final.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Too many requests. Please wait a moment and try again.",
        }
    }
    # 10 successful hits + the two 429s should have only ever run the
    # handler body 10 times, never 11 or 12 — the 429s never reached it.
    assert app.state.call_count["n"] == 10


def test_ip_cap_engages_even_when_every_request_uses_a_fresh_session_and_no_cookie() -> None:
    """The literal adversarial-review reproduction: many requests, each
    one from a brand-new `TestClient` (fresh cookie jar, so
    `SessionIdentityMiddleware` mints an entirely new, never-before-seen
    `session_id` every single time) but all originating from the same
    source IP (every `TestClient` in this process shares the same fixed
    test-client address). `/search`'s IP ceiling is 30/minute — request
    #31 must be rejected, proving the per-session cap alone (which a
    fresh-session-per-request caller trivially resets every time) is not
    what's actually stopping this, the shared IP bucket is."""
    app = _make_app()

    statuses = []
    for _ in range(31):
        # A brand-new `TestClient` each iteration = a brand-new cookie
        # jar = no cookie sent = `SessionIdentityMiddleware` mints a
        # fresh `Session` row/`session_id` for this request, same as
        # adversarial review's "30 fresh cookie-less clients" repro.
        fresh_client = _client(app)
        statuses.append(fresh_client.post(f"{_API_PREFIX}/search").status_code)

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429
    assert app.state.call_count["n"] == 30


def test_two_distinct_persistent_sessions_sharing_an_ip_each_get_a_session_budget() -> None:
    """Legitimate multi-tab/shared-IP use isn't collapsed into a single
    global bucket: two distinct, *persistent* sessions (each reusing its
    own cookie across all of its own requests, unlike the fresh-session
    attack above) sharing one IP can each exhaust their own 10/minute
    session budget, as long as their combined total (20) stays under the
    30/minute IP ceiling — this is the "session_id as a secondary,
    finer-grained dimension" half of the design, not just the IP cap."""
    app = _make_app()
    client_a = _client(app)
    client_b = TestClient(app, base_url="https://testserver")

    for _ in range(10):
        assert client_a.post(f"{_API_PREFIX}/search").status_code == 200
    assert client_a.post(f"{_API_PREFIX}/search").status_code == 429

    for _ in range(10):
        assert client_b.post(f"{_API_PREFIX}/search").status_code == 200
    assert client_b.post(f"{_API_PREFIX}/search").status_code == 429


def test_ungated_route_is_not_rate_limited() -> None:
    """Only the specific endpoints §10.5 calls out (search, the abstract
    endpoint, Zotero push, export) are gated — a cheap, non-listed GET
    route must never 429 regardless of volume."""
    app = _make_app()
    client = _client(app)

    statuses = [
        client.get(f"{_API_PREFIX}/search/settings").status_code for _ in range(40)
    ]

    assert statuses == [200] * 40


def test_ip_key_and_session_key_helpers() -> None:
    """Direct unit coverage of the two key-building helpers themselves —
    `_ip_key` is unconditional; `_session_key` returns `None` (not a
    fallback identity) when no session has been resolved, since the
    primary defense no longer depends on a session ever existing."""
    from starlette.requests import Request

    from app.middleware.ratelimit import _ip_key, _session_key

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/search",
        "headers": [],
        "client": ("203.0.113.5", 12345),
    }
    request = Request(scope)
    assert _ip_key(request) == "ip:203.0.113.5"
    assert _session_key(request) is None
