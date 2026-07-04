"""Shared API error shape (CONTRACTS.md §2, SPEC.md §10.3).

Not explicitly named in BuildPlan.md's Task 3A ownership list (which
lists only the four route files), but required identically by all four —
duplicating the exact envelope shape four times would invite drift the
first time one of them is edited and not the others, so it lives here
instead. No other Wave-1 task owns this file; Task 3D (cross-cutting
middleware) later adds the catch-all handler for genuinely *unanticipated*
exceptions (also using the `internal_error` code) — this module's own
`internal_error()` helper below is for the narrower case where 3A's own
code can positively identify a real backend bug (as opposed to a caller
error or an external dependency being down) and wants to surface it as
such immediately, rather than letting it fall through to 3D's generic
handler under a code that would look identical either way.

Every route in this task catches `ApiError` itself and returns
`api_error_response(...)` directly (a `Response` instance bypasses
FastAPI's `response_model` serialization entirely, per FastAPI's own
documented behavior) rather than relying on an app-level exception
handler — this keeps 3A's contract correct today without depending on
Task 3D's not-yet-landed global handler, and without this task reaching
into `app/main.py` to register exception handlers that would conflict
with 3D's own planned addition there.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse


class ApiError(Exception):
    """A deliberate, safe-to-surface API error — never raised for an
    unexpected/unhandled condition (those should propagate and eventually
    be caught by Task 3D's catch-all `internal_error` handler instead, so
    they're logged with a full stack trace server-side rather than
    silently swallowed here)."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def api_error_response(error: ApiError) -> JSONResponse:
    """CONTRACTS.md §2's exact envelope — `message` is always the safe,
    pre-written string passed to `ApiError`, never raw exception text."""
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


def service_unavailable(
    message: str = "This service is currently unavailable. Please try again shortly.",
) -> ApiError:
    """CONTRACTS.md §2's `service_unavailable` (503) — an external
    dependency (PubMed/iCite/Zotero) is unreachable, distinct from the
    caller being rate-limited (§13.6)."""
    return ApiError(503, "service_unavailable", message)


def not_found(message: str) -> ApiError:
    """CONTRACTS.md §2's `not_found` (404)."""
    return ApiError(404, "not_found", message)


def validation_error(message: str) -> ApiError:
    """CONTRACTS.md §2's `validation_error` (400)."""
    return ApiError(400, "validation_error", message)


def internal_error(
    message: str = "Something went wrong on our end. Please try again shortly.",
) -> ApiError:
    """CONTRACTS.md §2's `internal_error` (500) — reserved here for a
    genuine, positively-identified backend bug (e.g. `app.integrations.
    pubmed.PubMedParseError`, adversarial review's TASK 3A REVIEW finding
    #2: every article in an EFetch response failing to parse, which looks
    nothing like a caller error or an external outage), so it surfaces to
    monitoring/alerting as a 500 rather than silently collapsing into an
    ordinary-looking 404/503. Callers must log the real cause at ERROR
    *before* raising this — `message` itself stays the same safe,
    pre-written string either way, per §10.3's no-raw-exception-text rule."""
    return ApiError(500, "internal_error", message)
