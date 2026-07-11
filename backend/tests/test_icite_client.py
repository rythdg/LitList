"""Tests for BuildPlan.md Task 1B's iCite client (SPEC.md §7.6, §15.1).

Covers the fixture-based happy path (including iCite's documented
coverage gap — not every PMID has citation data yet) and the graceful-
degradation-on-unreachable path required by §7.6/BuildPlan.md 1B, mocked
here as a connection error since the fixture note calls out that this
case "is not representable as a fixture payload."
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.integrations.icite import BASE_URL, ICiteClient

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "pubmed"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.mark.asyncio
async def test_fetch_citation_counts_parses_fixture_payload() -> None:
    fixture = _load_json("icite_response.json")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(BASE_URL).mock(return_value=httpx.Response(200, json=fixture))
        client = ICiteClient()
        result = await client.fetch_citation_counts(["38279812", "38279813", "37000001"])

    assert result.available is True
    assert result.counts["38279812"] == 12
    assert result.counts["38279813"] == 0
    # §7.6's coverage-lag note: 37000001 is deliberately absent from the
    # fixture's `data` — no citation count available yet, not an error.
    assert "37000001" not in result.counts


@pytest.mark.asyncio
async def test_fetch_citation_counts_empty_input_makes_no_request() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(BASE_URL)
        client = ICiteClient()
        result = await client.fetch_citation_counts([])

    assert result.available is True
    assert result.counts == {}
    assert route.call_count == 0


@pytest.mark.asyncio
async def test_fetch_citation_counts_degrades_gracefully_on_connection_error() -> None:
    """§7.6: iCite unreachable -> `available=False`, never an exception —
    callers fall back to Relevance sort rather than the whole search
    breaking."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(BASE_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        client = ICiteClient()
        result = await client.fetch_citation_counts(["38279812"])

    assert result.available is False
    assert result.counts == {}


@pytest.mark.asyncio
async def test_fetch_citation_counts_degrades_gracefully_on_5xx() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(BASE_URL).mock(return_value=httpx.Response(503))
        client = ICiteClient()
        result = await client.fetch_citation_counts(["38279812"])

    assert result.available is False
    assert result.counts == {}


# ---------------------------------------------------------------------------
# PERF-2: connection reuse + bounded timeout.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_citation_counts_reuses_one_pooled_http_client() -> None:
    """PERF-2: same fix as `PubMedClient` — one long-lived pooled
    `httpx.AsyncClient` per client instance, not a fresh handshake per
    call, and `aclose` -> transparent re-creation on next use."""
    fixture = _load_json("icite_response.json")
    with respx.mock(assert_all_called=True) as mock:
        mock.get(BASE_URL).mock(return_value=httpx.Response(200, json=fixture))
        client = ICiteClient()
        await client.fetch_citation_counts(["38279812"])
        first_http = client._http
        await client.fetch_citation_counts(["38279813"])
        assert client._http is first_http
        assert first_http is not None and not first_http.is_closed

        await client.aclose()
        assert first_http.is_closed
        await client.fetch_citation_counts(["37000001"])

    assert client._http is not first_http
    assert client._http is not None and not client._http.is_closed


def test_default_timeout_is_bounded_for_user_facing_search() -> None:
    """PERF-2: iCite stays single-attempt (§7.6 graceful degradation), so
    its default timeout is the whole worst-case latency it can add to a
    search — must stay well inside the ~15s overall budget."""
    client = ICiteClient()
    assert client._timeout == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_fetch_citation_counts_degrades_gracefully_on_malformed_json() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(BASE_URL).mock(return_value=httpx.Response(200, text="not json"))
        client = ICiteClient()
        result = await client.fetch_citation_counts(["38279812"])

    assert result.available is False
    assert result.counts == {}
