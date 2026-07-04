"""Project-wide exception-shape guarantee (BuildPlan.md Task 3D,
SPEC.md §10.3, CONTRACTS.md §2).

This is the **last line of defense** for CONTRACTS.md §2's error
envelope, `{"error": {"code", "message"}}` — every non-2xx JSON response
must look like this, project-wide, and `message` must always be a safe,
pre-written string, never raw exception text or a stack trace (§10.3).

Two adversarial-review findings this task is explicitly told to guard
against (`logs/orchestrator.log`'s Tier 1 Wave 2 "PATTERN NOTE"): 1B's
PubMed client once leaked `NCBI_API_KEY`/`NCBI_EMAIL` via an uncaught
httpx exception's URL-embedded message, and 1C's OAuth handshake once
leaked raw Zotero `oauth_token`/`oauth_token_secret` via a `%r`-formatted
log line. Both were bugs in the *specific modules that raised/logged*
those exceptions (already fixed there) — this handler can't retroactively
scrub a secret that's already baked into `str(exc)` before it reaches
here, but it is the guarantee that whatever ends up in `str(exc)`,
*regardless of exception type*, only ever reaches the server-side log
(`logger.exception`, §12.6), never the HTTP response body. That's the
one thing this module can unconditionally promise, and it's deliberately
the same promise for a plain `Exception`, a SQLAlchemy error, a
`KeyError`, or anything else — no exception-type allowlist/denylist, no
"this one looks safe to echo back" special case.

**Known limitation, not covered by "any unhandled exception, regardless
of type" above: mid-stream failures in a `StreamingResponse` generator**
(flagged by adversarial review's "TASK 3D REVIEW"). `GET /export.csv`
(Task 3C) returns a `StreamingResponse` whose 200 status line and header
bytes — and, once the generator has started yielding, some of its body —
are already flushed to the client by the time an exception can occur
partway through iterating the generator. This handler's mechanism (an
exception handler that constructs and returns a whole new `JSONResponse`)
fundamentally cannot apply here: there is no un-sent response left to
replace once bytes are already in flight, so a failure partway through an
export silently ends as a truncated file, not a 500 with this module's
safe shape. This is a real, accepted gap in "every non-2xx response looks
like CONTRACTS.md §2," not one this module can close from here — the
mitigation lives at the source (`app/routes/export.py`'s own generator
now logs loudly server-side, `logger.exception`, before letting the
failure propagate, so it's at least visible to monitoring rather than
silently read as "an unusually short but otherwise normal export").
Every *non-streaming* response in this backend (every route except
`export.csv`) is unaffected — this handler's core guarantee holds fully
for those.

Three handlers are registered here, all funneling into
`app.errors.api_error_response`/CONTRACTS.md §2's shape:

- `ApiError` — belt-and-suspenders. Every Wave-1 route (3A/3B/3C) already
  catches its own `ApiError`s and returns `api_error_response(...)`
  directly (see `app/errors.py`'s own docstring) rather than relying on
  this handler, so this mostly guards against a *future* route letting
  one propagate by accident.
- `RequestValidationError` (FastAPI/Pydantic's automatic 422) — none of
  Wave 1's own routes trigger this today (they all parse/validate request
  bodies manually via `request.json()` + `model_validate`, precisely so
  they can catch `pydantic.ValidationError` and issue CONTRACTS.md's own
  `validation_error` shape themselves), but any future route that lets
  FastAPI validate a body/query param automatically would otherwise leak
  FastAPI's own default validation-error body shape (`{"detail": [...]}
  `) — a different shape than CONTRACTS.md §2, and one that echoes back
  the submitted value. Normalized to the same `validation_error` (400)
  code/status Task 3A already uses for hand-rolled validation failures,
  with a safe fixed message.
- `Exception` (bare) — the actual catch-all. Anything that reaches here
  is, by definition, a bug or an unanticipated failure mode; it's logged
  server-side with a full stack trace (`logger.exception`) and answered
  with CONTRACTS.md's pinned `internal_error` (500) code and safe
  message. Registering a handler for the bare `Exception` class is
  supported by Starlette/FastAPI's `ExceptionMiddleware` (it walks the
  exception's MRO looking for a registered handler) and is what actually
  makes this apply to "any unhandled exception... regardless of exception
  type" as the task requires.

**This also covers exceptions raised inside this app's own ASGI
middleware** (`app/middleware/ratelimit.py`'s `InboundRateLimitMiddleware`,
`app/middleware/security.py`'s `CSRFGuardMiddleware`/
`SecurityHeadersMiddleware`) — not just route handlers and their
dependencies. An earlier version of this docstring claimed otherwise
(reasoning that `ExceptionMiddleware` is Starlette's innermost layer,
wrapping only the router, with every `add_middleware(...)` layer sitting
outside its reach) — that reasoning about *where* `ExceptionMiddleware`
sits is correct, but it missed a second mechanism: Starlette's
`Starlette.build_middleware_stack` looks up whichever handler is
registered for `Exception` (exactly the one `install_exception_handlers`
registers below) and passes it as `handler=` to `ServerErrorMiddleware`
directly — the outermost layer, wrapping every `add_middleware(...)` call
including this task's own three. `ServerErrorMiddleware.__call__` wraps
its entire inner app (i.e. the whole middleware stack + router) in a
`try/except Exception`, and calls that same handler on anything that
escapes — so a bare `Exception` raised from inside `RateLimitMiddleware`
or `CSRFGuardMiddleware` itself (not just from a route it's wrapping)
still gets CONTRACTS.md §2's safe JSON shape, not a raw traceback.
(`ServerErrorMiddleware` does re-raise after sending that response, so
the exception is still visible to WSGI/ASGI-server-level logging/test
harnesses that ask for it — it just never reaches the *response body*.)
Corrected after tester's TASK 3D VERIFY empirically reproduced this with
a middleware that raises with a fake embedded secret and confirmed the
safe shape came back regardless; see
`test_middleware_errors.py::test_exception_from_middleware_itself_is_still_safe`
for the pinned regression test.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.errors import ApiError, api_error_response, internal_error, validation_error

logger = logging.getLogger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    """Register the three handlers described above on `app`. Called once
    from `app/main.py`'s app-assembly, alongside `install_rate_limiting`
    and `install_security`."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        # A route let its own `ApiError` propagate instead of catching it
        # itself (see module docstring) — still safe to surface directly,
        # since `ApiError.message` is always the same kind of pre-written,
        # safe string this module's own responses use.
        return api_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Deliberately does not include `exc.errors()` in the response —
        # FastAPI's default body echoes back the submitted value per
        # failing field, which is exactly the kind of "map of the backend"
        # detail §10.3 warns against handing back to an untrusted caller.
        # The full validation detail is still logged server-side.
        logger.info(
            "Request validation failed for %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return api_error_response(
            validation_error("The request was invalid. Please check your input and try again.")
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        # `logger.exception` logs the full traceback (type, message,
        # frames/line numbers) server-side only, per §10.3/§12.6 — never
        # returned to the caller below, regardless of what kind of
        # exception this is or what its own message happens to contain.
        logger.exception(
            "Unhandled exception in %s %s (exception type: %s)",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return api_error_response(internal_error())
