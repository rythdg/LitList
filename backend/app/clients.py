"""FastAPI dependency providers for Task 1B's outbound wrapper clients
(`PubMedClient`, `ICiteClient`).

Not explicitly named in BuildPlan.md's Task 3A ownership list, same
rationale as `app/errors.py`: `search.py`, `queue.py` both need the same
two clients, and §10.5 requires that no route talk to `httpx` directly —
routes depend on these provider functions (`Depends(get_pubmed_client)`)
rather than importing/constructing `PubMedClient()` themselves, which
also lets tests swap in a fake/mocked client via
`app.dependency_overrides` instead of monkeypatching module internals or
using `respx` against real network calls (disallowed in tests per this
task's brief).

`lru_cache` gives one shared instance per process — required so the
`RateLimiter` inside `PubMedClient` (§7.7) actually paces *all* outbound
calls through one bucket, not a fresh one per request.
"""

from __future__ import annotations

from functools import lru_cache

from app.integrations.icite import ICiteClient
from app.integrations.pubmed import PubMedClient


@lru_cache(maxsize=1)
def get_pubmed_client() -> PubMedClient:
    return PubMedClient()


@lru_cache(maxsize=1)
def get_icite_client() -> ICiteClient:
    return ICiteClient()
