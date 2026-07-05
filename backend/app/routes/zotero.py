"""Zotero endpoints (SPEC.md §10.4's zotero rows, §8 all, §9.6;
BuildPlan.md Task 3B).

This module owns exactly the FastAPI route layer on top of two already-
built pieces (Task 1C, merged): `app.auth.oauth` (the OAuth 1.0a
handshake logic) and `app.integrations.zotero` (the `pyzotero`-backed
wrapper for collections/item-push, §10.5's chokepoint for authenticated
Zotero calls). No route here talks to Zotero directly — every call goes
through one of those two modules.

Session/connection lookup reuses Task 1A's `get_current_session` /
`get_current_zotero_connection` FastAPI dependencies verbatim — this
module never re-reads the session cookie or re-implements that lookup.

**Token handling (§9.6):** `ZoteroConnection.oauth_token`/
`oauth_token_secret` are stored Fernet-encrypted (`app.models.crypto`).
This module decrypts `oauth_token` only at the point of making an
authenticated Zotero call (it doubles as pyzotero's `api_key` argument,
per SPEC.md §8.2 step 4 / §8.4) and never logs or returns either field.

**Error shape:** every non-2xx response here uses CONTRACTS.md §2's
`{"error": {"code", "message"}}` shape directly (via `_error_response`
below) rather than FastAPI's default `HTTPException` body (which wraps
`detail` in a different shape) — Task 3D's future cross-cutting
exception handler is for genuinely *unhandled* exceptions; every error
this module can anticipate (session mismatch, missing connection,
Zotero unavailable, not-found PMID) is handled explicitly here so it
never has to fall through to that catch-all.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.auth import oauth
from app.db import get_session
from app.integrations import zotero as zotero_client
from app.middleware.session import (
    get_current_session,
    get_current_zotero_connection,
    set_session_cookie,
)
from app.models import (
    Paper,
    ZoteroConnection,
    ZoteroExport,
    decrypt_token,
    encrypt_token,
    rotate_session,
)
from app.models import Session as SessionRow
from app.models.ids import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zotero", tags=["zotero"])

_SERVICE_UNAVAILABLE_MESSAGE = "Zotero is currently unavailable. Please try again shortly."
_NOT_CONNECTED_MESSAGE = "Connect to Zotero before continuing."

# Module-level `Depends(...)` singletons (ruff B008's own suggested fix) —
# avoids calling `Depends(...)` inline in every route's argument defaults
# below, which ruff otherwise flags on each occurrence.
_CurrentSession = Depends(get_current_session)
_CurrentZoteroConnection = Depends(get_current_zotero_connection)
_DbSession = Depends(get_session)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """CONTRACTS.md §2's pinned `{"error": {code, message}}` shape,
    project-wide — see this module's docstring for why routes build this
    directly rather than raising `HTTPException`."""
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def _callback_redirect(
    status: str, *, code: str | None = None, message: str | None = None
) -> RedirectResponse:
    """Builds the browser-facing redirect target for `GET /zotero/auth/
    callback` (§8.2 step 6, CONTRACTS.md's OAuth-callback-redirect
    section). This route is hit by a real browser navigation (Zotero
    bounces the user here directly), never by `fetch` — so every outcome,
    success *and* failure, must be a redirect to the frontend's fixed
    `/oauth/zotero/callback` route (Task 2A) rather than a raw JSON body,
    which the browser would otherwise render as an unstyled page with no
    way back into the app. Reuses the pinned `ApiError` `code`/`message`
    fields as query params on failure rather than inventing a new shape.
    """
    params: dict[str, str] = {"status": status}
    if code is not None:
        params["code"] = code
    if message is not None:
        params["message"] = message
    url = f"{oauth.post_auth_redirect_url()}?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


def _client_error_response(exc: zotero_client.ZoteroClientError) -> JSONResponse:
    """Maps `app.integrations.zotero`'s `ZoteroClientError.error_code`
    (already a safe, pre-written `str(exc)` per that module's own
    docstring) to the matching HTTP status from CONTRACTS.md §2."""
    status_code = 401 if exc.error_code == "zotero_not_connected" else 503
    return _error_response(status_code, exc.error_code, str(exc))


# ---------------------------------------------------------------------
# GET /zotero/auth/start, GET /zotero/auth/callback (§8.2)
# ---------------------------------------------------------------------


@router.get("/auth/start")
def start_auth(session: SessionRow = _CurrentSession) -> Response:
    """Begins the OAuth 1.0a handshake (§8.2 step 2) and redirects the
    user's browser to Zotero's authorize page. `start_handshake` binds the
    issued request token to this session (§10.2's addendum) so the
    callback below can verify it later."""
    try:
        authorize_url = oauth.start_handshake(session.session_id)
    except oauth.ZoteroOAuthProviderError:
        logger.exception("Zotero OAuth start_handshake failed")
        # Same rationale as `auth_callback`'s error paths below: this
        # route is hit by a real browser navigation (the "Connect to
        # Zotero" button does a full navigation here, not a `fetch`), so
        # a raw JSON error body would render as an unstyled dead end
        # instead of bouncing the user back into the app.
        return _callback_redirect(
            "error", code="service_unavailable", message=_SERVICE_UNAVAILABLE_MESSAGE
        )
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/auth/callback")
def auth_callback(
    oauth_token: str = Query(...),
    oauth_verifier: str = Query(...),
    session: SessionRow = _CurrentSession,
    db: DBSession = _DbSession,
) -> Response:
    """OAuth callback (§8.2 step 4). Must arrive on the *same* session
    cookie that started the handshake — `complete_handshake` enforces the
    request-token-to-session binding (§10.2's addendum) and raises
    `ZoteroSessionMismatchError` otherwise.

    This route is hit by a real browser navigation (Zotero redirects the
    user's browser here directly), never by `fetch` — so every outcome,
    success or failure, is a `302` redirect to the frontend's fixed
    `/oauth/zotero/callback` route (Task 2A), never a raw JSON error body
    (see `_callback_redirect`). A session mismatch redirects with
    `?status=error&code=zotero_session_mismatch`; an unreachable Zotero
    redirects with `?status=error&code=service_unavailable`. This was a
    real, unpinned contract gap as of Tier 2/3 (2A's frontend assumed a
    redirect shape; 3B's original implementation returned raw JSON on
    error and redirected to an unrelated URL on success) — fixed by Task
    4B; see CONTRACTS.md's OAuth-callback-redirect section and this
    task's build-log PIVOT entry.

    On success: Fernet-encrypts the returned credentials (§9.6) before
    persisting a `ZoteroConnection` row (replacing any prior one for this
    session — at most one per §9.2), rotates the session id (§9.1's
    privilege-escalation fix, §8.2 step 5), pushes the rotated cookie onto
    the redirect response, and bounces the browser to the fixed in-app
    post-auth path with `?status=success` (§8.2 step 6).

    **Single atomic transaction (post-review fix).** The `ZoteroConnection`
    insert and the session rotation are one commit, not two: the
    connection is only `flush()`-ed (visible within this transaction, not
    yet durable) before calling `rotate_session`, which migrates every
    session-scoped row — including this just-flushed connection — onto
    the new `session_id` and issues the *one* commit for the whole
    sequence. If anything raises before that commit (a crash, an
    unexpected `rotate_session` failure), `app.db.get_session`'s
    `with Session(...) as session:` block rolls the entire uncommitted
    transaction back on exit — so a `ZoteroConnection` can never be left
    durably attached to the pre-rotation `session_id`, which would
    otherwise reopen exactly the session-fixation window rotation exists
    to close (§9.1). An earlier version of this handler committed the
    connection insert on its own before calling `rotate_session`
    separately, which had this narrow window; caught by adversarial
    review, see this task's PIVOT log entry.
    """
    try:
        credentials = oauth.complete_handshake(session.session_id, oauth_token, oauth_verifier)
    except oauth.ZoteroSessionMismatchError as exc:
        return _callback_redirect("error", code="zotero_session_mismatch", message=str(exc))
    except oauth.ZoteroOAuthProviderError:
        logger.exception("Zotero OAuth complete_handshake failed")
        return _callback_redirect(
            "error", code="service_unavailable", message=_SERVICE_UNAVAILABLE_MESSAGE
        )

    existing = db.exec(
        select(ZoteroConnection).where(ZoteroConnection.session_id == session.session_id)
    ).first()
    if existing is not None:
        db.delete(existing)
        db.flush()

    connection = ZoteroConnection(
        session_id=session.session_id,
        zotero_user_id=credentials.zotero_user_id,
        oauth_token=encrypt_token(credentials.oauth_token),
        oauth_token_secret=encrypt_token(credentials.oauth_token_secret),
    )
    db.add(connection)
    # Flush, don't commit: makes the insert visible to `rotate_session`'s
    # own query (below) within this same transaction, without yet making
    # it durable — see the atomicity note in this function's docstring.
    db.flush()

    current_session_row = db.get(SessionRow, session.session_id)
    assert current_session_row is not None  # this request's own session row
    # `rotate_session` performs the *only* commit in this handler — it
    # migrates the connection just flushed above (and any other session-
    # scoped rows) onto the new session_id and commits once, atomically.
    new_session = rotate_session(db, current_session_row)

    response = _callback_redirect("success")
    set_session_cookie(response, new_session.session_id)
    return response


# ---------------------------------------------------------------------
# GET/POST /zotero/collections (§8.4/§8.5)
# ---------------------------------------------------------------------


class ZoteroCollectionOut(BaseModel):
    key: str
    name: str


class ZoteroCollectionsResponse(BaseModel):
    collections: list[ZoteroCollectionOut]
    connected: bool


@router.get("/collections", response_model=None)
async def list_collections(
    zotero_connection: ZoteroConnection | None = _CurrentZoteroConnection,
) -> Response:
    """Lists the connected user's collections (§8.4). No `ZoteroConnection`
    yet -> `zotero_not_connected` (401-equivalent, CONTRACTS.md §2), which
    the frontend uses to trigger the "Connect to Zotero" step (§5.5)."""
    if zotero_connection is None:
        return _error_response(401, "zotero_not_connected", _NOT_CONNECTED_MESSAGE)

    try:
        api_key = decrypt_token(zotero_connection.oauth_token)
    except ValueError:
        logger.exception("Failed to decrypt stored Zotero token")
        return _error_response(503, "service_unavailable", _SERVICE_UNAVAILABLE_MESSAGE)

    try:
        collections = await zotero_client.list_collections(
            zotero_connection.zotero_user_id, api_key
        )
    except zotero_client.ZoteroClientError as exc:
        return _client_error_response(exc)

    return JSONResponse(
        content=ZoteroCollectionsResponse(
            collections=[ZoteroCollectionOut(key=c.key, name=c.name) for c in collections],
            connected=True,
        ).model_dump()
    )


class CreateZoteroCollectionRequest(BaseModel):
    name: str


class CreateZoteroCollectionResponse(BaseModel):
    collection: ZoteroCollectionOut


@router.post("/collections", response_model=None)
async def create_collection(
    body: CreateZoteroCollectionRequest,
    zotero_connection: ZoteroConnection | None = _CurrentZoteroConnection,
) -> Response:
    """Creates a new collection (§8.5) — the "+ New collection" inline
    field on Screen D1 (§5.5)."""
    if zotero_connection is None:
        return _error_response(401, "zotero_not_connected", _NOT_CONNECTED_MESSAGE)

    try:
        api_key = decrypt_token(zotero_connection.oauth_token)
    except ValueError:
        logger.exception("Failed to decrypt stored Zotero token")
        return _error_response(503, "service_unavailable", _SERVICE_UNAVAILABLE_MESSAGE)

    try:
        collection = await zotero_client.create_collection(
            zotero_connection.zotero_user_id, api_key, body.name
        )
    except zotero_client.ZoteroClientError as exc:
        return _client_error_response(exc)

    return JSONResponse(
        content=CreateZoteroCollectionResponse(
            collection=ZoteroCollectionOut(key=collection.key, name=collection.name)
        ).model_dump()
    )


# ---------------------------------------------------------------------
# POST /zotero/push (§8.6/§8.7, CONTRACTS.md §3)
# ---------------------------------------------------------------------


class ZoteroPushRequest(BaseModel):
    collection_key: str
    pmids: list[str]


@router.post("/push", response_model=None)
async def push_items(
    body: ZoteroPushRequest,
    session: SessionRow = _CurrentSession,
    zotero_connection: ZoteroConnection | None = _CurrentZoteroConnection,
    db: DBSession = _DbSession,
) -> Response:
    """Pushes saved papers into a Zotero collection (§8.6), chunked into
    batches of 50 by `app.integrations.zotero.push_items`. Always returns
    CONTRACTS.md §3's per-PMID `ZoteroPushResponse` — never an
    all-or-nothing result (§8.7) — and writes a `ZoteroExport` row per
    successfully-pushed PMID so a partial retry only needs to cover what's
    actually still missing.
    """
    if zotero_connection is None:
        return _error_response(401, "zotero_not_connected", _NOT_CONNECTED_MESSAGE)

    try:
        api_key = decrypt_token(zotero_connection.oauth_token)
    except ValueError:
        logger.exception("Failed to decrypt stored Zotero token")
        return _error_response(503, "service_unavailable", _SERVICE_UNAVAILABLE_MESSAGE)

    papers_by_pmid: dict[str, Paper] = {}
    if body.pmids:
        rows = db.exec(select(Paper).where(Paper.pmid.in_(body.pmids))).all()  # type: ignore[attr-defined]
        papers_by_pmid = {p.pmid: p for p in rows}

    pushable: list[zotero_client.ZoteroPaperInput] = []
    not_found_pmids: set[str] = set()
    for pmid in body.pmids:
        paper = papers_by_pmid.get(pmid)
        if paper is None:
            not_found_pmids.add(pmid)
            continue
        pushable.append(
            zotero_client.ZoteroPaperInput(
                pmid=paper.pmid,
                title=paper.title,
                authors=[
                    zotero_client.ZoteroAuthor(
                        first_name=a.get("first_name", ""), last_name=a.get("last_name", "")
                    )
                    for a in paper.authors
                ],
                abstract=paper.display_abstract,
                journal=paper.journal,
                pub_date=paper.pub_date,
                doi=paper.doi,
            )
        )

    push_results = await zotero_client.push_items(
        zotero_connection.zotero_user_id, api_key, body.collection_key, pushable
    )

    results_by_pmid = {r.pmid: r for r in push_results}
    ordered_results: list[dict[str, Any]] = []
    for pmid in body.pmids:
        if pmid in not_found_pmids:
            ordered_results.append(
                {
                    "pmid": pmid,
                    "status": "failure",
                    "error": {
                        "code": "not_found",
                        "message": "This paper is no longer available to export.",
                    },
                }
            )
            continue
        result = results_by_pmid[pmid]
        if result.status == "success":
            db.add(
                ZoteroExport(
                    session_id=session.session_id,
                    pmid=result.pmid,
                    zotero_item_key=result.zotero_item_key or "",
                    zotero_collection_key=body.collection_key,
                    pushed_at=utcnow(),
                )
            )
            ordered_results.append(
                {
                    "pmid": result.pmid,
                    "status": "success",
                    "zotero_item_key": result.zotero_item_key,
                }
            )
        else:
            error = result.error
            ordered_results.append(
                {
                    "pmid": result.pmid,
                    "status": "failure",
                    "error": {
                        "code": error.code if error else "service_unavailable",
                        "message": error.message if error else _SERVICE_UNAVAILABLE_MESSAGE,
                    },
                }
            )

    db.commit()

    return JSONResponse(
        content={"collection_key": body.collection_key, "results": ordered_results}
    )


# ---------------------------------------------------------------------
# DELETE /zotero/connection (§9.6's "Disconnect Zotero" action —
# newly pinned in SPEC.md §10.4 / CONTRACTS.md §4 by this task)
# ---------------------------------------------------------------------


@router.delete("/connection", status_code=204, response_model=None)
def disconnect(
    session: SessionRow = _CurrentSession,
    db: DBSession = _DbSession,
) -> Response:
    """Deletes the session's `ZoteroConnection` row immediately (§9.6).
    Idempotent: calling this with no connection present is not an error —
    still `204 No Content` (CONTRACTS.md §4)."""
    existing = db.exec(
        select(ZoteroConnection).where(ZoteroConnection.session_id == session.session_id)
    ).first()
    if existing is not None:
        db.delete(existing)
        db.commit()
    return Response(status_code=204)
