"""Application settings, loaded from environment variables.

Kept intentionally minimal at Tier 0 — this grows as later tasks (Zotero
OAuth, session cookies, rate limiting) need their own settings, but every
setting is env-var-driven from day one so local dev, CI, and Render/Turso
production never diverge in how config is sourced (SPEC.md §12.3).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database (see app/db.py) ---
    # If unset, db.py falls back to a local SQLite file for dev/test.
    turso_database_url: str | None = None
    turso_auth_token: str | None = None
    local_sqlite_path: str = "./litlist_dev.db"

    # --- App metadata ---
    api_v1_prefix: str = "/api/v1"

    # --- Session identity & secrets (Task 1A, SPEC.md §9.1/§9.6/§10.2) ---
    # Both are dev-only placeholders that MUST be generated (never hand-
    # authored or committed) — see backend/.env.example for how, and
    # app/models/crypto.py / app/middleware/session.py for the documented
    # fallback used when unset (local dev/test convenience only, never a
    # substitute for setting these for real in any persistent deployment,
    # per §12.3). Left optional here so a fresh checkout with no .env still
    # boots and runs the test suite.
    token_encryption_key: str | None = None
    session_cookie_secret: str | None = None

    # --- Zotero OAuth 1.0a (Task 1C, SPEC.md §8.2/§8.3) ---
    # Client key/secret come from registering LitList at
    # zotero.org/oauth/apps (see logs/creds.log — requested, not yet
    # received; left optional so a fresh checkout still boots and the
    # fully-mocked test suite runs with no live credential). Never logged,
    # never returned in any API response.
    zotero_client_key: str | None = None
    zotero_client_secret: str | None = None
    # Fixed, non-dynamic callback path (§8.2's open-redirect fix) — this is
    # the exact URL registered with Zotero in the developer console and is
    # never derived from request headers/query params at request time. The
    # host portion must match wherever this backend is actually deployed
    # (see BuildPlan.md Task 5A); the default here is a local-dev value.
    zotero_callback_url: str = "http://localhost:8000/api/v1/zotero/auth/callback"
    # Fixed in-app path the user lands on after the callback finishes
    # (§8.2 step 6, §11.6) — again never attacker-influenceable. Must be
    # the frontend's real URL-based route (Task 2A's
    # `ZOTERO_OAUTH_CALLBACK_PATH`, `/oauth/zotero/callback`) — the
    # callback route below appends `?status=success` or `?status=error&
    # code=...&message=...` (CONTRACTS.md's OAuth-callback-redirect
    # section) so that route can render success/failure without ever
    # seeing raw JSON. This was previously pointed at the SPA's home path
    # with an unrelated `?zotero=connected` param that the frontend's
    # actual callback route never parsed — a real, unpinned
    # frontend/backend contract mismatch fixed by Task 4B; see that
    # task's build-log PIVOT entry.
    zotero_post_auth_redirect_url: str = "http://localhost:5173/oauth/zotero/callback"

    # --- PubMed E-utilities (Task 1B, SPEC.md §7.7) ---
    # Free NCBI API key — raises the outbound rate ceiling from 3 req/s to
    # 10 req/s (§7.7). Optional so a fresh checkout still boots and the
    # fully respx-mocked test suite runs with no live credential; see
    # logs/creds.log for status. `tool`/`email` are required-in-practice
    # identification NCBI asks every E-utilities client to send.
    ncbi_api_key: str | None = None
    ncbi_tool: str = "litlist"
    ncbi_email: str | None = None

    # --- CORS allow-list (Task 3D, SPEC.md §10.7) ---
    # Comma-separated list of the frontend's real origin(s) — this is
    # LitList's main CSRF defense (§10.7), so it must be an explicit
    # allow-list, never a wildcard, and must be extended (not replaced)
    # with the real deployed frontend origin by Task 5A rather than left
    # at this local-dev default in any real deployment. Read by
    # `app/middleware/security.py`, which owns both the CORS middleware
    # wiring and the additional server-side Origin/Content-Type CSRF
    # guard described there.
    frontend_origins: str = "http://localhost:5173"


settings = Settings()
