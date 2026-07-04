"""`GET /saved` and `DELETE /saved/{pmid}` (BuildPlan.md Task 3A,
SPEC.md §10.4, §5.4, §4.7, §9.2).

The Saved List *is* `QueueDecision` rows where `decision == interested`
for the current session (§9.2's own note) — no separate table, no
PubMed/iCite call, so §13.6 doesn't apply here either.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.errors import ApiError, api_error_response, not_found
from app.models.entities import DecidedVia, DecisionState, Paper, QueueDecision
from app.models.entities import Session as SessionRow
from app.models.ids import utcnow
from app.routes._shared import CurrentSession, DbSession

router = APIRouter()


class SavedItem(BaseModel):
    pmid: str
    title: str
    last_author: str | None
    journal: str | None
    pub_date: str | None
    doi: str | None
    citation_count: int | None
    position: int
    # See `app.routes.search.QueueItem.retracted`'s docstring — same
    # §13.4 badge, same `Paper.retracted` source, same "False may mean
    # not-yet-known" caveat.
    retracted: bool


class SavedListResponse(BaseModel):
    items: list[SavedItem]


@router.get("/saved")
def list_saved(
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
) -> SavedListResponse:
    rows = db.exec(
        select(Paper, QueueDecision)
        .join(QueueDecision, QueueDecision.pmid == Paper.pmid)  # type: ignore[arg-type]
        .where(
            QueueDecision.session_id == session.session_id,
            QueueDecision.decision == DecisionState.interested,
        )
        .order_by(QueueDecision.position)  # type: ignore[arg-type]
    ).all()

    items = [
        SavedItem(
            pmid=paper.pmid,
            title=paper.title,
            last_author=paper.last_author,
            journal=paper.journal,
            pub_date=paper.pub_date,
            doi=paper.doi,
            citation_count=paper.citation_count,
            position=decision.position,
            retracted=paper.retracted,
        )
        for paper, decision in rows
    ]
    return SavedListResponse(items=items)


@router.delete("/saved/{pmid}", response_model=None)
def remove_saved(
    pmid: str,
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
) -> SavedItem | JSONResponse:
    """§4.7: "undo/remove" sets the decision back to `not_interested`
    rather than deleting the row outright — preserves the audit trail
    (§9.2) and deliberately does not resurrect the card in the live
    queue."""
    try:
        decision_row = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session.session_id,
                QueueDecision.pmid == pmid,
                QueueDecision.decision == DecisionState.interested,
            )
        ).first()
        if decision_row is None:
            raise not_found(f"No saved entry for PMID {pmid} in this session.")

        decision_row.decision = DecisionState.not_interested
        decision_row.decided_via = DecidedVia.manual_remove
        decision_row.decided_at = utcnow()
        db.add(decision_row)
        db.commit()

        paper = db.get(Paper, pmid)
        title = paper.title if paper else ""
        return SavedItem(
            pmid=pmid,
            title=title,
            last_author=paper.last_author if paper else None,
            journal=paper.journal if paper else None,
            pub_date=paper.pub_date if paper else None,
            doi=paper.doi if paper else None,
            citation_count=paper.citation_count if paper else None,
            position=decision_row.position,
            retracted=paper.retracted if paper else False,
        )
    except ApiError as error:
        return api_error_response(error)
