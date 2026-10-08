"""Run pytest and write results to a file."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = ROOT / "eval" / "results" / "pytest_run.txt"
RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

result = subprocess.run(
    [sys.executable, "-m", "pytest", "api/tests/unit/", "-v", "--tb=short"],
    capture_output=True,
    text=True,
    cwd=str(ROOT),
)

output = result.stdout + result.stderr
RESULTS_FILE.write_text(output, encoding="utf-8")

# Print summary lines to stdout so we can see it in the tool output
lines = output.splitlines()
for line in lines:
    print(line)

print(f"\nReturn code: {result.returncode}")
print(f"Full output written to: {RESULTS_FILE}")
