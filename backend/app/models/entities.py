"""SQLModel table definitions for BuildPlan.md Task 1A, implementing
SPEC.md §9.2's entities verbatim: `Session`, `ZoteroConnection`,
`SearchSession`, `Paper`, `QueueDecision`, `ZoteroExport`.

One model per SPEC.md §9.2 table; field-level comments below cross-reference
the spec row they implement rather than re-deriving the reasoning here.

Naming note: this module deliberately does NOT import `sqlmodel.Session`
(the DB-session/transaction object used throughout `app/db.py` and this
package) into the same namespace as our `Session` *entity* class below —
callers needing both alias one of them (e.g. `from sqlmodel import Session
as DBSession`), which is what `app/models/identity.py` and
`app/middleware/session.py` do.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.ids import generate_session_id, utcnow


class Session(SQLModel, table=True):
    """One row per anonymous browser/device (§9.2). Created silently by the
    session-identity middleware (`app/middleware/session.py`) on first load
    — no route ever constructs this directly under normal operation."""

    __tablename__ = "session"

    session_id: str = Field(default_factory=generate_session_id, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class ZoteroConnection(SQLModel, table=True):
    """At most one per `Session` (§9.2) — created only once the user
    completes the OAuth handshake (§8.2). `oauth_token`/`oauth_token_secret`
    are stored **already Fernet-encrypted** (§9.6) — this table never holds
    plaintext credentials. Use `app.models.crypto.encrypt_token` /
    `decrypt_token` at the call site (Task 1C's OAuth handshake, and any
    later Zotero-calling code) rather than reaching into these columns
    directly."""

    __tablename__ = "zotero_connection"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id", unique=True, index=True)
    zotero_user_id: str
    oauth_token: str
    oauth_token_secret: str
    connected_at: datetime = Field(default_factory=utcnow)


class SortOrder(StrEnum):
    relevance = "relevance"
    recency = "recency"
    citations = "citations"


class SwipeBehavior(StrEnum):
    interested = "interested"
    not_interested = "not_interested"


class SearchSession(SQLModel, table=True):
    """The current query + settings for a `Session` (§9.2). Per §3.5, a new
    search *replaces* the current one — this is a one-to-one, upsert-in-
    place relationship, never a growing history table."""

    __tablename__ = "search_session"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id", unique=True, index=True)
    query: str
    sort: SortOrder = Field(default=SortOrder.relevance)
    # JSON list, subset of {"last_author", "journal", "pub_date"} (§3.2.C;
    # "country" deliberately excluded per §7.4).
    read_aloud_fields: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    default_swipe_behavior: SwipeBehavior = Field(default=SwipeBehavior.interested)
    speed: float = Field(default=1.0)
    updated_at: datetime = Field(default_factory=utcnow)
    # --- Pagination bookkeeping (Task 3A, §7.9's "transparent follow-up
    # ESearch page" requirement) — not in the original §9.2 table listing,
    # added here because GET /queue needs to know (a) how many total PMIDs
    # ESearch reported so it knows whether "running low" means "no more
    # exist" vs "fetch the next page", and (b) what `retstart` to resume
    # from. Kept on `SearchSession` since it's 1:1 with the query that
    # produced these counts and is replaced/reset exactly when a new
    # search replaces the old one (§3.5), same lifecycle as everything
    # else on this row.
    total_result_count: int | None = None
    next_retstart: int = 0


class Paper(SQLModel, table=True):
    """Global, session-independent cache of PubMed/iCite data, keyed by
    PMID (§9.2) — shared across every session, never duplicated per user."""

    __tablename__ = "paper"

    pmid: str = Field(primary_key=True)
    title: str
    # JSON list of {"first_name": ..., "last_name": ...} from EFetch's
    # AuthorList (§7.5) — feeds Zotero `creators` on push (§8.6).
    authors: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    last_author: str | None = None
    journal: str | None = None
    pub_date: str | None = None
    doi: str | None = None
    display_abstract: str | None = None
    spoken_abstract: str | None = None
    citation_count: int | None = None
    citation_fetched_at: datetime | None = None
    esummary_fetched_at: datetime | None = None
    efetch_fetched_at: datetime | None = None
    # --- Fields added by Task 3A, flagged as needed-but-not-yet-persisted
    # in Task 1B's log and Task 1D's log respectively. Populated only once
    # EFetch has actually run for this PMID (i.e. together with
    # `efetch_fetched_at`) — null until then.
    # §13.3: MEDLINE `Language` code, needed to recompute
    # `narration_unavailable` (Task 1D's `is_narration_unavailable`)
    # without re-fetching EFetch.
    language: str | None = None
    # §13.4: convenience flag from EFetch's PublicationType list.
    retracted: bool = False
    # Raw structured sections (§7.5's `AbstractText`/`Label` pairs) this
    # paper's `display_abstract`/`spoken_abstract` were built from — kept
    # so `GET /papers/{pmid}/abstract` can re-derive the full
    # `SegmentedAbstractResponse` (CONTRACTS.md §1) from a cache hit alone,
    # via Task 1D's `build_segmented_abstract`, without ever calling
    # PubMed again (§9.2/§13.6: cached Paper rows keep serving regardless
    # of PubMed being reachable). JSON list of `{"label": str|None,
    # "text": str}`, one entry per original `AbstractText` element.
    abstract_sections: list[dict[str, str | None]] | None = Field(
        default=None, sa_column=Column(JSON)
    )


class DecisionState(StrEnum):
    pending = "pending"
    interested = "interested"
    not_interested = "not_interested"


class DecidedVia(StrEnum):
    swipe = "swipe"
    auto = "auto"
    manual_remove = "manual_remove"


class QueueDecision(SQLModel, table=True):
    """One row per (search session, paper) pair (§9.2) — this single table
    *is* both the live queue state and the Saved List (§5.4): the Saved List
    is simply the rows where `decision == interested` for the current
    `SearchSession`."""

    __tablename__ = "queue_decision"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id", index=True)
    pmid: str = Field(foreign_key="paper.pmid", index=True)
    position: int
    decision: DecisionState = Field(default=DecisionState.pending)
    decided_via: DecidedVia | None = None
    decided_at: datetime | None = None


class ZoteroExport(SQLModel, table=True):
    """Tracks which `QueueDecision`s have actually been pushed to Zotero
    (§9.2) — satisfies §8.7's partial-batch-failure requirement: a failed
    multi-batch push must know exactly which papers still need retrying."""

    __tablename__ = "zotero_export"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id", index=True)
    pmid: str = Field(foreign_key="paper.pmid", index=True)
    zotero_item_key: str
    zotero_collection_key: str
    pushed_at: datetime = Field(default_factory=utcnow)
