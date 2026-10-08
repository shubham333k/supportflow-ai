import pytest
from eval.run_eval import run_evaluation


@pytest.mark.asyncio
class TestEvaluationBenchmark:
    async def test_dev_split_benchmark(self, async_db):
        summary = await run_evaluation("dev")
        assert summary["total_messages"] == 24
        assert summary["intent_accuracy_pct"] >= 80.0
        assert summary["escalation_recall_pct"] >= 90.0  # Pass bar: ≥ 90% recall
        assert summary["missed_escalations_count"] == 0

    async def test_heldout_test_split_benchmark(self, async_db):
        summary = await run_evaluation("test")
        assert summary["total_messages"] == 16
        assert summary["intent_accuracy_pct"] >= 80.0
        assert summary["escalation_recall_pct"] >= 90.0  # Pass bar: ≥ 90% recall
        assert summary["missed_escalations_count"] == 0
