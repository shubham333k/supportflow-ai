import unittest.mock as mock
import pytest
from httpx import AsyncClient, ASGITransport

from api.app.main import app
from api.app.core.security import (
    RateLimiter,
    generate_hmac_signature,
    verify_hmac_signature,
)
from api.app.integrations.llm import LLMClient
from api.app.integrations.hubspot import HubSpotClient


@pytest.mark.asyncio
class TestSecurityAndHardening:
    async def test_hmac_signature_generation_and_verification(self):
        secret = "test-secret-key-12345"
        payload = '{"channel":"email","subject":"Test Security"}'
        
        signature = generate_hmac_signature(payload, secret)
        assert len(signature) == 64  # SHA256 hex length
        assert verify_hmac_signature(payload, signature, secret) is True
        assert verify_hmac_signature(payload + "tampered", signature, secret) is False
        assert verify_hmac_signature(payload, "invalid_sig", secret) is False

    async def test_rate_limiter_sliding_window(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_key = "user_123"

        assert limiter.is_allowed(user_key) is True
        assert limiter.is_allowed(user_key) is True
        assert limiter.is_allowed(user_key) is True
        assert limiter.is_allowed(user_key) is False  # 4th request within window rejected


@pytest.mark.asyncio
class TestFailureDrills:
    async def test_drill_gemini_429_quota_exhaustion_triggers_failsafe(self, async_db):
        """Simulate LLM quota exhaustion (429) during analysis."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "dev-supportflow-api-key-change-me"}) as client:
            # 1. Ingest ticket
            ingest_resp = await client.post(
                "/api/v1/messages/ingest",
                json={
                    "channel": "email",
                    "external_message_id": "test-drill-429-msg",
                    "thread_id": "test-drill-429-thread",
                    "from_email": "user.429@example.com",
                    "from_name": "Quota User",
                    "subject": "System billing question",
                    "body": "Hi, I have a question about billing cycle.",
                },
            )
            assert ingest_resp.status_code == 200
            ticket_id = ingest_resp.json()["ticket_id"]

            # 2. Mock generate_structured to raise RuntimeError (429 Quota Exhausted)
            with mock.patch.object(LLMClient, "generate_structured", side_effect=RuntimeError("429 Quota Exhausted")):
                analyze_resp = await client.post(f"/api/v1/tickets/{ticket_id}/analyze")
                assert analyze_resp.status_code == 200
                data = analyze_resp.json()
                assert data["tier"] in ("immediate", "priority", "ai_assisted", "automated")
                assert ("HR4" in data["hard_rule_hits"]) or data["needs_manual_review"] is True

    async def test_drill_hubspot_token_revocation_non_blocking(self, async_db):
        """Simulate HubSpot 401 Unauthorized token revocation."""
        with mock.patch.object(HubSpotClient, "create_or_update_ticket", side_effect=RuntimeError("401 Unauthorized")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "dev-supportflow-api-key-change-me"}) as client:
                resp = await client.post(
                    "/api/v1/messages/ingest",
                    json={
                        "channel": "email",
                        "external_message_id": "test-drill-hs-401",
                        "thread_id": "test-drill-hs-thread",
                        "from_email": "user.hs401@example.com",
                        "from_name": "HS User",
                        "subject": "Testing CRM failure",
                        "body": "Checking if CRM failure blocks ticket intake.",
                    },
                )
                assert resp.status_code == 200
                assert "ticket_id" in resp.json()

    async def test_drill_webhook_replay_idempotency(self, async_db):
        """Simulate duplicate webhook delivery."""
        payload = {
            "channel": "email",
            "external_message_id": "test-drill-replay-unique-999",
            "thread_id": "test-drill-replay-thread",
            "from_email": "replay.user@example.com",
            "from_name": "Replay User",
            "subject": "Replay test",
            "body": "Payload delivered twice.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "dev-supportflow-api-key-change-me"}) as client:
            resp1 = await client.post("/api/v1/messages/ingest", json=payload)
            resp2 = await client.post("/api/v1/messages/ingest", json=payload)

            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert resp1.json()["ticket_id"] == resp2.json()["ticket_id"]
