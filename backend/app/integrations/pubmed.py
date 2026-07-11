"""PubMed E-utilities client (BuildPlan.md Task 1B, SPEC.md §7 all).

Implements the three-call strategy from §7.1: ESearch (§7.3, query -> PMID
list), ESummary (§7.4, batched lightweight metadata), and EFetch (§7.5,
structured-XML abstract retrieval). All calls happen server-side, through
this single wrapper client — no ad hoc `httpx` calls belong in route
handlers (§10.5).

Also captures, from EFetch (§13.4/§7.5):
- `Language` — needed by Task 1D's §13.3 language-mismatch check.
- `PublicationType` (specifically a "Retracted Publication" flag) — needed
  by Task 2B's retracted badge.

Neither of these is persisted here — this module only parses the wire
payload into plain dataclasses. Persisting into the `Paper` cache (§9.2),
including adding any new columns needed for these fields, is later Tier
work (Task 3A's core-loop endpoints); this module's job stops at "return
clean, typed data from PubMed."

Outbound pacing (§7.7) and 429/`Retry-After` backoff are implemented here,
against an injectable clock so tests never sleep real wall-clock time
(§15.8). This is deliberately a *separate* mechanism from the inbound
per-session/per-IP rate limiter (§10.5, Task 3D) — conflating the two was
explicitly called out as a mistake to avoid (§15.8).
"""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from app.config import settings
from app.text.tokenize import AbstractSection

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# §7.7: max 3 req/s without an API key, 10 req/s with one.
_RATE_WITHOUT_KEY = 3.0
_RATE_WITH_KEY = 10.0

# Retry policy for a 429 response (§7.9's "queue/retry with backoff" —
# SPEC.md doesn't pin an exact attempt count, so this is a deliberate,
# small, documented choice rather than an unbounded retry loop).
#
# PERF-2: retries lowered 3 -> 1 (2 attempts total) and the per-attempt
# timeout lowered 10s -> 6s, so a genuinely-failing NCBI call surfaces
# §13.6's "PubMed is currently unavailable" degradation in well under
# ~15s instead of burning ~40s in front of a waiting user. Worst-case
# arithmetic with these numbers (no API key, so 3 req/s pacing):
#   2 attempts x 6s timeout + 1 inter-attempt pacing wait (~0.33s)
#   = ~12.4s; a 429 path is cheaper still (fast responses + one
#   Retry-After backoff, capped below at 3s).
_MAX_RETRY_ATTEMPTS = 1
_DEFAULT_TIMEOUT_SECONDS = 6.0
_DEFAULT_RETRY_AFTER_SECONDS = 1.0
# PERF-2: honor `Retry-After` but cap it — NCBI could legally send a
# large value (e.g. 300) and a user-facing search must not sleep that
# long before surfacing the §13.6 degradation state. The cap keeps the
# documented <15s worst-case budget true regardless of the header.
_MAX_RETRY_AFTER_SECONDS = 3.0

SortOption = Literal["relevance", "pub_date"]


class PubMedError(Exception):
    """Base class for PubMed-client failures."""


class PubMedUnavailableError(PubMedError):
    """PubMed is unreachable or persistently rate-limiting us.

    Route handlers (Tier 3) are expected to catch this and map it onto
    CONTRACTS.md's `service_unavailable` error shape (§10.3) — this
    module never fabricates that response shape itself since it has no
    knowledge of the HTTP layer above it.
    """


class PubMedParseError(PubMedError):
    """EFetch returned a well-formed HTTP response, but this module could
    not extract *any* usable article from it, despite the response
    containing (or being expected to contain) actual `<PubmedArticle>`
    data — i.e. a likely bug in `_parse_one_article`/`_parse_efetch_xml`
    (e.g. an NCBI XML schema change), not a genuinely nonexistent PMID.

    Deliberately distinct from an *individual* malformed record within an
    otherwise-successful batch (§7.9 — one bad record is still logged and
    skipped, the batch's other results are still returned normally) and
    from `PubMedUnavailableError` (a reachability/rate-limit problem, not
    a parsing one). Callers (Tier 3's route handlers) are expected to map
    this onto CONTRACTS.md's `internal_error` (500) rather than treating
    an empty result as an ordinary "PMID not found" (404) — collapsing
    the two would silently hide a systemic backend bug (e.g. every EFetch
    call failing to parse after an upstream schema change) behind
    unremarkable-looking 404 traffic that no 404-tolerant monitoring
    would ever flag. Raised, and logged at ERROR (not WARNING) by the
    caller, precisely because this case deserves to be noticed.
    """


# --------------------------------------------------------------------------
# Clock abstraction — lets tests drive pacing/backoff without real sleeps.
# --------------------------------------------------------------------------


@dataclass
class Clock:
    """Wall-clock source used by `RateLimiter` and retry backoff.

    Defaults to real time/`asyncio.sleep`; tests substitute a fake clock
    whose `sleep` advances a virtual counter instantly instead of actually
    waiting (§15.8: "unit-tested against a fake/injectable clock, never
    real sleep() calls").
    """

    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


class RateLimiter:
    """Enforces a minimum interval between successive outbound calls.

    A simple leaky-bucket-of-one: each `acquire()` call waits, if needed,
    until `min_interval` seconds have elapsed since the previously
    *scheduled* call, so back-to-back calls never exceed the configured
    rate even under concurrent callers (guarded by an `asyncio.Lock`).
    """

    def __init__(self, requests_per_second: float, *, clock: Clock | None = None) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._clock = clock or Clock()
        self._lock = asyncio.Lock()
        self._next_allowed: float | None = None

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock.now()
            if self._next_allowed is None:
                self._next_allowed = now
            wait = self._next_allowed - now
            if wait > 0:
                await self._clock.sleep(wait)
                now += wait
            self._next_allowed = max(now, self._next_allowed) + self._min_interval


# --------------------------------------------------------------------------
# Parsed result shapes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ESearchResult:
    """§7.3 — ESearch's PMID list plus pagination bookkeeping (§7.9)."""

    count: int
    pmids: list[str]
    retmax: int
    retstart: int


@dataclass(frozen=True)
class ESummaryRecord:
    """§7.4 — one ESummary DocSum, trimmed to the fields the product uses."""

    pmid: str
    title: str
    last_author: str | None
    journal: str | None
    pub_date: str | None
    sort_pub_date: str | None
    doi: str | None


@dataclass(frozen=True)
class Author:
    last_name: str | None
    first_name: str | None


@dataclass(frozen=True)
class EFetchArticle:
    """§7.5's structured EFetch record, plus §13.3/§13.4's extra fields."""

    pmid: str
    title: str
    journal: str | None
    abstract_sections: list[AbstractSection] = field(default_factory=list)
    authors: list[Author] = field(default_factory=list)
    doi: str | None = None
    # §13.3: PubMed's `Language` field (ISO 639-2/B code, e.g. "eng",
    # "fre"), used by Task 1D's narration language-mismatch check.
    language: str | None = None
    # §13.4: raw PublicationType strings (e.g. "Journal Article",
    # "Retracted Publication").
    publication_types: list[str] = field(default_factory=list)
    # §13.4: convenience flag derived from `publication_types` — true if
    # any entry indicates a retraction. Task 2B's badge reads this.
    retracted: bool = False


def _common_params() -> dict[str, str]:
    """§7.7's required identification params, included on every call."""
    params: dict[str, str] = {
        "tool": settings.ncbi_tool or "litlist",
    }
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


class PubMedClient:
    """Wrapper client for NCBI E-utilities (§7.2).

    One instance's `RateLimiter` is shared across `esearch`/`esummary`/
    `efetch` since all three hit the same `eutils.ncbi.nlm.nih.gov` host
    and share the same §7.7 rate ceiling.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retry_attempts: int = _MAX_RETRY_ATTEMPTS,
    ) -> None:
        self._clock = clock or Clock()
        requests_per_second = _RATE_WITH_KEY if settings.ncbi_api_key else _RATE_WITHOUT_KEY
        self._rate_limiter = RateLimiter(requests_per_second, clock=self._clock)
        self._timeout = timeout
        self._max_retry_attempts = max_retry_attempts
        # PERF-2: one long-lived, lazily-created AsyncClient per client
        # instance (and `app/clients.py`'s `lru_cache` provider makes that
        # one per *process*), so keep-alive connections to
        # eutils.ncbi.nlm.nih.gov are reused instead of paying a fresh
        # TCP+TLS handshake on every single call. Lazy (created on first
        # use, inside a running event loop) rather than eager so plain
        # `PubMedClient()` construction stays synchronous and loop-free.
        self._http: httpx.AsyncClient | None = None

    def _http_client(self) -> httpx.AsyncClient:
        """Return the shared AsyncClient, (re)creating it if absent/closed.

        The `is_closed` re-creation path matters for the `lru_cache`d
        process singleton: after a lifespan shutdown closes it (see
        `app/main.py`), a later use — e.g. a second `TestClient` context
        in the test suite — gets a fresh client instead of a dead one.
        """
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self._http

    async def aclose(self) -> None:
        """Close the pooled AsyncClient (FastAPI lifespan shutdown hook)."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()

    async def _get(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        """Issue one paced, backed-off GET against `endpoint`.

        Real NCBI behavior (verified against E-utilities docs + observed
        behavior, not just SPEC.md §7.9's paraphrase of the error body):
        a rate-limited request comes back as HTTP 429, generally with a
        `Retry-After` header. §7.9 also mentions the JSON body
        `{"error": "API rate limit exceeded"}` — we treat that as a
        secondary signal (checked even on a non-429 status) in case NCBI
        ever returns it without setting 429, but 429 is the primary,
        trustworthy signal.
        """
        all_params = {**_common_params(), **params}
        last_exc: Exception | None = None
        for attempt in range(self._max_retry_attempts + 1):
            await self._rate_limiter.acquire()
            try:
                response = await self._http_client().get(
                    BASE_URL + endpoint, params=all_params
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("PubMed request to %s failed: %s", endpoint, exc)
                if attempt >= self._max_retry_attempts:
                    raise PubMedUnavailableError(
                        "PubMed is currently unavailable."
                    ) from exc
                continue

            if response.status_code == 429 or _looks_rate_limited(response):
                retry_after = _parse_retry_after(response)
                logger.warning(
                    "PubMed rate-limited us on %s (attempt %d/%d); backing off %.2fs",
                    endpoint,
                    attempt + 1,
                    self._max_retry_attempts,
                    retry_after,
                )
                if attempt >= self._max_retry_attempts:
                    raise PubMedUnavailableError(
                        "PubMed rate limit exceeded; retries exhausted."
                    )
                await self._clock.sleep(retry_after)
                continue

            if response.status_code >= 500:
                logger.warning(
                    "PubMed returned %d on %s (attempt %d/%d)",
                    response.status_code,
                    endpoint,
                    attempt + 1,
                    self._max_retry_attempts,
                )
                if attempt >= self._max_retry_attempts:
                    raise PubMedUnavailableError("PubMed is currently unavailable.")
                await self._clock.sleep(_DEFAULT_RETRY_AFTER_SECONDS)
                continue

            if response.status_code >= 400:
                # Deliberately NOT `response.raise_for_status()` — httpx's
                # `HTTPStatusError.__str__` embeds the full request URL,
                # and `_common_params()` puts `email`/`api_key` directly in
                # the query string on every call. Since CONTRACTS.md
                # documents an eventual catch-all handler (Task 3D) that
                # will very likely log unhandled exceptions verbatim, an
                # uncaught `HTTPStatusError` here would leak
                # NCBI_EMAIL/NCBI_API_KEY into shared logs on any
                # non-429/5xx 4xx response (e.g. 400 malformed query, 403
                # invalid key). Raise a sanitized, status-code-only
                # message instead — never echo the request URL/params.
                logger.warning(
                    "PubMed returned unexpected status %d on %s (attempt %d/%d)",
                    response.status_code,
                    endpoint,
                    attempt + 1,
                    self._max_retry_attempts,
                )
                raise PubMedUnavailableError(
                    f"PubMed request failed with status {response.status_code}."
                )

            return response

        # Unreachable in practice (loop always returns or raises above),
        # but keeps mypy happy about the return type.
        raise PubMedUnavailableError("PubMed is currently unavailable.") from last_exc

    async def esearch(
        self,
        query: str,
        *,
        retmax: int = 20,
        retstart: int = 0,
        sort: SortOption = "relevance",
    ) -> ESearchResult:
        """§7.3 — turn a free-text query into an ordered PMID list.

        Zero results (§7.9) simply produce an `ESearchResult` with an
        empty `pmids` list — callers must not issue ESummary/EFetch calls
        against it.
        """
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(retmax),
            "retstart": str(retstart),
            "sort": sort,
            "retmode": "json",
        }
        response = await self._get("esearch.fcgi", params)
        body = response.json()
        result = body.get("esearchresult", {})
        return ESearchResult(
            count=int(result.get("count", 0)),
            pmids=list(result.get("idlist", [])),
            retmax=int(result.get("retmax", 0)),
            retstart=int(result.get("retstart", 0)),
        )

    async def esummary(self, pmids: list[str]) -> list[ESummaryRecord]:
        """§7.4 — one batched call covering every PMID passed in.

        Per §7.9, a malformed/missing individual DocSum is skipped rather
        than failing the whole batch.
        """
        if not pmids:
            return []
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
        }
        response = await self._get("esummary.fcgi", params)
        body = response.json()
        result = body.get("result", {})
        uids: list[str] = result.get("uids", [])
        records: list[ESummaryRecord] = []
        for uid in uids:
            doc = result.get(uid)
            if not isinstance(doc, dict):
                logger.warning("ESummary: skipping malformed/missing record for PMID %s", uid)
                continue
            try:
                records.append(_parse_esummary_doc(doc))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("ESummary: skipping unparseable record for PMID %s: %s", uid, exc)
                continue
        return records

    async def efetch(self, pmids: list[str]) -> list[EFetchArticle]:
        """§7.5 — fetch structured abstract XML for one or a small batch.

        Per §7.9, a PMID present in `pmids` but missing/malformed in the
        response is skipped, not treated as a fatal error for the batch.

        Raises `PubMedParseError` (distinct from returning `[]`) if the
        response contained article data that entirely failed to parse —
        see that exception's docstring for why this must not be confused
        with a genuinely empty/not-found result.
        """
        if not pmids:
            return []
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml",
        }
        response = await self._get("efetch.fcgi", params)
        return _parse_efetch_xml(response.text)


def _looks_rate_limited(response: httpx.Response) -> bool:
    """Secondary detection for §7.9's documented rate-limit error body.

    Best-effort only — never raises on a body that isn't JSON/isn't a dict
    (EFetch responses are normally XML; a rate-limit response for EFetch
    may or may not be JSON, in which case HTTP 429, checked before this
    function is called, remains the primary signal).
    """
    try:
        body: Any = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("error") == "API rate limit exceeded"


def _parse_retry_after(response: httpx.Response) -> float:
    header = response.headers.get("Retry-After")
    if header is None:
        return _DEFAULT_RETRY_AFTER_SECONDS
    try:
        value = float(header)
    except ValueError:
        return _DEFAULT_RETRY_AFTER_SECONDS
    if value <= 0:
        return _DEFAULT_RETRY_AFTER_SECONDS
    # PERF-2: cap so a large upstream Retry-After can't blow the <15s
    # worst-case latency budget for a user-facing search request.
    return min(value, _MAX_RETRY_AFTER_SECONDS)


def _parse_esummary_doc(doc: dict[str, Any]) -> ESummaryRecord:
    doi: str | None = None
    for entry in doc.get("articleids", []):
        if entry.get("idtype") == "doi":
            doi = entry.get("value")
            break
    return ESummaryRecord(
        pmid=str(doc["uid"]),
        title=doc.get("title", ""),
        last_author=doc.get("lastauthor") or None,
        journal=doc.get("fulljournalname") or doc.get("source") or None,
        pub_date=doc.get("pubdate") or None,
        sort_pub_date=doc.get("sortpubdate") or None,
        doi=doi,
    )


_RETRACTED_MARKERS = ("retracted", "retraction")


def _parse_efetch_xml(xml_text: str) -> list[EFetchArticle]:
    """Parse EFetch's XML body into `EFetchArticle`s.

    Distinguishes two very different "we ended up with nothing" outcomes
    (see `PubMedParseError`'s docstring):
    - The response genuinely contains zero `<PubmedArticle>` elements
      (PubMed's own way of saying "no such PMID(s)") -> returns `[]`
      normally; this is a legitimate not-found case for the caller to
      surface as such.
    - The response contains one or more `<PubmedArticle>` elements but
      *every single one* threw while parsing (or the whole document
      failed to parse as XML at all) -> raises `PubMedParseError`,
      because that pattern means our parser is broken against real data,
      not that PubMed has no data for us.

    A genuinely mixed batch (some elements parse, some don't) still just
    skips the bad ones and returns the good ones per §7.9 — only a
    *complete* parse failure against non-empty input is treated as
    systemic.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("EFetch: could not parse response XML at all: %s", exc)
        raise PubMedParseError("EFetch response was not valid XML.") from exc

    article_elements = root.findall("PubmedArticle")
    articles: list[EFetchArticle] = []
    failed_count = 0
    for article_el in article_elements:
        try:
            parsed = _parse_one_article(article_el)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: one
            # malformed record (§7.9) must not take down the whole batch;
            # whether this is systemic is decided after the loop below.
            pmid_el = article_el.find(".//PMID")
            pmid_text = pmid_el.text if pmid_el is not None else "<unknown>"
            logger.warning("EFetch: skipping malformed record for PMID %s: %s", pmid_text, exc)
            failed_count += 1
            continue
        if parsed is not None:
            articles.append(parsed)
        else:
            failed_count += 1

    if article_elements and not articles:
        # Every element present failed to parse — a likely schema-drift
        # bug, not "PubMed has nothing for these PMIDs" (that case has
        # zero `article_elements` in the first place, handled above by
        # simply returning `[]`).
        logger.error(
            "EFetch: all %d article element(s) in a non-empty response failed to parse "
            "(%d failures) — treating as a systemic parsing bug, not a not-found result.",
            len(article_elements),
            failed_count,
        )
        raise PubMedParseError(
            f"EFetch returned {len(article_elements)} article(s) but none could be parsed."
        )

    return articles


def _parse_one_article(article_el: ET.Element) -> EFetchArticle | None:
    citation_el = article_el.find("MedlineCitation")
    if citation_el is None:
        return None
    pmid_el = citation_el.find("PMID")
    if pmid_el is None or not pmid_el.text:
        return None
    pmid = pmid_el.text

    article_body = citation_el.find("Article")
    title = ""
    journal = None
    language = None
    doi = None
    abstract_sections: list[AbstractSection] = []
    authors: list[Author] = []
    publication_types: list[str] = []

    if article_body is not None:
        title_el = article_body.find("ArticleTitle")
        title = (title_el.text or "") if title_el is not None else ""

        journal_el = article_body.find("Journal/Title")
        journal = journal_el.text if journal_el is not None else None

        language_el = article_body.find("Language")
        language = language_el.text if language_el is not None else None

        for abstract_text_el in article_body.findall("Abstract/AbstractText"):
            label = abstract_text_el.get("Label")
            text = abstract_text_el.text or ""
            abstract_sections.append(AbstractSection(label=label, text=text))

        for author_el in article_body.findall("AuthorList/Author"):
            last_name_el = author_el.find("LastName")
            fore_name_el = author_el.find("ForeName")
            collective_name_el = author_el.find("CollectiveName")
            if last_name_el is not None or fore_name_el is not None:
                authors.append(
                    Author(
                        last_name=last_name_el.text if last_name_el is not None else None,
                        first_name=fore_name_el.text if fore_name_el is not None else None,
                    )
                )
            elif collective_name_el is not None:
                authors.append(Author(last_name=collective_name_el.text, first_name=None))

        for pub_type_el in article_body.findall("PublicationTypeList/PublicationType"):
            if pub_type_el.text:
                publication_types.append(pub_type_el.text)

    # `PubmedData` is a sibling of `MedlineCitation` under `PubmedArticle`
    # (`article_el`), not a child of `citation_el` — walk from `article_el`.
    for article_id_el in article_el.findall("PubmedData/ArticleIdList/ArticleId"):
        if article_id_el.get("IdType") == "doi":
            doi = article_id_el.text
            break

    retracted = any(
        marker in pub_type.lower()
        for pub_type in publication_types
        for marker in _RETRACTED_MARKERS
    )

    return EFetchArticle(
        pmid=pmid,
        title=title,
        journal=journal,
        abstract_sections=abstract_sections,
        authors=authors,
        doi=doi,
        language=language,
        publication_types=publication_types,
        retracted=retracted,
    )
