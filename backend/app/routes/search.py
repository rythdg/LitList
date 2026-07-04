"""`POST /search` and `GET /search/settings` (BuildPlan.md Task 3A,
SPEC.md §10.4's first two rows, §7.1-7.4/7.6/7.9, §3.5).

`POST /search` is the one endpoint that always needs a live PubMed call
(there's nothing to cache yet for a brand-new query) — §13.6's
`service_unavailable` path applies here whenever `PubMedClient` raises
`PubMedUnavailableError`. iCite is only called when `sort == "citations"`
(§7.6); if iCite itself is down, the sort silently degrades to the
ESearch-returned (relevance) order rather than failing the request,
matching §7.6's explicit "degrade gracefully... rather than blocking the
whole search."
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, field_validator
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.errors import ApiError, api_error_response, service_unavailable, validation_error
from app.integrations.icite import ICiteClient
from app.integrations.pubmed import PubMedClient, PubMedUnavailableError
from app.models.entities import (
    DecisionState,
    QueueDecision,
    SearchSession,
    SortOrder,
    SwipeBehavior,
)
from app.models.entities import Session as SessionRow
from app.models.ids import utcnow
from app.routes._shared import (
    PAGE_SIZE,
    CurrentSession,
    DbSession,
    ICite,
    PubMed,
    apply_citation_counts,
    order_pmids_by_citations,
    pubmed_sort_for,
    upsert_papers_from_esummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_READ_ALOUD_FIELDS = {"last_author", "journal", "pub_date"}


class SearchRequestBody(BaseModel):
    query: str
    sort: SortOrder = SortOrder.relevance
    read_aloud_fields: list[str] = []
    default_swipe_behavior: SwipeBehavior = SwipeBehavior.interested
    speed: float = 1.0

    @field_validator("query")
    @classmethod
    def _query_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @field_validator("read_aloud_fields")
    @classmethod
    def _fields_known(cls, value: list[str]) -> list[str]:
        unknown = set(value) - _VALID_READ_ALOUD_FIELDS
        if unknown:
            raise ValueError(f"unknown read_aloud_fields: {sorted(unknown)}")
        return value

    @field_validator("speed")
    @classmethod
    def _speed_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("speed must be positive")
        return value


class QueueItem(BaseModel):
    pmid: str
    position: int
    decision: DecisionState
    title: str
    last_author: str | None
    journal: str | None
    pub_date: str | None
    doi: str | None
    citation_count: int | None
    # §13.4's "Retracted Publication" badge (frontend: StackScreen.tsx) —
    # sourced from `Paper.retracted`, only populated once EFetch has run
    # for this PMID (§7.1's two-stage strategy — ESummary alone, which is
    # all a brand-new queue item has, carries no PublicationType data).
    # `False` here means "not retracted" *or* "not yet known" — it
    # becomes accurate the moment the abstract endpoint has fetched this
    # PMID at least once, same lazy-population story as `citation_count`.
    # Pinned as CONTRACTS.md's note for Task 4A.
    retracted: bool


class QueueResponse(BaseModel):
    items: list[QueueItem]
    total_count: int
    has_more: bool


class SearchSettingsResponse(BaseModel):
    query: str | None
    sort: SortOrder
    read_aloud_fields: list[str]
    default_swipe_behavior: SwipeBehavior
    speed: float


async def _parse_search_body(request: Request) -> SearchRequestBody:
    try:
        raw = await request.json()
    except Exception as exc:  # noqa: BLE001 — malformed JSON body
        raise validation_error("Request body must be valid JSON.") from exc
    try:
        return SearchRequestBody.model_validate(raw)
    except ValidationError as exc:
        logger.info("POST /search: validation failed: %s", exc)
        raise validation_error("Search request body is invalid.") from None


@router.post("/search", response_model=None)
async def create_search(
    request: Request,
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
    pubmed_client: PubMedClient = PubMed,
    icite_client: ICiteClient = ICite,
) -> QueueResponse | JSONResponse:
    try:
        body = await _parse_search_body(request)

        try:
            esearch_result = await pubmed_client.esearch(
                body.query,
                retmax=PAGE_SIZE,
                retstart=0,
                sort=pubmed_sort_for(body.sort),  # type: ignore[arg-type]
            )
        except PubMedUnavailableError as exc:
            logger.warning("POST /search: PubMed unreachable: %s", exc)
            raise service_unavailable(
                "PubMed is currently unavailable. Please try again shortly."
            ) from exc

        # §3.5: a new search replaces the current one — upsert SearchSession
        # in place, and wipe any prior QueueDecision rows for this session
        # (the Saved List is scoped to the current search, per §14.1's note
        # that cross-search persistence is explicitly out of v1 scope).
        search_session = db.exec(
            select(SearchSession).where(SearchSession.session_id == session.session_id)
        ).first()
        if search_session is None:
            search_session = SearchSession(session_id=session.session_id, query=body.query)
        search_session.query = body.query
        search_session.sort = body.sort
        search_session.read_aloud_fields = body.read_aloud_fields
        search_session.default_swipe_behavior = body.default_swipe_behavior
        search_session.speed = body.speed
        search_session.updated_at = utcnow()
        search_session.total_result_count = esearch_result.count
        search_session.next_retstart = PAGE_SIZE
        db.add(search_session)

        stale_decisions = db.exec(
            select(QueueDecision).where(QueueDecision.session_id == session.session_id)
        ).all()
        for stale in stale_decisions:
            db.delete(stale)

        items: list[QueueItem] = []
        if esearch_result.pmids:
            # §7.9: zero results skip ESummary/EFetch entirely — this
            # branch only runs when ESearch actually returned PMIDs.
            records = await pubmed_client.esummary(esearch_result.pmids)
            papers = await upsert_papers_from_esummary(db, records)
            ordered_pmids = [pmid for pmid in esearch_result.pmids if pmid in papers]

            counts: dict[str, int | None] = {}
            if body.sort == SortOrder.citations:
                counts = await apply_citation_counts(db, icite_client, ordered_pmids)
                ordered_pmids = order_pmids_by_citations(ordered_pmids, counts)

            for position, pmid in enumerate(ordered_pmids):
                decision = QueueDecision(
                    session_id=session.session_id,
                    pmid=pmid,
                    position=position,
                    decision=DecisionState.pending,
                )
                db.add(decision)
                paper = papers[pmid]
                items.append(
                    QueueItem(
                        pmid=pmid,
                        position=position,
                        decision=DecisionState.pending,
                        title=paper.title,
                        last_author=paper.last_author,
                        journal=paper.journal,
                        pub_date=paper.pub_date,
                        doi=paper.doi,
                        citation_count=counts.get(pmid, paper.citation_count),
                        retracted=paper.retracted,
                    )
                )

        db.commit()

        return QueueResponse(
            items=items,
            total_count=esearch_result.count,
            has_more=len(items) < esearch_result.count,
        )
    except ApiError as error:
        return api_error_response(error)


@router.get("/search/settings")
def get_search_settings(
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
) -> SearchSettingsResponse:
    """Powers the pre-fill behavior (§3.5) even before any search has been
    run this visit — returns sensible defaults (no error) when no
    `SearchSession` exists yet for this session."""
    search_session = db.exec(
        select(SearchSession).where(SearchSession.session_id == session.session_id)
    ).first()
    if search_session is None:
        return SearchSettingsResponse(
            query=None,
            sort=SortOrder.relevance,
            read_aloud_fields=[],
            default_swipe_behavior=SwipeBehavior.interested,
            speed=1.0,
        )
    return SearchSettingsResponse(
        query=search_session.query,
        sort=search_session.sort,
        read_aloud_fields=search_session.read_aloud_fields,
        default_swipe_behavior=search_session.default_swipe_behavior,
        speed=search_session.speed,
    )

