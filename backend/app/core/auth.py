"""Supabase JWT verification.

The frontend sends the user's Supabase access token. We verify it and keep the
raw token so database calls run as that user (RLS applies). The service-role
key is never used on a user's behalf.

Supabase signs user tokens with asymmetric keys (ES256/RS256) published at
`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`; older projects use HS256 with
the project's JWT secret. Both are accepted: the token's own `alg` decides.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)

ASYMMETRIC_ALGS = ("ES256", "RS256")


@dataclass(frozen=True)
class CurrentUser:
    id: str
    token: str


@lru_cache
def _jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail)


def verify_token(token: str, settings: Settings) -> dict:
    """Return the claims of a valid Supabase access token, or raise 401."""
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError as e:
        raise _unauthorized("Malformed token") from e

    try:
        if alg in ASYMMETRIC_ALGS:
            if not settings.supabase_url:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, "SUPABASE_URL is not set"
                )
            jwks_url = (
                settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
            )
            key = _jwk_client(jwks_url).get_signing_key_from_jwt(token).key
            return jwt.decode(
                token, key, algorithms=list(ASYMMETRIC_ALGS), audience="authenticated"
            )
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "SUPABASE_JWT_SECRET is not set",
                )
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except jwt.PyJWTError as e:
        raise _unauthorized("Invalid token") from e
    raise _unauthorized(f"Unsupported token algorithm: {alg}")


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    claims = verify_token(credentials.credentials, settings)
    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("Token has no subject")
    return CurrentUser(id=sub, token=credentials.credentials)
