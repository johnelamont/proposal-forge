"""Zoho OAuth and CRM calls (F6). The only module that talks to Zoho.

Scopes are create and update on Leads; nothing is ever read from Zoho.
Every failure becomes a ZohoError with a message safe to show the operator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

SCOPES = "ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE"
UPSERT_PATH = "/crm/v8/Leads/upsert"


class ZohoError(Exception):
    def __init__(self, message: str, status: int | None = None, *, reconnect=False):
        super().__init__(message)
        self.message = message
        self.status = status
        self.reconnect = reconnect  # the refresh token is no good; reconnect


@dataclass
class TokenGrant:
    refresh_token: str
    access_token: str
    api_domain: str
    expires_in: int


@dataclass
class UpsertResult:
    lead_id: str
    action: str  # 'insert' | 'update'
    status: int


class ZohoGateway(Protocol):
    def authorize_url(self, state: str) -> str: ...
    def exchange_code(self, code: str) -> TokenGrant: ...
    def access_token(self, refresh_token: str) -> tuple[str, str]: ...
    def revoke(self, refresh_token: str) -> None: ...
    def upsert_lead(
        self, access_token: str, api_domain: str, payload: dict[str, Any]
    ) -> UpsertResult: ...


class ZohoClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        accounts_url: str,
        api_url: str,
        redirect_uri: str,
        layout_id: str,
        timeout: float = 20.0,
    ) -> None:
        self._id = client_id
        self._secret = client_secret
        self._accounts = accounts_url.rstrip("/")
        self._api = api_url.rstrip("/")
        self._redirect = redirect_uri
        self.layout_id = layout_id
        self._timeout = timeout
        # access tokens cached per refresh token until shortly before expiry
        self._cache: dict[str, tuple[str, str, float]] = {}

    # --- OAuth -------------------------------------------------------------

    def authorize_url(self, state: str) -> str:
        return (
            self._accounts
            + "/oauth/v2/auth?"
            + urlencode(
                {
                    "scope": SCOPES,
                    "client_id": self._id,
                    "response_type": "code",
                    "access_type": "offline",
                    "prompt": "consent",
                    "redirect_uri": self._redirect,
                    "state": state,
                }
            )
        )

    def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            r = httpx.post(
                self._accounts + "/oauth/v2/token", data=data, timeout=self._timeout
            )
        except httpx.HTTPError as e:
            raise ZohoError(
                f"Could not reach Zoho accounts ({type(e).__name__})."
            ) from e
        body = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in body:
            err = str(body.get("error", r.status_code))
            bad = err in {"invalid_code", "invalid_client", "invalid_grant"}
            raise ZohoError(f"Zoho token error: {err}", r.status_code, reconnect=bad)
        return body

    def exchange_code(self, code: str) -> TokenGrant:
        body = self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": self._id,
                "client_secret": self._secret,
                "redirect_uri": self._redirect,
                "code": code,
            }
        )
        if "refresh_token" not in body:
            raise ZohoError(
                "Zoho did not return a refresh token; approve the request again "
                "(the consent screen must be shown)."
            )
        return TokenGrant(
            refresh_token=body["refresh_token"],
            access_token=body["access_token"],
            api_domain=body.get("api_domain", self._api),
            expires_in=int(body.get("expires_in", 3600)),
        )

    def access_token(self, refresh_token: str) -> tuple[str, str]:
        """(access token, api domain), refreshed when the cached one is stale."""
        cached = self._cache.get(refresh_token)
        if cached and cached[2] > time.time() + 60:
            return cached[0], cached[1]
        body = self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self._id,
                "client_secret": self._secret,
                "refresh_token": refresh_token,
            }
        )
        token = body["access_token"]
        domain = body.get("api_domain", self._api)
        self._cache[refresh_token] = (
            token,
            domain,
            time.time() + int(body.get("expires_in", 3600)),
        )
        return token, domain

    def revoke(self, refresh_token: str) -> None:
        self._cache.pop(refresh_token, None)
        try:
            httpx.post(
                self._accounts + "/oauth/v2/token/revoke",
                params={"token": refresh_token},
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            pass  # best effort; the stored copy is deleted regardless

    # --- CRM -----------------------------------------------------------------

    def upsert_lead(
        self, access_token: str, api_domain: str, payload: dict[str, Any]
    ) -> UpsertResult:
        record = dict(payload)
        if self.layout_id:
            record["Layout"] = {"id": self.layout_id}
        body = {
            "data": [record],
            "duplicate_check_fields": ["Upwork_Job_ID"],
            "trigger": [],
        }
        try:
            r = httpx.post(
                api_domain.rstrip("/") + UPSERT_PATH,
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                json=body,
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise ZohoError(f"Could not reach Zoho CRM ({type(e).__name__}).") from e
        if r.status_code == 401:
            raise ZohoError("Zoho rejected the access token.", 401, reconnect=True)
        try:
            data = r.json().get("data", [{}])[0]
        except Exception as e:  # noqa: BLE001
            raise ZohoError(
                f"Unexpected Zoho response ({r.status_code}).", r.status_code
            ) from e
        if r.status_code >= 400 or data.get("status") != "success":
            detail = data.get("message") or data.get("code") or str(r.status_code)
            fields = data.get("details", {})
            api_name = fields.get("api_name")
            if api_name:
                detail += f" (field {api_name})"
            raise ZohoError(f"Zoho refused the Lead: {detail}", r.status_code)
        return UpsertResult(
            lead_id=str(data["details"]["id"]),
            action=str(data.get("action", "unknown")),
            status=r.status_code,
        )
