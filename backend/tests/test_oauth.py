"""Task 1C tests, SPEC.md §15.1/§15.7 (automated half) — Zotero OAuth 1.0a
handshake (`app.auth.oauth`).

Per this task's build-log PIVOT entry: §15.7 says to stub the OAuth
provider with `respx`, but `respx` only intercepts `httpx` traffic and
§8.1 pins `requests-oauthlib` (built on `requests`) for this specific
handshake — so these tests stub the three real Zotero OAuth URLs at the
HTTP layer with `responses` (the `requests`-equivalent of `respx`)
instead, which preserves the spirit of "stub the wire", not just the tool
name.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from app.auth import oauth
from app.middleware.session import OAuthSessionBinding


@pytest.fixture(autouse=True)
def _isolated_binding(monkeypatch: pytest.MonkeyPatch) -> OAuthSessionBinding:
    """Every test gets a fresh, isolated `OAuthSessionBinding` instance
    rather than sharing the process-wide singleton, so tests can't leak
    pending tokens into one another."""
    binding = OAuthSessionBinding()
    monkeypatch.setattr(oauth, "oauth_session_binding", binding)
    return binding


@pytest.fixture(autouse=True)
def _configured_client_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth.settings, "zotero_client_key", "test-client-key")
    monkeypatch.setattr(oauth.settings, "zotero_client_secret", "test-client-secret")
    monkeypatch.setattr(
        oauth.settings, "zotero_callback_url", "https://litlist.example/api/v1/zotero/auth/callback"
    )


@responses.activate
def test_start_handshake_binds_token_to_session_and_returns_authorize_url(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    responses.add(
        responses.POST,
        oauth.ZOTERO_REQUEST_TOKEN_URL,
        body="oauth_token=req-token-1&oauth_token_secret=req-secret-1&oauth_callback_confirmed=true",
        status=200,
    )

    authorize_url = oauth.start_handshake("session-abc")

    assert authorize_url.startswith(oauth.ZOTERO_AUTHORIZE_URL)
    query = parse_qs(urlparse(authorize_url).query)
    assert query["oauth_token"] == ["req-token-1"]
    assert query["library_access"] == ["1"]
    assert query["write_access"] == ["1"]

    # The binding primitive (Task 1A) now holds this token keyed to the
    # session that started the flow.
    resolved = _isolated_binding.resolve("session-abc", "req-token-1")
    assert resolved == "req-secret-1"


@responses.activate
def test_start_handshake_never_sends_a_request_supplied_callback(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    """§8.2's open-redirect fix: the callback URL used is always the fixed,
    server-configured one — never anything derived from caller input (this
    function doesn't even accept a callback URL parameter)."""
    captured: dict[str, str] = {}

    def _record_request(request):  # type: ignore[no-untyped-def]
        header = request.headers.get("Authorization", "")
        captured["authorization_header"] = (
            header.decode() if isinstance(header, bytes) else header
        )
        return (200, {}, "oauth_token=req-token-1&oauth_token_secret=req-secret-1")

    responses.add_callback(
        responses.POST, oauth.ZOTERO_REQUEST_TOKEN_URL, callback=_record_request
    )

    oauth.start_handshake("session-abc")

    # The OAuth1 Authorization header carries the signed `oauth_callback`
    # parameter — assert it's exactly the fixed, server-configured URL
    # (percent-encoded), never anything else.
    from urllib.parse import quote

    expected_callback = quote(oauth.settings.zotero_callback_url, safe="")
    assert f'oauth_callback="{expected_callback}"' in captured["authorization_header"]

    # Structural guarantee too: start_handshake's signature has no way to
    # accept a caller-supplied redirect target at all.
    import inspect

    assert "callback" not in inspect.signature(oauth.start_handshake).parameters


@responses.activate
def test_complete_handshake_succeeds_for_matching_session(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    _isolated_binding.store("session-abc", "req-token-1", "req-secret-1")
    responses.add(
        responses.POST,
        oauth.ZOTERO_ACCESS_TOKEN_URL,
        body="oauth_token=access-token-1&oauth_token_secret=access-secret-1&userID=123456",
        status=200,
    )

    credentials = oauth.complete_handshake("session-abc", "req-token-1", "verifier-1")

    assert credentials.oauth_token == "access-token-1"
    assert credentials.oauth_token_secret == "access-secret-1"
    assert credentials.zotero_user_id == "123456"


@responses.activate
def test_complete_handshake_missing_userid_never_logs_raw_credentials(
    _isolated_binding: OAuthSessionBinding, caplog: pytest.LogCaptureFixture
) -> None:
    """§9.6: `oauth_token`/`oauth_token_secret` are live bearer credentials
    that must never appear in plaintext outside the Fernet-encryption call
    site (`app.models.crypto`). A malformed Zotero response missing
    `userID` must not leak these into server logs on its error path."""
    _isolated_binding.store("session-abc", "req-token-1", "req-secret-1")
    realistic_token = "sekret-oauth-token-value-should-never-be-logged"
    realistic_secret = "sekret-oauth-token-secret-should-never-be-logged"
    responses.add(
        responses.POST,
        oauth.ZOTERO_ACCESS_TOKEN_URL,
        body=f"oauth_token={realistic_token}&oauth_token_secret={realistic_secret}",
        status=200,
    )

    with caplog.at_level("ERROR"):
        with pytest.raises(oauth.ZoteroOAuthProviderError):
            oauth.complete_handshake("session-abc", "req-token-1", "verifier-1")

    log_text = caplog.text
    assert realistic_token not in log_text
    assert realistic_secret not in log_text


def test_complete_handshake_rejects_mismatched_session(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    _isolated_binding.store("session-victim", "req-token-1", "req-secret-1")

    with pytest.raises(oauth.ZoteroSessionMismatchError):
        oauth.complete_handshake("session-attacker", "req-token-1", "verifier-1")


def test_complete_handshake_rejects_unknown_or_expired_token(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    with pytest.raises(oauth.ZoteroSessionMismatchError):
        oauth.complete_handshake("session-abc", "never-issued-token", "verifier-1")


@responses.activate
def test_complete_handshake_replay_is_rejected(_isolated_binding: OAuthSessionBinding) -> None:
    """A second callback for the same request token (replayed URL) must
    fail even with the correct session, since the binding is single-use."""
    _isolated_binding.store("session-abc", "req-token-1", "req-secret-1")
    responses.add(
        responses.POST,
        oauth.ZOTERO_ACCESS_TOKEN_URL,
        body="oauth_token=access-token-1&oauth_token_secret=access-secret-1&userID=123456",
        status=200,
    )

    oauth.complete_handshake("session-abc", "req-token-1", "verifier-1")

    with pytest.raises(oauth.ZoteroSessionMismatchError):
        oauth.complete_handshake("session-abc", "req-token-1", "verifier-1")


@responses.activate
def test_start_handshake_raises_provider_error_when_zotero_unreachable(
    _isolated_binding: OAuthSessionBinding,
) -> None:
    responses.add(
        responses.POST,
        oauth.ZOTERO_REQUEST_TOKEN_URL,
        status=503,
    )

    with pytest.raises(oauth.ZoteroOAuthProviderError):
        oauth.start_handshake("session-abc")


def test_start_handshake_requires_configured_client_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oauth.settings, "zotero_client_key", None)
    monkeypatch.setattr(oauth.settings, "zotero_client_secret", None)

    with pytest.raises(oauth.ZoteroOAuthProviderError):
        oauth.start_handshake("session-abc")


def test_post_auth_redirect_url_is_fixed_and_not_request_influenceable() -> None:
    """`post_auth_redirect_url` takes no arguments at all — structurally
    incapable of honoring a caller-supplied redirect target (§8.2's
    open-redirect fix, §11.6)."""
    import inspect

    assert inspect.signature(oauth.post_auth_redirect_url).parameters == {}
    assert re.match(r"^https?://", oauth.post_auth_redirect_url())
