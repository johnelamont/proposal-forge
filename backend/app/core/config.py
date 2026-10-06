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

    # Supabase project this backend verifies user JWTs against. Requests are
    # made with the caller's JWT so RLS applies; the service-role key is never
    # used on a user's behalf.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""

    # Claude API. Unused until F1 (job post parsing) is built.
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
