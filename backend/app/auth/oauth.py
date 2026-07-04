"""Zotero OAuth 1.0a handshake (SPEC.md §8.2/§8.3, BuildPlan.md Task 1C).

This module implements the *logic* of the three-step OAuth 1.0a dance
(request token -> user authorization -> access token exchange) using
`requests-oauthlib` (per SPEC.md §8.1 — the natural choice for this dated
OAuth version; `pyzotero` deliberately does not implement OAuth itself).

It does **not** define any FastAPI route — that's Task 3B's job. Route
handlers call `start_handshake`/`complete_handshake` below and are
responsible for the actual HTTP redirect responses, reading/writing the
`session_id` cookie, and persisting the resulting `ZoteroConnection` row
(encrypting the token/secret via `app.models.crypto.encrypt_token` and
rotating the session via `app.models.rotate_session`, per Task 1A's
docstrings).

**Two security properties enforced here, per SPEC.md §8.2/§10.2:**

1. **Fixed, non-dynamic callback redirect.** The callback URL handed to
   Zotero at the request-token step is always `settings.zotero_callback_url`
   — a value read from server-side configuration, never from anything in
   the incoming request (no `return_to`/`next` query parameter is ever
   consulted). This is what closes the open-redirect vector SPEC.md §8.2
   describes: an attacker cannot influence where a completed OAuth flow
   ends up by crafting a malicious link, because there is no request input
   anywhere in this module that feeds into a redirect target.
2. **Request-token-to-session binding.** `start_handshake` records the
   issued request token against the initiating `session_id` via Task 1A's
   `oauth_session_binding` (`app.middleware.session`); `complete_handshake`
   requires that exact binding to resolve before it will exchange anything
   with Zotero, and rejects (raises `ZoteroSessionMismatchError`) if the
   callback's `session_id` doesn't match, the token is unknown, or the
   binding already expired/was consumed. This is Task 1A's primitive used
   as-is, not reimplemented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from requests_oauthlib import OAuth1Session

from app.config import settings
from app.middleware.session import oauth_session_binding

logger = logging.getLogger(__name__)

ZOTERO_REQUEST_TOKEN_URL = "https://www.zotero.org/oauth/request"
ZOTERO_AUTHORIZE_URL = "https://www.zotero.org/oauth/authorize"
ZOTERO_ACCESS_TOKEN_URL = "https://www.zotero.org/oauth/access"

# §8.3: minimal requested scope — personal-library read/write only, no
# notes access, no group libraries (§8.9).
_AUTHORIZE_PARAMS = {"library_access": "1", "write_access": "1"}


class ZoteroOAuthError(Exception):
    """Base class for handshake failures. Route handlers (Task 3B) catch
    this and translate it into CONTRACTS.md's `{"error": {...}}` shape —
    this module never returns or logs a raw exception to a caller outside
    the backend (§10.3)."""


class ZoteroSessionMismatchError(ZoteroOAuthError):
    """Raised when the OAuth callback's request token doesn't match the
    session that started the handshake (§10.2's binding primitive). Maps to
    CONTRACTS.md's `zotero_session_mismatch` (403)."""


class ZoteroOAuthProviderError(ZoteroOAuthError):
    """Raised when Zotero's OAuth endpoints themselves fail/are unreachable
    (network error, non-2xx response). Maps to CONTRACTS.md's
    `service_unavailable` (503)."""


@dataclass(frozen=True)
class ZoteroCredentials:
    """The durable output of a completed handshake (§8.2 step 4) — plaintext
    here deliberately; encryption (§9.6) is the caller's (Task 3B's)
    responsibility at the point of persistence, matching
    `app.models.crypto`'s documented call-site convention."""

    oauth_token: str
    oauth_token_secret: str
    zotero_user_id: str


def _require_client_credentials() -> tuple[str, str]:
    if not settings.zotero_client_key or not settings.zotero_client_secret:
        # A configuration error, not a client-facing one — surfaced as
        # `service_unavailable` by the route layer rather than leaking
        # "credentials not configured" specifics per §10.3.
        raise ZoteroOAuthProviderError(
            "ZOTERO_CLIENT_KEY/ZOTERO_CLIENT_SECRET are not configured."
        )
    return settings.zotero_client_key, settings.zotero_client_secret


def start_handshake(session_id: str) -> str:
    """Begin the OAuth 1.0a dance for `session_id` (§8.2 step 2).

    Requests a temporary request token from Zotero, binds it to
    `session_id` via `oauth_session_binding` (§10.2 addendum) so the
    callback can later verify it's being completed by the same session, and
    returns the fully-formed Zotero authorize URL the caller should
    redirect the user's browser to.

    Raises `ZoteroOAuthProviderError` if Zotero's request-token endpoint is
    unreachable or rejects the request.
    """
    client_key, client_secret = _require_client_credentials()
    oauth = OAuth1Session(
        client_key,
        client_secret=client_secret,
        callback_uri=settings.zotero_callback_url,
    )
    try:
        fetch_response = oauth.fetch_request_token(ZOTERO_REQUEST_TOKEN_URL)
    except Exception as exc:  # noqa: BLE001 — any transport/parsing failure here
        logger.exception("Zotero OAuth request-token step failed")
        raise ZoteroOAuthProviderError("Failed to obtain a Zotero request token.") from exc

    request_token = fetch_response["oauth_token"]
    request_token_secret = fetch_response["oauth_token_secret"]

    oauth_session_binding.store(session_id, request_token, request_token_secret)

    return str(oauth.authorization_url(ZOTERO_AUTHORIZE_URL, **_AUTHORIZE_PARAMS))


def complete_handshake(session_id: str, request_token: str, verifier: str) -> ZoteroCredentials:
    """Complete the OAuth 1.0a dance (§8.2 steps 3-4) for the callback
    arriving on `session_id`, using the pending `request_token`/`verifier`
    Zotero's redirect supplied.

    Raises `ZoteroSessionMismatchError` if `request_token` wasn't issued to
    exactly this `session_id` (or is unknown/expired/already consumed) —
    the caller (Task 3B) must reject the callback in this case rather than
    proceeding, per §10.2's addendum. Raises `ZoteroOAuthProviderError` if
    the access-token exchange with Zotero itself fails.
    """
    request_token_secret = oauth_session_binding.resolve(session_id, request_token)
    if request_token_secret is None:
        raise ZoteroSessionMismatchError(
            "OAuth callback's request token does not match the session "
            "that started the handshake, or has expired."
        )

    client_key, client_secret = _require_client_credentials()
    oauth = OAuth1Session(
        client_key,
        client_secret=client_secret,
        resource_owner_key=request_token,
        resource_owner_secret=request_token_secret,
        verifier=verifier,
    )
    try:
        tokens = oauth.fetch_access_token(ZOTERO_ACCESS_TOKEN_URL)
    except Exception as exc:  # noqa: BLE001 — any transport/parsing failure here
        logger.exception("Zotero OAuth access-token exchange failed")
        raise ZoteroOAuthProviderError("Failed to complete the Zotero OAuth handshake.") from exc

    try:
        zotero_user_id = str(tokens["userID"])
    except KeyError as exc:
        # Never log `tokens` itself (or interpolate it via %r/%s) — it
        # normally carries the live, unencrypted `oauth_token`/
        # `oauth_token_secret` bearer credentials (§9.6 requires these be
        # Fernet-encrypted before they ever reach storage; a log line is
        # not storage and completely bypasses that). Only log the key
        # *names* present, which is enough to debug a malformed response
        # without leaking any credential material.
        logger.exception(
            "Zotero access-token response missing userID; keys present: %r",
            sorted(tokens.keys()),
        )
        raise ZoteroOAuthProviderError(
            "Zotero's OAuth response did not include the expected user ID."
        ) from exc

    return ZoteroCredentials(
        oauth_token=tokens["oauth_token"],
        oauth_token_secret=tokens["oauth_token_secret"],
        zotero_user_id=zotero_user_id,
    )


def post_auth_redirect_url() -> str:
    """The single fixed in-app path the user is bounced to once the
    callback finishes (§8.2 step 6, §11.6) — a server-configured constant,
    never influenced by request input (same open-redirect rationale as
    `zotero_callback_url` above)."""
    return settings.zotero_post_auth_redirect_url
