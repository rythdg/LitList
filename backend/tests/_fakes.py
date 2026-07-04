"""Shared fake PubMed/iCite clients for Task 3A's route tests.

Per this task's brief: "1B's PubMed/iCite clients should still be mocked/
injected since real network calls aren't allowed in tests" — these fakes
implement the same public methods as `PubMedClient`/`ICiteClient` and are
swapped in via `app.dependency_overrides`, never `respx` (that's for 1B's
own client-level tests against real HTTP shapes).
"""

from __future__ import annotations

from app.integrations.icite import ICiteResult
from app.integrations.pubmed import (
    Author,
    EFetchArticle,
    ESearchResult,
    ESummaryRecord,
    PubMedError,
    PubMedUnavailableError,
)
from app.text.tokenize import AbstractSection


class FakePubMedClient:
    def __init__(
        self,
        *,
        esearch_result: ESearchResult | None = None,
        esummary_records: list[ESummaryRecord] | None = None,
        efetch_articles: list[EFetchArticle] | None = None,
        unavailable: bool = False,
        efetch_exception: PubMedError | None = None,
    ) -> None:
        self.esearch_result = esearch_result
        self.esummary_records = esummary_records or []
        self.efetch_articles = efetch_articles or []
        self.unavailable = unavailable
        # Lets a test simulate a specific `PubMedError` subclass from
        # `efetch` alone (e.g. `PubMedParseError`) without also making
        # `esearch`/`esummary` unavailable — distinct from `unavailable`,
        # which simulates PubMed being entirely unreachable across all
        # three calls.
        self.efetch_exception = efetch_exception
        self.esearch_calls: list[dict] = []
        self.esummary_calls: list[list[str]] = []
        self.efetch_calls: list[list[str]] = []

    async def esearch(self, query, *, retmax=20, retstart=0, sort="relevance") -> ESearchResult:
        self.esearch_calls.append(
            {"query": query, "retmax": retmax, "retstart": retstart, "sort": sort}
        )
        if self.unavailable:
            raise PubMedUnavailableError("PubMed is currently unavailable.")
        assert self.esearch_result is not None
        return self.esearch_result

    async def esummary(self, pmids: list[str]) -> list[ESummaryRecord]:
        self.esummary_calls.append(pmids)
        if self.unavailable:
            raise PubMedUnavailableError("PubMed is currently unavailable.")
        return [r for r in self.esummary_records if r.pmid in pmids]

    async def efetch(self, pmids: list[str]) -> list[EFetchArticle]:
        self.efetch_calls.append(pmids)
        if self.unavailable:
            raise PubMedUnavailableError("PubMed is currently unavailable.")
        if self.efetch_exception is not None:
            raise self.efetch_exception
        return [a for a in self.efetch_articles if a.pmid in pmids]


class FakeICiteClient:
    def __init__(self, *, counts: dict[str, int] | None = None, available: bool = True) -> None:
        self.counts = counts or {}
        self.available = available

    async def fetch_citation_counts(self, pmids: list[str]) -> ICiteResult:
        return ICiteResult(available=self.available, counts=self.counts)


def make_esearch_result(pmids: list[str], count: int | None = None) -> ESearchResult:
    return ESearchResult(
        count=count if count is not None else len(pmids), pmids=pmids, retmax=20, retstart=0
    )


def make_esummary_record(pmid: str, **overrides) -> ESummaryRecord:
    defaults = dict(
        pmid=pmid,
        title=f"Title for {pmid}",
        last_author="Doe J",
        journal="Journal of Examples",
        pub_date="2024",
        sort_pub_date="2024/01/01",
        doi=f"10.1234/{pmid}",
    )
    defaults.update(overrides)
    return ESummaryRecord(**defaults)


def make_efetch_article(pmid: str, **overrides) -> EFetchArticle:
    defaults = dict(
        pmid=pmid,
        title=f"Title for {pmid}",
        journal="Journal of Examples",
        abstract_sections=[
            AbstractSection(label="BACKGROUND", text="Prior work is limited."),
            AbstractSection(label="METHODS", text="We ran a trial."),
        ],
        authors=[Author(last_name="Doe", first_name="Jane")],
        doi=f"10.1234/{pmid}",
        language="eng",
        publication_types=[],
        retracted=False,
    )
    defaults.update(overrides)
    return EFetchArticle(**defaults)
