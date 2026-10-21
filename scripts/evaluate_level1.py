"""Run Level-1 extraction accuracy evaluation from the repository root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.evaluation import evaluate_level1  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data/input")
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=PROJECT_ROOT / "tests/ground_truth",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data/output/evaluation",
    )
    args = parser.parse_args()
    results = evaluate_level1(args.input_dir, args.ground_truth_dir, args.output_dir)
    summary = {
        "overall": results["overall"],
        "by_category": results["by_category"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
