"""
Self-contained smoke test that writes results to a file.
Avoids all shell escaping issues by writing to a known path.
"""
import sys
import asyncio
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "eval" / "smoke_results.txt"
OUT.parent.mkdir(parents=True, exist_ok=True)

lines = []
passed = 0
failed = 0


def run_test(name, fn):
    global passed, failed
    try:
        if asyncio.iscoroutinefunction(fn):
            asyncio.run(fn())
        else:
            fn()
        lines.append(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        lines.append(f"  FAIL: {name}")
        lines.append(f"        {e}")
        lines.append(traceback.format_exc())
        failed += 1


def test_hmac():
    from api.app.core.security import generate_hmac_signature, verify_hmac_signature
    secret = "my-secret"
    body = '{"event":"test"}'
    sig = generate_hmac_signature(body, secret)
    assert len(sig) == 64
    assert verify_hmac_signature(body, sig, secret) is True
    assert verify_hmac_signature(body + "x", sig, secret) is False

run_test("HMAC signature generation & verification", test_hmac)


def test_rate_limiter():
    from api.app.core.security import RateLimiter
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    key = "test_user"
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is False

run_test("Rate limiter sliding window", test_rate_limiter)


def test_hubspot_mock():
    from api.app.integrations.hubspot import HubSpotClient
    client_empty = HubSpotClient(access_token="")
    assert client_empty.mock_mode is True
    client_placeholder = HubSpotClient(access_token="mock-token")
    assert client_placeholder.mock_mode is True

run_test("HubSpotClient mock mode detection", test_hubspot_mock)


def test_escalation():
    from api.app.services.escalation import score_ticket
    score_obj = score_ticket(
        urgency_level="high",
        sentiment="very_negative",
        customer_tier="enterprise",
        issue_severity="critical",
        prior_unresolved_count=2,
        sla_risk=True,
        threat_detected=True,
    )
    assert score_obj.total_score >= 80, f"Expected >= 80, got {score_obj.total_score}"
    assert score_obj.priority_tier == "immediate"

run_test("Escalation scoring (scenario A -> immediate)", test_escalation)


def test_loop_guard():
    from api.app.services.loop_guard import is_auto_reply
    assert is_auto_reply("noreply@example.com", "Test", "Test body") is True
    assert is_auto_reply("customer@biz.com", "Invoice", "I need help") is False

run_test("Loop guard auto-reply detection", test_loop_guard)


def test_eval_set():
    import json
    data = json.loads((ROOT / "eval" / "eval_set.json").read_text(encoding="utf-8"))
    assert len(data) == 40
    dev = [d for d in data if d["split"] == "dev"]
    test = [d for d in data if d["split"] == "test"]
    assert len(dev) == 24
    assert len(test) == 16

run_test("Evaluation dataset integrity (40 msgs, 24/16 split)", test_eval_set)


summary = f"\n{'='*55}\n  Results: {passed} passed, {failed} failed\n{'='*55}\n"
lines.append(summary)
print(summary)

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if failed == 0 else 1)
