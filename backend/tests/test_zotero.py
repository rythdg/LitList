"""Task 1C tests, SPEC.md §15.1/§15.7 (automated half) + §8.4/§8.6/§8.7 —
the `pyzotero`-backed client wrapper (`app.integrations.zotero`).

Uses `fixtures/zotero/*.json` (Task 0.3) rather than inventing new mock
data, per this task's brief — in particular
`item_creation_response.json`'s partial-batch-failure shape (index 0
succeeds, index 1 fails) is exercised directly against
`push_items`/CONTRACTS.md's per-PMID `ZoteroPushResult` shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.integrations import zotero

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "zotero"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture
def collections_fixture() -> dict[str, Any]:
    return _load_fixture("collections_response.json")


@pytest.fixture
def item_creation_fixture() -> dict[str, Any]:
    return _load_fixture("item_creation_response.json")


async def test_list_collections_returns_key_and_name_following_pagination(
    collections_fixture: dict[str, Any],
) -> None:
    raw_collections = collections_fixture["collections"]

    with patch.object(zotero.Zotero, "everything", return_value=raw_collections):
        with patch.object(zotero.Zotero, "collections", return_value=None):
            result = await zotero.list_collections("123456", "fake-api-key")

    assert result == [
        zotero.ZoteroCollection(key="ABCD1234", name="Journal Club"),
        zotero.ZoteroCollection(key="WXYZ5678", name="To Read"),
    ]


async def test_create_collection_returns_new_key() -> None:
    write_response = {
        "successful": {
            "0": {
                "key": "NEWKEY99",
                "data": {"key": "NEWKEY99", "name": "Journal Club"},
            }
        },
        "success": {"0": "NEWKEY99"},
        "unchanged": {},
        "failed": {},
    }
    with patch.object(zotero.Zotero, "create_collections", return_value=write_response):
        result = await zotero.create_collection("123456", "fake-api-key", "Journal Club")

    assert result == zotero.ZoteroCollection(key="NEWKEY99", name="Journal Club")


async def test_push_items_reports_partial_batch_failure_per_pmid(
    item_creation_fixture: dict[str, Any],
) -> None:
    """Exercises the exact fixture: index 0 succeeds (XJ2K9F3P), index 1
    fails (Zotero-side 503) — per §8.7, this must surface as one success and
    one failure result, not an all-or-nothing outcome."""
    papers = [
        zotero.ZoteroPaperInput(
            pmid="38279812",
            title="Effects of early intervention on outcomes in a mixed-methods cohort study",
            authors=[
                zotero.ZoteroAuthor(first_name="Sofia", last_name="Alvarez"),
                zotero.ZoteroAuthor(first_name="Wei", last_name="Chen"),
            ],
            abstract="Background. Results are shown in Fig. 2. ...",
            journal="Journal of Applied Clinical Research",
            pub_date="2024 Feb",
            doi="10.1234/jacr.2024.001812",
        ),
        zotero.ZoteroPaperInput(pmid="38279813", title="A second paper that fails to save"),
    ]

    with patch.object(zotero.Zotero, "create_items", return_value=item_creation_fixture):
        results = await zotero.push_items("123456", "fake-api-key", "ABCD1234", papers)

    assert results == [
        zotero.ZoteroPushResult(
            pmid="38279812", status="success", zotero_item_key="XJ2K9F3P"
        ),
        zotero.ZoteroPushResult(
            pmid="38279813",
            status="failure",
            error=zotero.ZoteroPushError(
                code="service_unavailable",
                message="Zotero is currently unavailable. Please try again shortly.",
            ),
        ),
    ]


async def test_push_items_builds_the_pinned_item_shape() -> None:
    """§8.6's item dict shape, checked against the exact fields the wrapper
    sends to `create_items` (not just the response translation above)."""
    captured: dict[str, Any] = {}

    def _fake_create_items(self: zotero.Zotero, payload: list[dict[str, Any]]) -> dict[str, Any]:
        captured["payload"] = payload
        return {"success": {"0": "NEWITEM1"}, "failed": {}}

    paper = zotero.ZoteroPaperInput(
        pmid="38279812",
        title="A study",
        authors=[zotero.ZoteroAuthor(first_name="Sofia", last_name="Alvarez")],
        abstract="An abstract.",
        journal="Journal X",
        pub_date="2024",
        doi="10.1234/x",
    )

    with patch.object(zotero.Zotero, "create_items", _fake_create_items):
        results = await zotero.push_items("123456", "fake-api-key", "ABCD1234", [paper])

    assert results == [
        zotero.ZoteroPushResult(pmid="38279812", status="success", zotero_item_key="NEWITEM1")
    ]
    item = captured["payload"][0]
    assert item["itemType"] == "journalArticle"
    assert item["title"] == "A study"
    assert item["creators"] == [
        {"creatorType": "author", "firstName": "Sofia", "lastName": "Alvarez"}
    ]
    assert item["abstractNote"] == "An abstract."
    assert item["publicationTitle"] == "Journal X"
    assert item["date"] == "2024"
    assert item["DOI"] == "10.1234/x"
    assert item["url"] == "https://doi.org/10.1234/x"
    assert item["libraryCatalog"] == "PubMed"
    assert item["extra"] == "PMID: 38279812"
    assert item["collections"] == ["ABCD1234"]


async def test_push_items_chunks_into_batches_of_50() -> None:
    call_sizes: list[int] = []

    def _fake_create_items(self: zotero.Zotero, payload: list[dict[str, Any]]) -> dict[str, Any]:
        call_sizes.append(len(payload))
        return {"success": {str(i): f"KEY{i}" for i in range(len(payload))}, "failed": {}}

    papers = [zotero.ZoteroPaperInput(pmid=str(i), title=f"paper {i}") for i in range(120)]

    with patch.object(zotero.Zotero, "create_items", _fake_create_items):
        results = await zotero.push_items("123456", "fake-api-key", "ABCD1234", papers)

    assert call_sizes == [50, 50, 20]
    assert len(results) == 120
    assert all(r.status == "success" for r in results)


async def test_push_items_marks_whole_batch_as_failure_when_call_raises() -> None:
    from pyzotero import errors as ze

    def _raise(self: zotero.Zotero, payload: list[dict[str, Any]]) -> dict[str, Any]:
        raise ze.TooManyRequestsError("rate limited")

    papers = [
        zotero.ZoteroPaperInput(pmid="1", title="p1"),
        zotero.ZoteroPaperInput(pmid="2", title="p2"),
    ]

    with patch.object(zotero.Zotero, "create_items", _raise):
        results = await zotero.push_items("123456", "fake-api-key", "ABCD1234", papers)

    assert all(r.status == "failure" for r in results)
    assert all(r.error is not None and r.error.code == "service_unavailable" for r in results)


async def test_push_items_returns_empty_list_for_no_papers() -> None:
    result = await zotero.push_items("123456", "fake-api-key", "ABCD1234", [])
    assert result == []
