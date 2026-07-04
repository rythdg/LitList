"""Task 1A tests, SPEC.md §15.1 / §10.2's OAuth addendum: "binding primitive
rejects a mismatched/expired token." This is the primitive Task 1C's OAuth
handshake (Wave 2) imports directly — tested standalone here since 1C
doesn't exist yet.
"""

from __future__ import annotations

from app.middleware.session import OAuthSessionBinding


def test_resolve_succeeds_for_matching_session_and_token() -> None:
    binding = OAuthSessionBinding()
    binding.store("session-abc", "req-token-1", "req-secret-1")

    result = binding.resolve("session-abc", "req-token-1")

    assert result == "req-secret-1"


def test_resolve_rejects_mismatched_session() -> None:
    binding = OAuthSessionBinding()
    binding.store("session-victim", "req-token-1", "req-secret-1")

    # A different session (e.g. a replayed/shared callback URL used from a
    # different browser) must not be able to complete the handshake.
    result = binding.resolve("session-attacker", "req-token-1")

    assert result is None


def test_resolve_is_single_use_even_on_a_correct_match() -> None:
    binding = OAuthSessionBinding()
    binding.store("session-abc", "req-token-1", "req-secret-1")

    first = binding.resolve("session-abc", "req-token-1")
    second = binding.resolve("session-abc", "req-token-1")

    assert first == "req-secret-1"
    assert second is None  # already consumed — no replay


def test_resolve_is_single_use_even_after_a_mismatched_attempt() -> None:
    """A single mismatched attempt burns the token too — otherwise an
    attacker could probe repeatedly against the same pending token."""
    binding = OAuthSessionBinding()
    binding.store("session-victim", "req-token-1", "req-secret-1")

    mismatched = binding.resolve("session-attacker", "req-token-1")
    correct_after = binding.resolve("session-victim", "req-token-1")

    assert mismatched is None
    assert correct_after is None


def test_resolve_rejects_unknown_token() -> None:
    binding = OAuthSessionBinding()
    result = binding.resolve("session-abc", "never-issued-token")
    assert result is None


def test_resolve_rejects_expired_token(monkeypatch) -> None:
    binding = OAuthSessionBinding(ttl_seconds=60)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "app.middleware.session.time.monotonic", lambda: fake_time[0]
    )

    binding.store("session-abc", "req-token-1", "req-secret-1")

    fake_time[0] += 61  # past the 60s TTL

    result = binding.resolve("session-abc", "req-token-1")

    assert result is None
