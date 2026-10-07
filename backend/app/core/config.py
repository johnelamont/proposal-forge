"""Application settings, loaded from the environment and an optional `.env` file.

Only configuration lives here. Secrets are supplied through the environment
(or a git-ignored `.env`); see `.env.example` for the expected names.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Proposal Forge API"
    environment: str = "development"

    # Origins allowed to call this API from a browser (the Next.js frontend).
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Supabase project this backend talks to. User requests are made with the
    # caller's JWT (verified with the JWT secret) so RLS applies; the anon key
    # is the public API key PostgREST expects alongside it. The service-role
    # key is never used on a user's behalf.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # Claude API. Empty key → the AI layer reports itself as skipped (R8).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
