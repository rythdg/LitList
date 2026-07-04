"""Tests for BuildPlan.md Task 1B's `pubmed_client` (SPEC.md §7 all).

Covers SPEC.md §15.1/§15.8's outbound half:
- ESearch/ESummary/EFetch parsing against Task 0.3's fixture payloads,
  mocked via `respx` — no real network calls.
- Zero-result handling (§7.9).
- Malformed/missing individual record handling (§7.9) — the batch
  continues, the bad record is skipped.
- Outbound pacing against a fake/injectable clock (§7.7, §15.8) — no real
  `sleep()` calls, so this stays fast.
- Mocked 429/`Retry-After` backoff (§7.9, §15.8).
- §13.3/§13.4 extraction: `Language` field and retracted-publication flag
  from EFetch.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.integrations.pubmed import (
    BASE_URL,
    Clock,
    PubMedClient,
    PubMedUnavailableError,
    RateLimiter,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "pubmed"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _load_xml(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


class FakeClock:
    """Deterministic clock for pacing/backoff tests — `sleep` advances a
    virtual counter instantly instead of actually waiting, per §15.8's
    "never real sleep() calls" requirement."""

    def __init__(self) -> None:
        self.time = 0.0
        self.sleep_calls: list[float] = []

    def now(self) -> float:
        return self.time

    async def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.time += seconds

    def as_clock(self) -> Clock:
        return Clock(now=self.now, sleep=self.sleep)


# ---------------------------------------------------------------------------
# ESearch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_esearch_parses_fixture_payload() -> None:
    fixture = _load_json("esearch_response.json")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        result = await client.esearch("sample query")

    assert result.count == 3
    assert result.pmids == ["38279812", "38279813", "37000001"]
    assert result.retstart == 0


@pytest.mark.asyncio
async def test_esearch_zero_results() -> None:
    fixture = _load_json("esearch_zero_results.json")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        result = await client.esearch("a deliberately over-specific query")

    assert result.count == 0
    assert result.pmids == []


# ---------------------------------------------------------------------------
# ESummary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_esummary_parses_fixture_payload_including_missing_doi() -> None:
    fixture = _load_json("esummary_response.json")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esummary.fcgi").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        records = await client.esummary(["38279812", "38279813", "37000001"])

    assert len(records) == 3
    by_pmid = {r.pmid: r for r in records}

    normal = by_pmid["38279812"]
    assert normal.title.startswith("Effects of early intervention")
    assert normal.last_author == "Alvarez S"
    assert normal.doi == "10.1234/jacr.2024.001812"

    # §13.4's missing-DOI edge case.
    no_doi = by_pmid["38279813"]
    assert no_doi.doi is None

    # Sparse/older record — empty lastauthor should normalize to None,
    # not an empty string, and title/journal should still parse.
    sparse = by_pmid["37000001"]
    assert sparse.last_author is None
    assert sparse.title == "Older record with sparse metadata"


@pytest.mark.asyncio
async def test_esummary_skips_missing_record_without_failing_batch() -> None:
    """§7.9: ESearch succeeds but ESummary is missing a specific PMID's
    DocSum entirely — that paper is skipped, not a fatal error."""
    fixture = _load_json("esummary_response.json")
    # Simulate PubMed reporting a 4th uid that has no corresponding DocSum
    # object in `result` (a real-world malformed/withdrawn-record case).
    fixture["result"]["uids"].append("99999999")

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esummary.fcgi").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        records = await client.esummary(["38279812", "38279813", "37000001", "99999999"])

    assert {r.pmid for r in records} == {"38279812", "38279813", "37000001"}


@pytest.mark.asyncio
async def test_esummary_empty_input_makes_no_request() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{BASE_URL}esummary.fcgi")
        client = PubMedClient(clock=FakeClock().as_clock())
        records = await client.esummary([])

    assert records == []
    assert route.call_count == 0


# ---------------------------------------------------------------------------
# EFetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_efetch_parses_fixture_including_structured_abstract() -> None:
    xml_body = _load_xml("efetch_response.xml")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml_body)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        articles = await client.efetch(["38279812", "38279813", "37000001"])

    assert len(articles) == 3
    by_pmid = {a.pmid: a for a in articles}

    normal = by_pmid["38279812"]
    assert normal.language == "eng"
    assert normal.retracted is False
    labels = [s.label for s in normal.abstract_sections]
    assert labels == ["BACKGROUND", "METHODS", "RESULTS", "CONCLUSIONS"]
    assert "Fig. 2" in normal.abstract_sections[0].text
    assert normal.doi == "10.1234/jacr.2024.001812"
    assert normal.authors[0].last_name == "Alvarez"


@pytest.mark.asyncio
async def test_efetch_extracts_retracted_flag() -> None:
    """§13.4: 'Retracted Publication' PublicationType -> retracted=True,
    consumed later by Task 2B's badge."""
    xml_body = _load_xml("efetch_response.xml")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml_body)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        articles = await client.efetch(["38279813"])

    retracted_article = next(a for a in articles if a.pmid == "38279813")
    assert retracted_article.retracted is True
    assert "Retracted Publication" in retracted_article.publication_types
    assert retracted_article.doi is None


@pytest.mark.asyncio
async def test_efetch_extracts_language_for_mismatch_check() -> None:
    """§13.3: non-English `Language` field captured for Task 1D to key its
    narration-unavailable flag off."""
    xml_body = _load_xml("efetch_response.xml")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml_body)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        articles = await client.efetch(["37000001"])

    french_article = next(a for a in articles if a.pmid == "37000001")
    assert french_article.language == "fre"


@pytest.mark.asyncio
async def test_efetch_skips_malformed_record_without_failing_batch() -> None:
    """§7.9: a malformed record (missing PMID) is skipped, the rest of the
    batch still parses."""
    xml_body = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Missing PMID, should be skipped</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Well-formed sibling record</ArticleTitle>
        <Language>eng</Language>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}efetch.fcgi").mock(
            return_value=httpx.Response(200, text=xml_body)
        )
        client = PubMedClient(clock=FakeClock().as_clock())
        articles = await client.efetch(["00000000", "12345678"])

    assert len(articles) == 1
    assert articles[0].pmid == "12345678"


# ---------------------------------------------------------------------------
# Outbound pacing (§7.7, §15.8) — fake clock, no real sleeps.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_paces_calls_without_real_sleep() -> None:
    fake = FakeClock()
    limiter = RateLimiter(10.0, clock=fake.as_clock())  # 0.1s min interval

    for _ in range(5):
        await limiter.acquire()

    # 5 calls at 10 req/s => 4 waits of ~0.1s each, entirely on the fake
    # clock — this assertion would be flaky/slow if this were a real sleep.
    assert fake.time == pytest.approx(0.4)
    assert len(fake.sleep_calls) == 4


@pytest.mark.asyncio
async def test_rate_limiter_no_wait_if_calls_already_spaced_out() -> None:
    fake = FakeClock()
    limiter = RateLimiter(10.0, clock=fake.as_clock())

    await limiter.acquire()
    fake.time += 1.0  # plenty of time passes between calls
    await limiter.acquire()

    assert fake.sleep_calls == []


@pytest.mark.asyncio
async def test_esearch_uses_shared_rate_limiter_across_calls() -> None:
    """Two ESearch calls in a row on one client should be paced against
    each other, proving `_get` actually routes through the limiter."""
    fixture = _load_json("esearch_response.json")
    fake = FakeClock()
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        client = PubMedClient(clock=fake.as_clock())
        await client.esearch("q1")
        await client.esearch("q2")

    # With an API key unset in test settings, rate = 3 req/s => min
    # interval ~0.333s; the second call must have waited at least once.
    assert len(fake.sleep_calls) == 1
    assert fake.sleep_calls[0] == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# 429 / Retry-After backoff (§7.9, §15.8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backoff_retries_after_429_then_succeeds() -> None:
    fixture = _load_json("esearch_response.json")
    fake = FakeClock()

    call_count = 0

    def _responder(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"error": "API rate limit exceeded"},
            )
        return httpx.Response(200, json=fixture)

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(side_effect=_responder)
        client = PubMedClient(clock=fake.as_clock())
        result = await client.esearch("q")

    assert result.pmids == ["38279812", "38279813", "37000001"]
    assert call_count == 2
    # The 2-second Retry-After backoff must show up as a fake-clock sleep,
    # not a real wall-clock wait.
    assert 2.0 in fake.sleep_calls


@pytest.mark.asyncio
async def test_backoff_raises_after_retries_exhausted() -> None:
    fake = FakeClock()

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "1"})
        )
        client = PubMedClient(clock=fake.as_clock(), max_retry_attempts=2)
        with pytest.raises(PubMedUnavailableError):
            await client.esearch("q")


@pytest.mark.asyncio
async def test_network_error_raises_pubmed_unavailable() -> None:
    fake = FakeClock()
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = PubMedClient(clock=fake.as_clock(), max_retry_attempts=1)
        with pytest.raises(PubMedUnavailableError):
            await client.esearch("q")


# ---------------------------------------------------------------------------
# Non-429/5xx 4xx responses must not leak credentials (adversarial review
# finding — SPEC.md §10.3/§9.6's "secrets never appear in ... logs" applies
# to raised-exception messages too, since CONTRACTS.md documents an
# eventual catch-all handler (Task 3D) that will very likely log an
# unhandled exception's `str()` verbatim).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_403_response_does_not_leak_api_key_or_email_in_exception(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ncbi_api_key", "SEKRET123")
    monkeypatch.setattr(settings, "ncbi_email", "secret@example.com")

    fake = FakeClock()
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(return_value=httpx.Response(403))
        client = PubMedClient(clock=fake.as_clock(), max_retry_attempts=0)
        with pytest.raises(PubMedUnavailableError) as excinfo:
            await client.esearch("q")

    message = str(excinfo.value)
    assert "SEKRET123" not in message
    assert "secret@example.com" not in message
    # Also guard the chained/underlying exception, in case some future
    # refactor reintroduces `raise ... from exc` with an httpx exception
    # whose own __str__ embeds the request URL.
    cause = excinfo.value.__cause__
    if cause is not None:
        assert "SEKRET123" not in str(cause)
        assert "secret@example.com" not in str(cause)


@pytest.mark.asyncio
async def test_400_response_raises_pubmed_unavailable() -> None:
    """A malformed-query 400 (not 429/5xx) must still surface as a clean,
    sanitized `PubMedUnavailableError`, not an uncaught `httpx.HTTPStatusError`."""
    fake = FakeClock()
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE_URL}esearch.fcgi").mock(return_value=httpx.Response(400))
        client = PubMedClient(clock=fake.as_clock(), max_retry_attempts=0)
        with pytest.raises(PubMedUnavailableError):
            await client.esearch("q")
