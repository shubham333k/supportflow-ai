import asyncio
import json
from pathlib import Path
from eval.run_eval import run_evaluation

async def main():
    dev_res = await run_evaluation("dev")
    test_res = await run_evaluation("test")
    
    combined = {
        "dev": dev_res,
        "test": test_res
    }
    
    out_file = Path("C:/Users/shubh/Automation Pro/eval_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print("SAVED_EVAL_RESULTS_SUCCESSFULLY")

if __name__ == "__main__":
    asyncio.run(main())
