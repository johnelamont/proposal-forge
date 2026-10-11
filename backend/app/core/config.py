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

    # Zoho CRM (F6). Server-based OAuth client; each user connects their own
    # account. Refresh tokens are stored AES-GCM encrypted with
    # token_encryption_key (32 random bytes, base64), never in configuration.
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_accounts_url: str = "https://accounts.zoho.com"
    zoho_api_url: str = "https://www.zohoapis.com"
    zoho_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/zoho/callback"
    zoho_leads_layout_id: str = ""
    token_encryption_key: str = ""
    frontend_url: str = "http://localhost:3000"

    @property
    def zoho_configured(self) -> bool:
        return bool(
            self.zoho_client_id
            and self.zoho_client_secret
            and self.token_encryption_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
