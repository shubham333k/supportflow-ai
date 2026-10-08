import asyncio
from pathlib import Path
from eval.run_eval import main, run_evaluation

async def run_and_save():
    dev_summary = await run_evaluation("dev")
    test_summary = await run_evaluation("test")
    
    out_path = Path("eval/summary.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=== DEV SPLIT EVALUATION ===\n")
        f.write(f"Total Messages: {dev_summary['total_messages']}\n")
        f.write(f"Intent Accuracy: {dev_summary['intent_accuracy_pct']}%\n")
        f.write(f"Escalation Recall: {dev_summary['escalation_recall_pct']}%\n")
        f.write(f"Escalation Precision: {dev_summary['escalation_precision_pct']}%\n")
        f.write(f"Missed Escalations: {dev_summary['missed_escalations_count']}\n")
        f.write(f"Latency p50/p95: {dev_summary['p50_latency_ms']}ms / {dev_summary['p95_latency_ms']}ms\n\n")
        
        f.write("=== HELD-OUT TEST SPLIT EVALUATION ===\n")
        f.write(f"Total Messages: {test_summary['total_messages']}\n")
        f.write(f"Intent Accuracy: {test_summary['intent_accuracy_pct']}%\n")
        f.write(f"Escalation Recall: {test_summary['escalation_recall_pct']}%\n")
        f.write(f"Escalation Precision: {test_summary['escalation_precision_pct']}%\n")
        f.write(f"Missed Escalations: {test_summary['missed_escalations_count']}\n")
        f.write(f"Latency p50/p95: {test_summary['p50_latency_ms']}ms / {test_summary['p95_latency_ms']}ms\n")

if __name__ == "__main__":
    asyncio.run(run_and_save())
