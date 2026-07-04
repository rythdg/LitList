"""Zotero client wrapper (SPEC.md §8 all, BuildPlan.md Task 1C).

Per §10.5, this is the **only** code allowed to make authenticated Zotero
API calls — route handlers (Task 3B) never call `pyzotero` directly. This
module wraps `pyzotero.Zotero` for:

- listing collections, following pagination (§8.4)
- creating a collection (§8.5)
- batched item push with per-PMID success/failure reporting, matching
  CONTRACTS.md's pinned `ZoteroPushResult`/`ZoteroPushResponse` shape
  exactly (§8.6/§8.7)

**Sync-under-the-hood, async at the boundary.** `pyzotero` (and the
`httpx.Client` it builds internally) is a synchronous, blocking API — it is
not an async client. Every public function here is `async def` and runs
the actual blocking `pyzotero` call via Starlette's `run_in_threadpool`, so
callers (async FastAPI route handlers) never block the event loop on a
Zotero round-trip. This keeps the "async-native" choice in §10.1 true in
practice, not just at the route-decorator level.

**Backoff is already handled by pyzotero itself.** `pyzotero._client.Zotero`
tracks a `Backoff-until` timestamp and honors both the `Backoff` header (via
`_post_check`/`error_handler`, called on every write) and `Retry-After` on
429 responses internally (`_check_backoff` blocks before the next call) —
this is exactly §8.7's requirement, so this module does not reimplement
pacing; it only translates pyzotero's results/exceptions into CONTRACTS.md's
per-item shape. See this task's build-log PIVOT entry for why this was
verified against pyzotero's actual source rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pyzotero import Zotero
from pyzotero import errors as ze
from starlette.concurrency import run_in_threadpool

# §8.6: up to 50 items may be created per Zotero write request.
ITEM_BATCH_SIZE = 50

# Safe, pre-written message reused verbatim from CONTRACTS.md §3's example —
# never the raw pyzotero/Zotero-provided error text (§10.3).
_SERVICE_UNAVAILABLE_MESSAGE = "Zotero is currently unavailable. Please try again shortly."


class ZoteroClientError(Exception):
    """Base class for errors raised by this wrapper that aren't already
    expressed as a per-item `ZoteroPushResult` failure (e.g. errors from
    `list_collections`/`create_collection`, which aren't batchable). Route
    handlers (Task 3B) translate these into CONTRACTS.md's `{"error": ...}`
    envelope, using `error_code` below."""

    def __init__(self, message: str, *, error_code: str = "service_unavailable") -> None:
        super().__init__(message)
        self.error_code = error_code


def _wrap_pyzotero_error(exc: Exception) -> ZoteroClientError:
    """Map a pyzotero exception to a safe, pre-written `ZoteroClientError`
    per §10.3 — never surfaces `str(exc)` (which can include raw Zotero
    response bodies, per `pyzotero.errors._err_msg`) to a caller."""
    if isinstance(exc, ze.UserNotAuthorisedError):
        return ZoteroClientError(
            "Zotero rejected this request as unauthorized.", error_code="zotero_not_connected"
        )
    return ZoteroClientError(_SERVICE_UNAVAILABLE_MESSAGE, error_code="service_unavailable")


@dataclass(frozen=True)
class ZoteroCollection:
    """Mirrors §8.4/§8.5's `key`/`name` pair used to populate Screen D1's
    radio list and to file pushed items (§8.6)."""

    key: str
    name: str


@dataclass(frozen=True)
class ZoteroAuthor:
    first_name: str
    last_name: str


@dataclass(frozen=True)
class ZoteroPaperInput:
    """One saved paper's data as needed to build a Zotero `journalArticle`
    item (§8.6) — sourced from `Paper` (§9.2)/EFetch (§7.5). Every field
    here is optional except `pmid`/`title` since PubMed records aren't
    guaranteed to carry a DOI/journal/date for every record (§7.9)."""

    pmid: str
    title: str
    authors: list[ZoteroAuthor] = field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    pub_date: str | None = None
    doi: str | None = None


ZoteroPushStatus = Literal["success", "failure"]


@dataclass(frozen=True)
class ZoteroPushError:
    code: str
    message: str


@dataclass(frozen=True)
class ZoteroPushResult:
    """Matches CONTRACTS.md §3's `ZoteroPushResult` exactly — one entry per
    PMID, never an all-or-nothing batch result (§8.7)."""

    pmid: str
    status: ZoteroPushStatus
    zotero_item_key: str | None = None
    error: ZoteroPushError | None = None


def _client(zotero_user_id: str, api_key: str) -> Zotero:
    """Construct a `pyzotero.Zotero` bound to one user's personal library
    (§8.9 — group libraries are explicitly out of v1 scope, so `library_type`
    is always `"user"`)."""
    return Zotero(zotero_user_id, "user", api_key)


def _paper_to_item(paper: ZoteroPaperInput, collection_key: str) -> dict[str, Any]:
    """Build the exact item dict shape from §8.6."""
    item: dict[str, Any] = {
        "itemType": "journalArticle",
        "title": paper.title,
        "creators": [
            {"creatorType": "author", "firstName": a.first_name, "lastName": a.last_name}
            for a in paper.authors
        ],
        "abstractNote": paper.abstract or "",
        "publicationTitle": paper.journal or "",
        "date": paper.pub_date or "",
        "DOI": paper.doi or "",
        "libraryCatalog": "PubMed",
        "extra": f"PMID: {paper.pmid}",
        "collections": [collection_key],
    }
    if paper.doi:
        item["url"] = f"https://doi.org/{paper.doi}"
    return item


async def list_collections(zotero_user_id: str, api_key: str) -> list[ZoteroCollection]:
    """List every collection in the user's personal library (§8.4),
    following Zotero's `Link: rel="next"` pagination rather than assuming a
    single page — `pyzotero`'s `everything()` helper does exactly this."""
    zot = _client(zotero_user_id, api_key)

    def _call() -> list[dict[str, Any]]:
        return zot.everything(zot.collections())  # type: ignore[no-any-return]

    try:
        raw = await run_in_threadpool(_call)
    except ze.PyZoteroError as exc:
        raise _wrap_pyzotero_error(exc) from exc
    return [ZoteroCollection(key=c["key"], name=c["data"]["name"]) for c in raw]


async def create_collection(zotero_user_id: str, api_key: str, name: str) -> ZoteroCollection:
    """Create a new collection (§8.5) and return its key/name — the key
    flows straight into the same save action (5.5's inline "+ New
    collection" behavior)."""
    zot = _client(zotero_user_id, api_key)

    def _call() -> dict[str, Any]:
        return zot.create_collections([{"name": name}])  # type: ignore[no-any-return]

    try:
        response = await run_in_threadpool(_call)
    except ze.PyZoteroError as exc:
        raise _wrap_pyzotero_error(exc) from exc

    successful = response.get("successful") or {}
    if not successful:
        # Zotero's write-response shape always reports at least one of
        # successful/unchanged/failed per submitted item; an empty
        # `successful` map for a single-item request means Zotero rejected
        # it without raising — treat as a service failure rather than
        # crashing on a KeyError.
        raise ZoteroClientError(_SERVICE_UNAVAILABLE_MESSAGE, error_code="service_unavailable")
    created = next(iter(successful.values()))
    return ZoteroCollection(key=created["data"]["key"], name=created["data"]["name"])


async def push_items(
    zotero_user_id: str,
    api_key: str,
    collection_key: str,
    papers: list[ZoteroPaperInput],
) -> list[ZoteroPushResult]:
    """Push `papers` into `collection_key` as Zotero `journalArticle` items
    (§8.6), chunked into batches of `ITEM_BATCH_SIZE`. Always returns one
    `ZoteroPushResult` per input paper, in input order — a batch that fails
    entirely (e.g. the whole HTTP call raises) reports every paper in that
    batch as `failure` rather than raising, so a partial multi-batch push
    (§8.7 — batch 1 saves, batch 2 fails) is representable and callers
    (Task 3B) can write `ZoteroExport` rows only for the successes and
    report exactly what still needs retrying.
    """
    if not papers:
        return []

    zot = _client(zotero_user_id, api_key)
    results: list[ZoteroPushResult] = []

    for start in range(0, len(papers), ITEM_BATCH_SIZE):
        batch = papers[start : start + ITEM_BATCH_SIZE]
        items = [_paper_to_item(p, collection_key) for p in batch]

        def _call(items: list[dict[str, Any]] = items) -> dict[str, Any]:
            return zot.create_items(items)  # type: ignore[no-any-return]

        try:
            response = await run_in_threadpool(_call)
        except ze.PyZoteroError:
            # Whole-batch failure (rate-limited past retry, unreachable,
            # unauthorized, etc.) — every paper in this batch still needs
            # saving.
            results.extend(
                ZoteroPushResult(
                    pmid=p.pmid,
                    status="failure",
                    error=ZoteroPushError(
                        code="service_unavailable", message=_SERVICE_UNAVAILABLE_MESSAGE
                    ),
                )
                for p in batch
            )
            continue

        success_map: dict[str, str] = response.get("success", {})
        failed_map: dict[str, Any] = response.get("failed", {})

        for index, paper in enumerate(batch):
            index_str = str(index)
            if index_str in success_map:
                results.append(
                    ZoteroPushResult(
                        pmid=paper.pmid,
                        status="success",
                        zotero_item_key=success_map[index_str],
                    )
                )
            else:
                # Covers both an explicit `failed` entry and the
                # (undocumented-but-possible) case of an index missing from
                # every map — treated identically as a safe failure rather
                # than silently dropping the paper from the response.
                _ = failed_map.get(index_str)
                results.append(
                    ZoteroPushResult(
                        pmid=paper.pmid,
                        status="failure",
                        error=ZoteroPushError(
                            code="service_unavailable", message=_SERVICE_UNAVAILABLE_MESSAGE
                        ),
                    )
                )

    return results
