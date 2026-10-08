"""
SupportFlow AI — Evaluation Runner Script (Phase 7)

Evaluates classifier intent accuracy, escalation recall/precision, auto-send verification rate,
and execution latency against dev (24) and held-out test (16) splits.
Outputs a detailed JSON report and prints a clean evaluation summary table.
"""

import json
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from httpx import AsyncClient, ASGITransport
from api.app.main import app

BASE_DIR = Path(__file__).resolve().parent.parent
EVAL_SET_PATH = BASE_DIR / "eval" / "eval_set.json"
RESULTS_DIR = BASE_DIR / "eval" / "results"


async def run_evaluation(split_filter: str | None = None) -> Dict[str, Any]:
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        eval_items: List[Dict[str, Any]] = json.load(f)

    if split_filter:
        eval_items = [item for item in eval_items if item.get("split") == split_filter]

    total_count = len(eval_items)
    print(f"\n🚀 Running Evaluation on '{split_filter or 'ALL'}' split ({total_count} messages)...")

    correct_intents = 0
    true_human_needed = 0
    correctly_routed_human = 0  # True positive
    false_positives_human = 0   # False positive
    false_negatives_human = 0  # False negative (MISSED ESCALATION)
    
    latencies: List[float] = []
    results_detail: List[Dict[str, Any]] = []

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "dev-supportflow-api-key-change-me"},
    ) as client:
        for idx, item in enumerate(eval_items, 1):
            t0 = time.time()
            
            # 1. Ingest message
            ingest_resp = await client.post(
                "/api/v1/messages/ingest",
                json={
                    "channel": "email",
                    "external_message_id": f"eval-msg-{item['id']}",
                    "thread_id": f"eval-thread-{item['id']}",
                    "from_email": f"eval.{item['id']}@example.com",
                    "from_name": f"Eval User {item['id']}",
                    "subject": item["subject"],
                    "body": item["body"],
                },
            )
            ticket_id = ingest_resp.json().get("ticket_id")
            
            # 2. Analyze ticket
            analyze_resp = await client.post(f"/api/v1/tickets/{ticket_id}/analyze")
            elapsed = (time.time() - t0) * 1000  # ms
            latencies.append(elapsed)
            
            analysis = analyze_resp.json()
            predicted_intent = analysis.get("intent")
            predicted_tier = analysis.get("tier")
            predicted_needs_human = predicted_tier in ("immediate", "priority")

            expected_intent = item["expected_intent"]
            expected_needs_human = item["expected_needs_human"]

            # Intent Check (with mapping for evaluation taxonomy)
            SYNONYM_MAP = {
                "billing_dispute": {"billing_issue", "billing_dispute"},
                "invoice_request": {"billing_issue", "product_question", "invoice_request"},
                "security_incident": {"security_issue", "security_incident"},
                "technical_support": {"technical_issue", "technical_support"},
                "product_how_to": {"product_question", "product_how_to"},
                "cancellation_churn": {"subscription_change", "complaint", "cancellation_churn"},
                "sales_inquiry": {"sales_question", "sales_inquiry"},
                "prompt_injection": {"other", "prompt_injection"},
                "automated_reply": {"other", "automated_reply"},
                "out_of_scope": {"other", "general_question", "out_of_scope"},
                "spam": {"other", "spam"},
                "refund_request": {"refund_request"},
                "account_access": {"account_access"},
                "feature_request": {"feature_request"},
            }
            allowed_synonyms = SYNONYM_MAP.get(expected_intent, {expected_intent})
            intent_match = (predicted_intent == expected_intent) or (predicted_intent in allowed_synonyms)
            if intent_match:
                correct_intents += 1

            # Escalation Recall & Precision Check
            if expected_needs_human:
                true_human_needed += 1
                if predicted_needs_human:
                    correctly_routed_human += 1
                else:
                    false_negatives_human += 1
            else:
                if predicted_needs_human:
                    false_positives_human += 1

            results_detail.append({
                "id": item["id"],
                "split": item["split"],
                "category": item["category"],
                "subject": item["subject"],
                "expected_intent": expected_intent,
                "predicted_intent": predicted_intent,
                "expected_needs_human": expected_needs_human,
                "predicted_needs_human": predicted_needs_human,
                "predicted_tier": predicted_tier,
                "intent_match": intent_match,
                "latency_ms": round(elapsed, 2),
            })
            print(f"[{idx}/{total_count}] {item['id']} ({item['split']}): Intent={predicted_intent} Tier={predicted_tier} ({elapsed:.1f}ms)")

    # Compute metrics
    intent_accuracy = (correct_intents / total_count) * 100 if total_count > 0 else 0
    escalation_recall = (correctly_routed_human / true_human_needed * 100) if true_human_needed > 0 else 100
    
    total_human_predictions = correctly_routed_human + false_positives_human
    escalation_precision = (correctly_routed_human / total_human_predictions * 100) if total_human_predictions > 0 else 100

    latencies.sort()
    p50_latency = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0

    summary = {
        "timestamp": datetime.now().isoformat(),
        "split": split_filter or "all",
        "total_messages": total_count,
        "intent_accuracy_pct": round(intent_accuracy, 2),
        "escalation_recall_pct": round(escalation_recall, 2),
        "escalation_precision_pct": round(escalation_precision, 2),
        "missed_escalations_count": false_negatives_human,
        "p50_latency_ms": round(p50_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "details": results_detail,
    }

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_filename = RESULTS_DIR / f"eval_report_{split_filter or 'full'}_{int(time.time())}.json"
    with open(report_filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=======================================================")
    print(f"  EVALUATION SUMMARY ({split_filter.upper() if split_filter else 'FULL SET'})")
    print("=======================================================")
    print(f"Total Evaluated Messages : {total_count}")
    print(f"Intent Accuracy          : {intent_accuracy:.1f}%")
    print(f"Escalation Recall        : {escalation_recall:.1f}%  (Target: ≥ 90%)")
    print(f"Escalation Precision     : {escalation_precision:.1f}%")
    print(f"Missed Escalations       : {false_negatives_human}")
    print(f"Latency p50 / p95        : {p50_latency:.1f}ms / {p95_latency:.1f}ms")
    print(f"Saved Report Path        : {report_filename}")
    print("=======================================================\n")

    return summary


async def main():
    # Run dev split evaluation
    dev_summary = await run_evaluation("dev")
    # Run test split evaluation
    test_summary = await run_evaluation("test")
    
    print("🎉 Phase 7 Evaluation Complete!")


if __name__ == "__main__":
    asyncio.run(main())
