"""`PATCH /decisions/{pmid}` (BuildPlan.md Task 3A, SPEC.md §10.4,
§4.1/§4.6/§4.7).

Purely a local DB write — no PubMed/iCite/Zotero call, so §13.6's
external-downtime handling doesn't apply here at all.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.errors import ApiError, api_error_response, not_found, validation_error
from app.models.entities import DecidedVia, DecisionState, QueueDecision
from app.models.entities import Session as SessionRow
from app.models.ids import utcnow
from app.routes._shared import CurrentSession, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()


class DecisionUpdateBody(BaseModel):
    decision: DecisionState
    decided_via: DecidedVia


class DecisionResponse(BaseModel):
    pmid: str
    decision: DecisionState
    decided_via: DecidedVia | None
    decided_at: str | None


async def _parse_body(request: Request) -> DecisionUpdateBody:
    try:
        raw = await request.json()
    except Exception as exc:  # noqa: BLE001 — malformed JSON body
        raise validation_error("Request body must be valid JSON.") from exc
    try:
        return DecisionUpdateBody.model_validate(raw)
    except ValidationError as exc:
        logger.info("PATCH /decisions: validation failed: %s", exc)
        raise validation_error("Decision update body is invalid.") from None


@router.patch("/decisions/{pmid}", response_model=None)
async def update_decision(
    pmid: str,
    request: Request,
    session: SessionRow = CurrentSession,
    db: DBSession = DbSession,
) -> DecisionResponse | JSONResponse:
    try:
        body = await _parse_body(request)

        decision_row = db.exec(
            select(QueueDecision).where(
                QueueDecision.session_id == session.session_id,
                QueueDecision.pmid == pmid,
            )
        ).first()
        if decision_row is None:
            raise not_found(f"No queue entry for PMID {pmid} in this session.")

        decision_row.decision = body.decision
        decision_row.decided_via = body.decided_via
        decision_row.decided_at = utcnow()
        db.add(decision_row)
        db.commit()
        db.refresh(decision_row)

        return DecisionResponse(
            pmid=decision_row.pmid,
            decision=decision_row.decision,
            decided_via=decision_row.decided_via,
            decided_at=decision_row.decided_at.isoformat() if decision_row.decided_at else None,
        )
    except ApiError as error:
        return api_error_response(error)
