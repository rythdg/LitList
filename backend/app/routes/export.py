"""CSV export endpoint (BuildPlan.md Task 3C), implementing SPEC.md §8.8
(column spec, CSV/formula-injection neutralization) and §10.4's
`GET /api/v1/export.csv` row.

Scope: this module owns exactly one route — `GET /export.csv` — which
streams the current session's Saved List (§5.4: `QueueDecision` rows
where `decision == interested`, joined with the global `Paper` cache) as
a CSV file. No Zotero dependency (§8.8's own note); works purely off
local DB state, so unlike Task 3A/3B's routes this never calls out to
`pubmed_client`/`icite_client`/`zotero_client`.

**CSV/formula injection (§8.8).** Every field here ultimately traces back
to PubMed metadata (title, authors, journal, pub_date) — external,
uncontrolled text (CONTRACTS.md's own note that PubMed-sourced text is
untrusted). If a field value starts with `=`, `+`, `-`, or `@`,
spreadsheet software (Excel, Google Sheets) may interpret it as a
formula when the file is opened. Every column is passed through
`_neutralize_formula_injection` before being written — SPEC.md §8.8
names "prefixing with a leading single quote (or tab character)" as the
mitigation; this module uses a leading single quote, applied uniformly
to all seven columns (not just the ones PubMed populates with free text)
since the cost is one cheap string check per field and there's no reason
to special-case which columns are "probably safe" (PMID/DOI/URL are
backend-derived from PubMed IDs, but the underlying PMID string itself
still ultimately originates from an external API response).

The trigger check looks past leading whitespace and Unicode "format"
(category `Cf`) characters — e.g. a leading tab, space, or an invisible
RTL-override character — before testing the first *visible* character
against the trigger set (see `_first_significant_char`). This closes a
real bypass an adversarial review caught: some spreadsheet CSV importers
themselves strip leading whitespace before checking for a formula
trigger, so a raw `"\t=1+1"` field would sail through an unmodified
`str.startswith` check yet still be interpreted as a formula by the
importer on open. The single-quote prefix is still applied to the
*original, unmodified* value (never to a stripped/mutated copy) — this
is purely a smarter trigger-detection check, not a content transform.

**Missing DOI (§13.4).** A paper with no DOI exports with a blank DOI
*and* URL column (the URL is derived from the DOI, `https://doi.org/
<doi>`, mirroring the same omission the Zotero push payload does in
§8.6/§13.4) — never an error, never a crashed stream.
"""

from __future__ import annotations

import csv
import logging
import unicodedata
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.db import get_session
from app.middleware.session import get_current_session
from app.models.entities import DecisionState, Paper, QueueDecision
from app.models.entities import Session as SessionRow

logger = logging.getLogger(__name__)

router = APIRouter()

# §8.8's exact column set and order.
_CSV_COLUMNS = ["Title", "Authors", "Journal", "Date", "DOI", "PMID", "URL"]

# Characters Excel/Google Sheets treat as formula triggers (§8.8).
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def _first_significant_char(value: str) -> str:
    """Return the first character of `value` that isn't leading
    whitespace or a Unicode "format" (category `Cf`) character —
    invisible-but-meaningful codepoints like the RTL/LTR override marks
    (`‮`/`‭`) or a zero-width joiner. Returns `""` if `value` is
    empty or consists entirely of such characters.

    This exists because a naive `value.startswith(...)` check is
    bypassable: a field like `"\t=1+1"` or `"‮=1+1"` doesn't
    literally start with `=`, but some spreadsheet CSV importers strip
    leading whitespace/format characters themselves before evaluating a
    formula trigger — so the *importer's* notion of "first character"
    can disagree with Python's raw string indexing, and it's the
    importer's notion that matters for whether this is actually
    exploitable."""
    for char in value:
        if char.isspace():
            continue
        if unicodedata.category(char) == "Cf":
            continue
        return char
    return ""


def _neutralize_formula_injection(value: str) -> str:
    """Prefix `value` with a leading single quote if, once leading
    whitespace/invisible-format characters are looked past, it starts
    with a character spreadsheet software would interpret as a formula
    trigger (§8.8). Safe to call on every field unconditionally — a
    no-op for values with no such character. The prefix is always
    applied to the original, unmodified `value` — never to a stripped
    copy — so no legitimate content (including genuine leading
    whitespace) is altered beyond the one added quote character."""
    if _first_significant_char(value) in _FORMULA_TRIGGER_CHARS:
        return f"'{value}"
    return value


def _format_authors(authors: list[dict[str, str]]) -> str:
    """Join EFetch-shaped author dicts (`{"first_name", "last_name"}`,
    per `Paper.authors`, §9.2/§7.5) into a single semicolon-separated
    string for the CSV's one "Authors" column."""
    names = []
    for author in authors:
        first = author.get("first_name", "").strip()
        last = author.get("last_name", "").strip()
        full_name = " ".join(part for part in (first, last) if part)
        if full_name:
            names.append(full_name)
    return "; ".join(names)


def _paper_row(paper: Paper) -> list[str]:
    """Build one CSV row for `paper`, per §8.8's column set. Missing DOI
    (§13.4) leaves both the DOI and URL columns blank rather than
    erroring — the URL is derived from the DOI (mirroring §8.6's Zotero
    item payload, `https://doi.org/<doi>`), so there is nothing to
    derive it from when the DOI itself is absent."""
    doi = paper.doi or ""
    url = f"https://doi.org/{doi}" if doi else ""
    raw_values = [
        paper.title or "",
        _format_authors(paper.authors),
        paper.journal or "",
        paper.pub_date or "",
        doi,
        paper.pmid,
        url,
    ]
    return [_neutralize_formula_injection(value) for value in raw_values]


class _EchoBuffer:
    """A file-like object whose `write` returns the string it was given
    instead of buffering it, so `csv.writer` can be used to format one
    row at a time and each formatted line is yielded straight into the
    `StreamingResponse` — no need to accumulate the whole CSV (which
    could be an arbitrarily long Saved List) in memory."""

    def write(self, value: str) -> str:
        return value


def _iter_saved_papers_csv(db: DBSession, session_id: str) -> Iterator[str]:
    """Yield the CSV file for `session_id`'s Saved List one line at a
    time. Saved List membership is exactly `QueueDecision.decision ==
    interested` for this session (§5.4, §9.2's note that the Saved List
    *is* the `QueueDecision` table filtered this way, not a separate
    table)."""
    writer = csv.writer(_EchoBuffer())
    yield writer.writerow(_CSV_COLUMNS)

    # Task 3D note (adversarial review, "TASK 3D REVIEW"): once this
    # generator has yielded at least the header row, the response's 200
    # status and some body bytes are already flushed to the client — a
    # failure partway through can no longer be turned into a clean 4xx/5xx
    # (§10.3's error-shape guarantee doesn't apply here; there is no
    # response left to reshape). The best available mitigation at this
    # layer is to make the failure loud server-side (so it's caught by
    # monitoring rather than silently read as "an unusually short but
    # otherwise normal export") rather than letting it vanish as a
    # truncated connection with no log trace — the client still just sees
    # a truncated file, which is a known, accepted limitation of
    # streaming a response whose success/failure isn't knowable until
    # it's already in flight.
    try:
        rows = db.exec(
            select(Paper, QueueDecision)
            .join(QueueDecision, QueueDecision.pmid == Paper.pmid)  # type: ignore[arg-type]
            .where(
                QueueDecision.session_id == session_id,
                QueueDecision.decision == DecisionState.interested,
            )
            .order_by(QueueDecision.position)  # type: ignore[arg-type]
        )
        for paper, _decision in rows:
            yield writer.writerow(_paper_row(paper))
    except Exception:
        logger.exception(
            "GET /export.csv: streaming failed partway through for session_id=%s "
            "— client received a truncated file with no error signal in the "
            "response body (streaming responses can't be retroactively turned "
            "into an error status once bytes are already in flight)",
            session_id,
        )
        raise


@router.get("/export.csv")
def export_csv(
    session: SessionRow = Depends(get_current_session),  # noqa: B008 — standard FastAPI DI pattern
    db: DBSession = Depends(get_session),  # noqa: B008 — standard FastAPI DI pattern
) -> StreamingResponse:
    """`GET /api/v1/export.csv` (§10.4) — streams the current session's
    Saved List as CSV. Read-only, no request body, so §10.7's CORS/CSRF
    "state-changing endpoints require a JSON body" rule doesn't apply
    here."""
    return StreamingResponse(
        _iter_saved_papers_csv(db, session.session_id),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="litlist_export.csv"'},
    )
