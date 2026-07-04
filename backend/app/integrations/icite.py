"""NIH iCite client (BuildPlan.md Task 1B, SPEC.md §7.6).

Fills the citation-count gap E-utilities leaves open (PubMed itself has
no citation-count field) so the "Citations" sort option (§3.2.C) has data
to sort on. No API key/auth required.

Unlike `pubmed.py`, this client does not raise on an unreachable/failing
iCite — §7.6 explicitly calls for graceful degradation ("the Citations
sort option should degrade gracefully... if iCite is unreachable, rather
than blocking the whole search"), so `fetch_citation_counts` always
returns an `ICiteResult`; callers (Tier 3's search/queue endpoints) check
`.available` and fall back to Relevance sort themselves rather than
handling an exception.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://icite.od.nih.gov/api/pubs"

_DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class ICiteResult:
    """Result of one iCite batch lookup.

    `counts` only contains entries iCite actually returned data for — a
    requested PMID missing from `counts` means iCite has no citation data
    for it yet (§7.6's coverage-lag note), which is distinct from
    `available=False` (iCite itself was unreachable/erroring for the
    *whole* call). UI handling of "no data yet" vs. "0 citations" is a
    Frontend-Architecture-level detail per §7.6, deliberately left to the
    caller.
    """

    available: bool
    counts: dict[str, int] = field(default_factory=dict)


class ICiteClient:
    """Wrapper client for the NIH iCite API (§7.6)."""

    def __init__(self, *, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    async def fetch_citation_counts(self, pmids: list[str]) -> ICiteResult:
        if not pmids:
            return ICiteResult(available=True, counts={})

        params = {"pmids": ",".join(pmids), "fl": "pmid,citation_count,relative_citation_ratio"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "iCite unreachable — degrading Citations sort to unavailable: %s", exc
            )
            return ICiteResult(available=False, counts={})

        try:
            body: Any = response.json()
        except ValueError as exc:
            logger.warning("iCite returned malformed JSON — degrading: %s", exc)
            return ICiteResult(available=False, counts={})

        counts: dict[str, int] = {}
        for entry in body.get("data", []):
            if not isinstance(entry, dict):
                continue
            pmid = entry.get("pmid")
            citation_count = entry.get("citation_count")
            if pmid is None or citation_count is None:
                continue
            try:
                counts[str(pmid)] = int(citation_count)
            except (TypeError, ValueError):
                logger.warning("iCite: skipping record with unparseable citation_count: %r", entry)
                continue

        return ICiteResult(available=True, counts=counts)
