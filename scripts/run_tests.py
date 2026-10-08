import pytest
import sys
from pathlib import Path

if __name__ == "__main__":
    log_file = Path(__file__).resolve().parent.parent / "test_results.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("Starting Pytest...\n")
    ret = pytest.main(["api/tests/unit/", "-v", f"--logfile={log_file}"])
    sys.exit(ret)
