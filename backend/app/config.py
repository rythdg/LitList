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


settings = Settings()
