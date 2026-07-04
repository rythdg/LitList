"""`GET /queue` and `GET /papers/{pmid}/abstract` (BuildPlan.md Task 3A,
SPEC.md §10.4, §7.1/§7.5/§7.9 pagination, §9.2/§13.6 caching).

`GET /queue` reads the current `SearchSession`'s `QueueDecision` rows —
no PubMed call at all in the common case. It only calls PubMed when the
queue is running low on `pending` decisions *and* more results exist
upstream (§7.9's transparent pagination follow-up). If that follow-up
call fails (`PubMedUnavailableError`) **and there is already at least one
decision to serve**, the failure is logged and swallowed — per §13.6,
already-cached data keeps serving regardless of PubMed being reachable
*right now*; a paginated list that already has content to show should
not become a hard error just because *more* content couldn't be fetched
this instant. `service_unavailable` (503) is reserved for the case where
there is nothing at all to serve without that live call succeeding
(e.g. immediately after `POST /search` completed a page for a query that
has since started running low, or if `/queue` is somehow called before
any decisions exist yet).

`GET /papers/{pmid}/abstract` is the one place §13.6's contract matters
most concretely: a cache hit (`Paper.efetch_fetched_at` set) never calls
PubMed at all, so it is unaffected by a PubMed outage. Only a genuine
cache miss calls EFetch, and only then can it return `service_unavailable`.

**Distinguishing "genuinely no such PMID" from "our parser is broken"
(adversarial review, TASK 3A REVIEW finding #2).** `PubMedClient.efetch`
raises `PubMedParseError` (rather than just returning `[]`) when a
non-empty EFetch response entirely failed to parse — see that
exception's docstring in `app/integrations/pubmed.py`. This route maps
that to `internal_error` (500), logged at ERROR, deliberately never the
same `not_found` (404) a truly nonexistent PMID gets — collapsing the
two would silently hide a systemic backend bug (e.g. an NCBI XML schema
change breaking every EFetch parse) behind ordinary-looking 404 traffic
that no 404-tolerant monitoring would ever flag.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.errors import (
    ApiError,
    api_error_response,
    internal_error,
    not_found,
    service_unavailable,
)
from app.integrations.icite import ICiteClient
from app.integrations.pubmed import PubMedClient, PubMedParseError, PubMedUnavailableError
from app.models.entities import DecisionState, Paper, QueueDecision, SearchSession, SortOrder
from app.models.entities import Session as SessionRow
from app.models.ids import utcnow
from app.routes._shared import (
    LOW_WATERMARK,
    CurrentSession,
    DbSession,
    ICite,
    PubMed,
    apply_citation_counts,
    order_pmids_by_citations,
    pubmed_sort_for,
    upsert_papers_from_esummary,
)
from app.routes.search import QueueItem, QueueResponse
from app.text.tokenize import AbstractSection, SegmentedAbstractResponse, build_segmented_abstract

logger = logging.getLogger(__name__)

router = APIRouter()

# §13.3's default narration locale — matches Task 1D's own default, kept
# as a named constant here rather than hardcoding "en" inline in case a
# later task threads the user's actual voice locale through.
_DEFAULT_NARRATION_LOCALE = "en"


def _queue_item(decision: QueueDecision, paper: Paper) -> QueueItem:
    return QueueItem(
        pmid=paper.pmid,
        position=decision.position,
        decision=decision.decision,
        title=paper.title,
        last_author=paper.last_author,
        journal=paper.journal,
        pub_date=paper.pub_date,
        doi=paper.doi,
        citation_count=paper.citation_count,
        retracted=paper.retracted,
    )


async def _fetch_next_page(
    db: DBSession,
    search_session: SearchSession,
    session_id: str,
    pubmed_client: PubMedClient,
    icite_client: ICiteClient,
    start_position: int,
) -> None:
    """§7.9's transparent pagination follow-up — issues the next ESearch
    page (`retstart = search_session.next_retstart`) and appends new
    `QueueDecision` rows continuing from `start_position`. Raises
    `PubMedUnavailableError` on failure; callers decide whether that's
    fatal for the overall request (see module docstring)."""
    esearch_result = await pubmed_client.esearch(
        search_session.query,
        retmax=20,
        retstart=search_session.next_retstart,
        sort=pubmed_sort_for(search_session.sort),  # type: ignore[arg-type]
    )
    search_session.total_result_count = esearch_result.count
    if not esearch_result.pmids:
        db.add(search_session)
        db.commit()
        return

    records = await pubmed_client.esummary(esearch_result.pmids)
    papers = await upsert_papers_from_esummary(db, records)
    ordered_pmids = [pmid for pmid in esearch_result.pmids if pmid in papers]

    if search_session.sort == SortOrder.citations:
        counts = await apply_citation_counts(db, icite_client, ordered_pmids)
        ordered_pmids = order_pmids_by_citations(ordered_pmids, counts)

    for offset, pmid in enumerate(ordered_pmids):
        db.add(
            QueueDecision(
                session_id=session_id,
                pmid=pmid,
                position=start_position + offset,
                decision=DecisionState.pending,
            )
        )
    search_session.next_retstart += 20
    db.add(search_session)
    db.commit()


@router.get("/queue", response_model=None)
async def get_queue(
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
    pubmed_client: PubMedClient = PubMed,
    icite_client: ICiteClient = ICite,
) -> QueueResponse | JSONResponse:
    try:
        search_session = db.exec(
            select(SearchSession).where(SearchSession.session_id == session.session_id)
        ).first()
        if search_session is None:
            # Nothing searched yet this visit — an empty queue, not an error.
            return QueueResponse(items=[], total_count=0, has_more=False)

        decisions = db.exec(
            select(QueueDecision)
            .where(QueueDecision.session_id == session.session_id)
            .order_by(QueueDecision.position)  # type: ignore[arg-type]
        ).all()

        pending_count = sum(1 for d in decisions if d.decision == DecisionState.pending)
        total_result_count = search_session.total_result_count or 0
        more_upstream = len(decisions) < total_result_count

        if more_upstream and pending_count < LOW_WATERMARK:
            next_position = (max((d.position for d in decisions), default=-1)) + 1
            try:
                await _fetch_next_page(
                    db, search_session, session.session_id, pubmed_client, icite_client,
                    next_position,
                )
                decisions = db.exec(
                    select(QueueDecision)
                    .where(QueueDecision.session_id == session.session_id)
                    .order_by(QueueDecision.position)  # type: ignore[arg-type]
                ).all()
            except PubMedUnavailableError as exc:
                if not decisions:
                    # Nothing at all to serve without this call succeeding.
                    logger.warning("GET /queue: PubMed unreachable, no cached queue to serve")
                    raise service_unavailable(
                        "PubMed is currently unavailable. Please try again shortly."
                    ) from exc
                # Already-cached rows keep serving (§9.2/§13.6) — the
                # follow-up simply didn't happen this time.
                logger.warning(
                    "GET /queue: pagination follow-up failed, serving existing "
                    "%d cached decisions instead: %s",
                    len(decisions),
                    exc,
                )

        items: list[QueueItem] = []
        for decision in decisions:
            paper = db.get(Paper, decision.pmid)
            if paper is None:  # pragma: no cover - defensive, FK-guaranteed in practice
                continue
            items.append(_queue_item(decision, paper))

        total_result_count = search_session.total_result_count or len(items)
        return QueueResponse(
            items=items,
            total_count=total_result_count,
            has_more=len(items) < total_result_count,
        )
    except ApiError as error:
        return api_error_response(error)


@router.get("/papers/{pmid}/abstract", response_model=None)
async def get_paper_abstract(
    pmid: str,
    _session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
    pubmed_client: PubMedClient = PubMed,
) -> SegmentedAbstractResponse | JSONResponse:
    try:
        paper = db.get(Paper, pmid)

        if paper is not None and paper.abstract_sections is not None:
            # Cache hit (§9.2/§13.6) — never touches PubMed.
            sections = [
                AbstractSection(label=entry.get("label"), text=entry.get("text") or "")
                for entry in paper.abstract_sections
            ]
            _display, _spoken, response = build_segmented_abstract(
                pmid,
                sections,
                language=paper.language,
                narration_locale=_DEFAULT_NARRATION_LOCALE,
            )
            return response

        try:
            articles = await pubmed_client.efetch([pmid])
        except PubMedUnavailableError as exc:
            logger.warning("GET /papers/%s/abstract: PubMed unreachable: %s", pmid, exc)
            raise service_unavailable(
                "PubMed is currently unavailable. Please try again shortly."
            ) from exc
        except PubMedParseError as exc:
            # Logged at ERROR (not WARNING) deliberately — this is a real,
            # positively-identified backend bug (see module docstring),
            # not a routine "PubMed has nothing for this PMID" case.
            logger.error(
                "GET /papers/%s/abstract: EFetch response failed to parse entirely "
                "(likely an upstream schema change, not a missing PMID): %s",
                pmid,
                exc,
            )
            raise internal_error(
                "Something went wrong while fetching this paper. Please try again shortly."
            ) from exc

        if not articles:
            raise not_found(f"No paper found for PMID {pmid}.")
        article = articles[0]

        display_abstract, spoken_abstract, response = build_segmented_abstract(
            pmid,
            article.abstract_sections,
            language=article.language,
            narration_locale=_DEFAULT_NARRATION_LOCALE,
        )

        if paper is None:
            paper = Paper(pmid=pmid, title=article.title)
        paper.title = article.title or paper.title
        paper.journal = article.journal or paper.journal
        paper.doi = article.doi or paper.doi
        paper.authors = [
            {"first_name": a.first_name or "", "last_name": a.last_name or ""}
            for a in article.authors
        ]
        paper.language = article.language
        paper.retracted = article.retracted
        paper.display_abstract = display_abstract
        paper.spoken_abstract = spoken_abstract
        paper.abstract_sections = [
            {"label": s.label, "text": s.text} for s in article.abstract_sections
        ]
        paper.efetch_fetched_at = utcnow()
        db.add(paper)
        db.commit()

        return response
    except ApiError as error:
        return api_error_response(error)
