import sys
from pathlib import Path

for candidate in (
    Path(__file__).resolve().parents[1] / "libs" / "fastclass-shared",
    Path(__file__).resolve().parents[2] / "libs" / "fastclass-shared",
):
    if candidate.exists():
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        break
