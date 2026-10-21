"""Run the same mapper/reducer pair locally for a smoke test (not distributed)."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sample/socialpulse_sample.csv")
with source.open("r", encoding="utf-8-sig") as stream:
    mapped = subprocess.run(
        [sys.executable, str(root / "mapper.py")],
        stdin=stream, capture_output=True, text=True, check=True,
    )
reduced = subprocess.run(
    [sys.executable, str(root / "reducer.py")],
    input="".join(sorted(mapped.stdout.splitlines(keepends=True))),
    capture_output=True, text=True, check=True,
)
sys.stdout.write(reduced.stdout)

