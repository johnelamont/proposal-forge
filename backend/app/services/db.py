"""Database access through Supabase's REST API (PostgREST), as the user.

Every request carries the caller's JWT, so Row Level Security decides what is
visible. There is deliberately no service-role path in this module.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings


class DbError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class UserDb:
    def __init__(self, settings: Settings, user_token: str) -> None:
        self._base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = httpx.request(
                method, self._base + path, headers=headers, timeout=15.0, **kwargs
            )
        except httpx.HTTPError as e:
            raise DbError(502, f"Database unreachable: {type(e).__name__}") from e
        if response.status_code >= 400:
            raise DbError(response.status_code, response.text[:500])
        return response.json() if response.content else None

    # --- job_posts ---------------------------------------------------------

    def insert_job_post(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/job_posts",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def get_job_post(self, job_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "/job_posts", params={"id": f"eq.{job_id}", "select": "*"}
        )
        return rows[0] if rows else None

    def update_job_post(self, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "PATCH",
            "/job_posts",
            params={"id": f"eq.{job_id}"},
            json=patch,
            headers={"Prefer": "return=representation"},
        )
        if not rows:
            raise DbError(404, "Job post not found")
        return rows[0]

    def list_job_posts(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/job_posts",
            params={
                "select": "id,title:analysis->parsed->>title,parse_status,"
                "upwork_job_id,decision,created_at",
                "order": "created_at.desc",
            },
        )
