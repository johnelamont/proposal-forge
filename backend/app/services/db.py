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


class _Rest:
    _base: str
    _headers: dict[str, str]

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


class AnonDb(_Rest):
    """PostgREST as the anonymous role, for the one inbound call that carries
    no user JWT (F8). The anon role may execute `record_outcome()` and nothing
    else; that function resolves the tenant from the secret hash itself."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {settings.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    def record_outcome(
        self, secret_hash: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/rpc/record_outcome",
            json={"p_secret_hash": secret_hash, "p_payload": payload},
        )


class UserDb(_Rest):
    def __init__(self, settings: Settings, user_token: str) -> None:
        self._base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        }

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

    # --- work_history ------------------------------------------------------

    def insert_work_history(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/work_history",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def list_work_history(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/work_history",
            params={
                "select": "id,name,vertical,tech_stack,complexity,"
                "may_name_client,ended,updated_at",
                "order": "ended.desc.nullslast,updated_at.desc",
            },
        )

    def list_work_history_for_matching(self) -> list[dict[str, Any]]:
        """The fields F2 may compare and send to Claude. No client names,
        no source files, no extraction provenance."""
        return self._request(
            "GET",
            "/work_history",
            params={
                "select": "id,name,summary,tech_stack,vertical,project_type,"
                "complexity,outcomes,budget_band",
            },
        )

    def get_work_history_many(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        return self._request(
            "GET",
            "/work_history",
            params={
                "id": "in.(" + ",".join(ids) + ")",
                "select": "id,name,summary,tech_stack,vertical,project_type,"
                "complexity,outcomes,budget_band",
            },
        )

    # --- zoho (F6) -----------------------------------------------------------

    def get_zoho_connection(self) -> dict[str, Any] | None:
        rows = self._request("GET", "/zoho_connections", params={"select": "*"})
        return rows[0] if rows else None

    def upsert_zoho_connection(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/zoho_connections",
            params={"on_conflict": "user_id"},
            json=row,
            headers={"Prefer": "return=representation,resolution=merge-duplicates"},
        )
        return rows[0]

    def touch_zoho_connection(self) -> None:
        self._request(
            "PATCH",
            "/zoho_connections",
            params={"user_id": "not.is.null"},
            json={"last_used_at": "now()"},
        )

    def delete_zoho_connection(self) -> None:
        self._request("DELETE", "/zoho_connections", params={"user_id": "not.is.null"})

    def insert_oauth_state(self, nonce: str) -> None:
        self._request("POST", "/zoho_oauth_states", json={"nonce": nonce})

    def get_oauth_state(self, nonce: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "/zoho_oauth_states", params={"nonce": f"eq.{nonce}", "select": "*"}
        )
        return rows[0] if rows else None

    def delete_oauth_state(self, nonce: str) -> None:
        self._request("DELETE", "/zoho_oauth_states", params={"nonce": f"eq.{nonce}"})

    def insert_lead_attempt(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/lead_attempts",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def list_lead_attempts(self, proposal_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/lead_attempts",
            params={
                "proposal_id": f"eq.{proposal_id}",
                "select": "*",
                "order": "attempted_at.desc",
            },
        )

    # --- outcomes (F8) --------------------------------------------------------

    def get_integration_secret(self) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "/integration_secrets",
            params={"select": "user_id,created_at,last_used_at"},
        )
        return rows[0] if rows else None

    def upsert_integration_secret(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/integration_secrets",
            params={"on_conflict": "user_id"},
            json=row,
            headers={"Prefer": "return=representation,resolution=merge-duplicates"},
        )
        return rows[0]

    def delete_integration_secret(self) -> None:
        self._request(
            "DELETE", "/integration_secrets", params={"user_id": "not.is.null"}
        )

    def list_outcomes(self, proposal_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/proposal_outcomes",
            params={
                "proposal_id": f"eq.{proposal_id}",
                "select": "*",
                "order": "received_at.desc",
            },
        )

    def get_rag_index(self, proposal_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "/rag_index",
            params={"proposal_id": f"eq.{proposal_id}", "select": "*"},
        )
        return rows[0] if rows else None

    def set_rag_archived(
        self, proposal_id: str, archived: bool
    ) -> dict[str, Any] | None:
        rows = self._request(
            "PATCH",
            "/rag_index",
            params={"proposal_id": f"eq.{proposal_id}"},
            json={"archived": archived},
            headers={"Prefer": "return=representation"},
        )
        return rows[0] if rows else None

    def list_outcome_queue(self) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/outcome_queue",
            params={
                "resolved_at": "is.null",
                "dismissed_at": "is.null",
                "select": "*",
                "order": "received_at.desc",
            },
        )

    def dismiss_queued_outcome(self, queue_id: str) -> bool:
        rows = self._request(
            "PATCH",
            "/outcome_queue",
            params={"id": f"eq.{queue_id}", "dismissed_at": "is.null"},
            json={"dismissed_at": "now()"},
            headers={"Prefer": "return=representation"},
        )
        return bool(rows)

    def resolve_queued_outcome(self, queue_id: str, proposal_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/rpc/resolve_queued_outcome",
            json={"p_queue_id": queue_id, "p_proposal_id": proposal_id},
        )

    def rebuild_rag_index(self) -> int:
        return self._request("POST", "/rpc/rebuild_rag_index", json={})

    def list_proposals_for_attention(self) -> list[dict[str, Any]]:
        """Open proposals with the job title embedded; the strip filters them."""
        return self._request(
            "GET",
            "/proposals",
            params={
                "status": "in.(draft,submitted)",
                "select": "id,status,submitted_at,lead_sync_state,updated_at,"
                "job_posts(title:analysis->parsed->>title)",
                "order": "updated_at.desc",
            },
        )

    # --- profiles ----------------------------------------------------------

    def get_profile(self) -> dict[str, Any] | None:
        rows = self._request("GET", "/profiles", params={"select": "*"})
        return rows[0] if rows else None

    def upsert_profile(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/profiles",
            params={"on_conflict": "user_id"},
            json=row,
            headers={"Prefer": "return=representation,resolution=merge-duplicates"},
        )
        return rows[0]

    # --- proposals -----------------------------------------------------------

    def insert_proposal(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/proposals",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "/proposals", params={"id": f"eq.{proposal_id}", "select": "*"}
        )
        return rows[0] if rows else None

    def get_proposal_by_job(self, job_post_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "/proposals",
            params={"job_post_id": f"eq.{job_post_id}", "select": "*"},
        )
        return rows[0] if rows else None

    def update_proposal(self, proposal_id: str, patch: dict[str, Any]) -> dict:
        rows = self._request(
            "PATCH",
            "/proposals",
            params={"id": f"eq.{proposal_id}"},
            json=patch,
            headers={"Prefer": "return=representation"},
        )
        if not rows:
            raise DbError(404, "Proposal not found")
        return rows[0]

    def list_versions(self, proposal_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/draft_versions",
            params={
                "proposal_id": f"eq.{proposal_id}",
                "select": "*",
                "order": "version.asc",
            },
        )

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "/draft_versions",
            params={"id": f"eq.{version_id}", "select": "*"},
        )
        return rows[0] if rows else None

    def insert_version(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/draft_versions",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def list_approvals(self, proposal_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/proposal_approvals",
            params={
                "proposal_id": f"eq.{proposal_id}",
                "select": "*",
                "order": "approved_at.desc",
            },
        )

    def insert_approval(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "/proposal_approvals",
            json=row,
            headers={"Prefer": "return=representation"},
        )
        return rows[0]

    def get_work_history(self, entry_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "/work_history", params={"id": f"eq.{entry_id}", "select": "*"}
        )
        return rows[0] if rows else None

    def update_work_history(self, entry_id: str, patch: dict[str, Any]) -> dict:
        rows = self._request(
            "PATCH",
            "/work_history",
            params={"id": f"eq.{entry_id}"},
            json=patch,
            headers={"Prefer": "return=representation"},
        )
        if not rows:
            raise DbError(404, "Work history entry not found")
        return rows[0]

    def delete_work_history(self, entry_id: str) -> bool:
        rows = self._request(
            "DELETE",
            "/work_history",
            params={"id": f"eq.{entry_id}"},
            headers={"Prefer": "return=representation"},
        )
        return bool(rows)
