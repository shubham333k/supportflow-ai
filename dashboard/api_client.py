"""
API Client for SupportFlow AI Streamlit Dashboard.
Communicates strictly via REST API with FastAPI (no direct DB queries).
"""

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("API_KEY", "dev-supportflow-api-key-change-me")


class SupportFlowAPIClient:
    """Client for backend API communication."""

    def __init__(self, base_url: str = API_BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }
        self.timeout = 45.0

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, headers=self.headers, timeout=self.timeout)

    # ── Health ────────────────────────────────────────────────────────────

    def get_health(self) -> dict[str, Any]:
        """Check system health status."""
        try:
            with self._client() as c:
                resp = c.get("/healthz")
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "unhealthy", "code": resp.status_code}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    # ── Analytics ─────────────────────────────────────────────────────────

    def get_analytics_overview(self) -> dict[str, Any]:
        """Fetch KPI card summary metrics."""
        try:
            with self._client() as c:
                resp = c.get("/analytics/overview")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {
            "total_tickets": 0,
            "open_tickets": 0,
            "escalated_tickets": 0,
            "ai_resolved_tickets": 0,
            "sla_at_risk_count": 0,
            "avg_first_response_min": 0.0,
        }

    def get_analytics_trends(self) -> dict[str, Any]:
        """Fetch distribution data and rates."""
        try:
            with self._client() as c:
                resp = c.get("/analytics/trends")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {
            "intent_distribution": {},
            "sentiment_distribution": {},
            "tier_distribution": {},
            "status_distribution": {},
            "escalation_rate_pct": 0.0,
            "ai_resolution_rate_pct": 0.0,
            "sla_breach_rate_pct": 0.0,
            "crm_sync_success_rate_pct": 100.0,
        }

    # ── Tickets ───────────────────────────────────────────────────────────

    def get_tickets(
        self,
        tier: str | None = None,
        status: str | None = None,
        intent: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List tickets with optional filtering."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if tier and tier != "all":
            params["tier"] = tier
        if status and status != "all":
            params["status"] = status
        if intent and intent != "all":
            params["intent"] = intent

        try:
            with self._client() as c:
                resp = c.get("/tickets", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    def get_ticket_detail(self, ticket_id: str) -> dict[str, Any] | None:
        """Fetch full ticket detail with enriched relations."""
        try:
            with self._client() as c:
                resp = c.get(f"/tickets/{ticket_id}")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None

    def approve_draft(self, ticket_id: str, edited_body: str | None = None, agent_name: str = "agent:ui") -> dict[str, Any]:
        """Approve and send draft reply."""
        payload: dict[str, Any] = {"agent_name": agent_name}
        if edited_body:
            payload["edited_body"] = edited_body
        with self._client() as c:
            resp = c.post(f"/tickets/{ticket_id}/approve", json=payload)
            resp.raise_for_status()
            return resp.json()

    def escalate_ticket(self, ticket_id: str, reason: str = "dashboard_escalation") -> dict[str, Any]:
        """Escalate ticket to immediate tier."""
        with self._client() as c:
            resp = c.post(f"/tickets/{ticket_id}/escalate", params={"reason": reason})
            resp.raise_for_status()
            return resp.json()

    def resolve_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Mark ticket as resolved."""
        with self._client() as c:
            resp = c.post(f"/tickets/{ticket_id}/resolve")
            resp.raise_for_status()
            return resp.json()

    def trigger_analyze(self, ticket_id: str) -> dict[str, Any]:
        """Re-run AI classifier and escalation scoring."""
        with self._client() as c:
            resp = c.post(f"/tickets/{ticket_id}/analyze")
            resp.raise_for_status()
            return resp.json()

    def trigger_draft(self, ticket_id: str) -> dict[str, Any]:
        """Re-run RAG retrieval and drafting pipeline."""
        with self._client() as c:
            resp = c.post(f"/tickets/{ticket_id}/draft")
            resp.raise_for_status()
            return resp.json()

    # ── Knowledge Base ────────────────────────────────────────────────────

    def get_kb_documents(self) -> list[dict[str, Any]]:
        """List all indexed knowledge base documents."""
        try:
            with self._client() as c:
                resp = c.get("/kb/documents")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    def trigger_kb_ingest(self) -> dict[str, Any]:
        """Trigger ingestion of kb/ directory."""
        with self._client() as c:
            resp = c.post("/kb/ingest")
            resp.raise_for_status()
            return resp.json()

    def search_kb(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        """Run semantic test query against KB chunks."""
        try:
            with self._client() as c:
                resp = c.get("/kb/search", params={"query": query, "limit": limit})
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    # ── SLA ───────────────────────────────────────────────────────────────

    def trigger_sla_scan(self) -> dict[str, Any]:
        """Trigger scheduled SLA scan."""
        with self._client() as c:
            resp = c.post("/sla/scan")
            resp.raise_for_status()
            return resp.json()


# Shared singleton instance
api = SupportFlowAPIClient()
