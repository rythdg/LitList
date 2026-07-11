"""Private helpers shared by Task 3A's four route modules (search, queue,
decisions, saved) — not a public module, not imported outside this
package. Split out purely to avoid duplicating the PMID-batch-to-`Paper`-
row upsert logic (needed by both `search.py`'s initial page and
`queue.py`'s pagination follow-up, §7.9) in two places.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import insert
from sqlmodel import Session as DBSession
from sqlmodel import col, select

from app.clients import get_icite_client, get_pubmed_client
from app.db import get_session
from app.integrations.icite import ICiteClient
from app.integrations.pubmed import ESummaryRecord
from app.middleware.session import get_current_session
from app.models.entities import DecisionState, Paper, QueueDecision, SortOrder
from app.models.ids import utcnow

# Module-level `Depends(...)` singletons — matches Task 3B's own fix for
# ruff's B008 ("don't call `Depends()` in an argument default") — reused
# across all four of Task 3A's route modules rather than re-declared per
# file/per-route.
CurrentSession = Depends(get_current_session)
DbSession = Depends(get_session)
PubMed = Depends(get_pubmed_client)
ICite = Depends(get_icite_client)

# §7.3's default ESearch page size — also this app's own paging unit for
# the transparent follow-up fetch (§7.9).
PAGE_SIZE = 20

# GET /queue proactively fetches the next ESearch page once fewer than
# this many *pending* decisions remain, so the user never sees a "load
# more" action (§7.9's "transparently... when the user's queue runs
# low").
LOW_WATERMARK = 5


def pubmed_sort_for(sort: SortOrder) -> str:
    """Map LitList's own sort enum onto ESearch's `sort` parameter
    (§7.3). "citations" has no native ESearch value (§7.6) — ESearch is
    called with its default relevance ordering, and the caller re-sorts
    the fetched page by `citation_count` itself once iCite data is in."""
    if sort == SortOrder.recency:
        return "pub_date"
    return "relevance"


def get_papers_by_pmid(db: DBSession, pmids: list[str]) -> dict[str, Paper]:
    """One `SELECT ... WHERE pmid IN (...)` for the whole batch instead of
    a per-pmid `db.get(Paper, ...)` loop (TASK PERF-1) — against the remote
    Turso database each `db.get` is a full network round-trip, and the
    per-pmid loops here were the dominant cost of a live search request
    (~20 sequential round-trips per loop at 200-300ms each)."""
    if not pmids:
        return {}
    rows = db.exec(select(Paper).where(col(Paper.pmid).in_(pmids))).all()
    return {paper.pmid: paper for paper in rows}


async def upsert_papers_from_esummary(
    db: DBSession, records: list[ESummaryRecord]
) -> dict[str, Paper]:
    """Insert or refresh `Paper` rows (§9.2's global cache) from a batch
    of ESummary records. Returns a `{pmid: Paper}` map for the caller's
    convenience. Does not touch `display_abstract`/`spoken_abstract`/
    `abstract_sections` — those are EFetch's job (§7.1's two-stage
    strategy), populated later by `queue.py`'s abstract endpoint.

    Reads all existing rows in one batched SELECT (see
    `get_papers_by_pmid`) and flushes once — never per-record round-trips
    (TASK PERF-1)."""
    now = utcnow()
    papers: dict[str, Paper] = {}
    existing = get_papers_by_pmid(db, [record.pmid for record in records])
    for record in records:
        paper = existing.get(record.pmid)
        if paper is None:
            paper = Paper(pmid=record.pmid, title=record.title)
        paper.title = record.title
        paper.last_author = record.last_author
        paper.journal = record.journal
        paper.pub_date = record.pub_date
        paper.doi = record.doi
        paper.esummary_fetched_at = now
        db.add(paper)
        papers[record.pmid] = paper
    db.flush()
    return papers


async def apply_citation_counts(
    db: DBSession, icite_client: ICiteClient, pmids: list[str]
) -> dict[str, int | None]:
    """Fetch citation counts for `pmids` via iCite (§7.6) and persist them
    onto the already-upserted `Paper` rows. Never raises — per §7.6,
    iCite being unreachable degrades gracefully (an empty/`available=False`
    result), it never fails the whole search/queue request."""
    result = await icite_client.fetch_citation_counts(pmids)
    counts: dict[str, int | None] = {}
    # One batched SELECT for the whole page instead of a per-pmid
    # `db.get` loop in each branch (TASK PERF-1). The callers have just
    # flushed these rows via `upsert_papers_from_esummary`, so the ORM
    # identity map hands back the same instances.
    papers = get_papers_by_pmid(db, pmids)
    if not result.available:
        # Leave whatever citation_count each Paper row already had
        # (possibly None, possibly a stale-but-real prior value) —
        # degrade the *sort*, not the data.
        for pmid in pmids:
            paper = papers.get(pmid)
            counts[pmid] = paper.citation_count if paper else None
        return counts

    now = utcnow()
    for pmid in pmids:
        paper = papers.get(pmid)
        count = result.counts.get(pmid)
        if paper is not None and count is not None:
            paper.citation_count = count
            paper.citation_fetched_at = now
            db.add(paper)
        counts[pmid] = paper.citation_count if paper else count
    db.flush()
    return counts


def insert_pending_decisions(
    db: DBSession, session_id: str, ordered_pmids: list[str], start_position: int = 0
) -> None:
    """Insert one `pending` `QueueDecision` row per pmid, positions
    continuing from `start_position`, as a single executemany Core INSERT
    rather than ~20 per-object `db.add` flushes (TASK PERF-1 — the ORM
    add-loop was flushing row-by-row against remote Turso because
    `QueueDecision.id` is server-generated). Callers still own the
    surrounding transaction (`db.commit()`)."""
    if not ordered_pmids:
        return
    db.execute(
        insert(QueueDecision),
        [
            {
                "session_id": session_id,
                "pmid": pmid,
                "position": start_position + offset,
                "decision": DecisionState.pending,
            }
            for offset, pmid in enumerate(ordered_pmids)
        ],
    )


def order_pmids_by_citations(pmids: list[str], counts: dict[str, int | None]) -> list[str]:
    """§7.6's Citations sort: order the already-fetched page by
    `citation_count` descending, missing/unknown counts sorted last. This
    only orders *within* the page ESearch already returned (relevance
    order) — there is no native ESearch value for a true global
    citation-count sort (§7.3's own table calls this out explicitly)."""
    return sorted(pmids, key=lambda pmid: (counts.get(pmid) is None, -(counts.get(pmid) or 0)))
