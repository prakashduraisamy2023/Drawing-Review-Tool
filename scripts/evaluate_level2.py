"""Evaluate Level-2 statuses only against manually maintained rule ground truth."""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.extraction.drawing_parser import DrawingParser  # noqa: E402
from backend.app.validation import ValidationEngine  # noqa: E402

ACTIONABLE = {"FAIL", "WARNING"}


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def main() -> int:
    truth_root = ROOT / "tests" / "validation_ground_truth"
    input_root = ROOT / "data" / "input"
    output_root = ROOT / "data" / "output" / "evaluation"
    output_root.mkdir(parents=True, exist_ok=True)

    engine = ValidationEngine()
    parser = DrawingParser()
    metadata = {item.rule_id: item for item in engine.registry.metadata()}
    rows: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    category_grounded: dict[str, set[str]] = defaultdict(set)

    for truth_path in sorted(truth_root.glob("*.json")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        source = input_root / truth["source_filename"]
        level1_started = time.perf_counter()
        drawing = parser.parse(source)
        level1_ms = (time.perf_counter() - level1_started) * 1000
        report = engine.validate(drawing)
        result_map = {item.rule_id: item for item in report.results}
        for expected in truth["expectations"]:
            rule_id = expected["rule_id"]
            actual = result_map[rule_id]
            category = metadata[rule_id].category
            category_grounded[category].add(rule_id)
            rows.append(
                {
                    "source_filename": source.name,
                    "rule_id": rule_id,
                    "category": category,
                    "expected_status": expected["expected_status"],
                    "actual_status": actual.status,
                    "correct": expected["expected_status"] == actual.status,
                    "expected_actual_value": expected.get("expected_actual_value"),
                    "expected_message_class": expected.get("expected_message_class"),
                    "reviewer_comment": expected.get("reviewer_comment"),
                }
            )
        samples.append(
            {
                "source_filename": source.name,
                **report.summary.model_dump(mode="json"),
                "level2_validation_ms": round(report.timing.level2_validation_ms, 3),
                "level1_processing_ms": round(level1_ms, 3),
                "total_processing_ms": round(level1_ms + report.timing.level2_validation_ms, 3),
            }
        )

    correct = sum(bool(row["correct"]) for row in rows)
    true_positive = sum(
        row["expected_status"] in ACTIONABLE and row["actual_status"] == row["expected_status"]
        for row in rows
    )
    false_positive = sum(
        row["actual_status"] in ACTIONABLE and row["expected_status"] != row["actual_status"]
        for row in rows
    )
    false_negative = sum(
        row["expected_status"] in ACTIONABLE and row["actual_status"] != row["expected_status"]
        for row in rows
    )
    category_catalog: Counter[str] = Counter(item.category for item in metadata.values())
    categories = {
        category: {
            "catalog_rules": category_catalog[category],
            "grounded_rule_ids": len(category_grounded[category]),
            "ground_truth_coverage": safe_ratio(
                len(category_grounded[category]), category_catalog[category]
            ),
        }
        for category in sorted(category_catalog)
    }
    automation = Counter(item.automation_status for item in metadata.values())
    payload = {
        "ground_truth_scope": (
            "Metrics include only manually maintained expectations. Ungrounded rule "
            "outputs are excluded rather than assumed correct."
        ),
        "metrics": {
            "expectations": len(rows),
            "correct": correct,
            "accuracy": safe_ratio(correct, len(rows)),
            "precision": safe_ratio(true_positive, true_positive + false_positive),
            "recall": safe_ratio(true_positive, true_positive + false_negative),
        },
        "rule_coverage": {
            "implemented": len(metadata),
            "automated": automation["AUTOMATED"],
            "partially_automated": automation["PARTIALLY_AUTOMATED"],
            "manual": automation["MANUAL"],
            "not_implemented": automation["NOT_IMPLEMENTED"],
            "grounded_rule_ids": len({str(row["rule_id"]) for row in rows}),
        },
        "category_coverage": categories,
        "samples": samples,
        "results": rows,
    }
    (output_root / "level2_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    with (output_root / "level2_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                key: payload[key]
                for key in ("metrics", "rule_coverage", "category_coverage", "samples")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
