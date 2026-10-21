"""Run the complete pipeline and score Level-4 only against reviewed truth."""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.extraction import DrawingParser  # noqa: E402
from backend.app.relationships import RelationshipEngine  # noqa: E402
from backend.app.validation import ValidationEngine  # noqa: E402
from backend.app.vision import VisionEngine  # noqa: E402

INPUT = ROOT / "data" / "input"
GROUND_TRUTH = ROOT / "tests" / "relationship_ground_truth"
OUTPUT = ROOT / "data" / "output" / "evaluation"
ACTIONABLE = {"FAIL", "WARNING", "MANUAL_REVIEW"}
CATEGORIES = {
    "Revision": {"REL-REV-001", "REL-REV-002"},
    "BOM": {"REL-BOM-001", "REL-BOM-002", "REL-BOM-003"},
    "Notes": {"REL-NOTE-001"},
    "SCC": {"REL-SCC-001"},
    "Datum-GDT": {"REL-GDT-001", "REL-GDT-002"},
    "Supplier": {"REL-SUP-001", "REL-PART-001"},
    "Document": {"REL-DOC-001"},
}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _load_truth(pdf: Path) -> list[dict[str, Any]] | None:
    path = GROUND_TRUTH / f"{pdf.stem}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("review_status") != "MANUALLY_REVIEWED":
        return None
    return list(payload.get("expectations", []))


def _metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "reviewed_expectations": 0,
            "accuracy": None,
            "precision": None,
            "recall": None,
        }
    correct = sum(row["expected_status"] == row["actual_status"] for row in rows)
    true_positive = sum(
        row["expected_status"] in ACTIONABLE and row["actual_status"] == row["expected_status"]
        for row in rows
    )
    false_positive = sum(
        row["actual_status"] in ACTIONABLE and row["actual_status"] != row["expected_status"]
        for row in rows
    )
    false_negative = sum(
        row["expected_status"] in ACTIONABLE and row["actual_status"] != row["expected_status"]
        for row in rows
    )
    return {
        "reviewed_expectations": len(rows),
        "accuracy": _ratio(correct, len(rows)),
        "precision": _ratio(true_positive, true_positive + false_positive),
        "recall": _ratio(true_positive, true_positive + false_negative),
    }


def evaluate() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    parser = DrawingParser()
    validator = ValidationEngine()
    visual_engine = VisionEngine()
    relationship_engine = RelationshipEngine()
    samples: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    observed_rules: Counter[str] = Counter()

    for pdf in sorted(INPUT.glob("*.pdf")):
        level1_started = time.perf_counter()
        drawing = parser.parse(pdf)
        level1_ms = (time.perf_counter() - level1_started) * 1000
        base_validation = validator.validate(drawing)
        visual = visual_engine.analyze(pdf, drawing)
        validation = validator.validate(drawing, vision_report=visual)
        relationships = relationship_engine.analyze(
            drawing,
            validation_report=validation,
            vision_report=visual,
        )
        result_by_rule: dict[str, list[Any]] = defaultdict(list)
        for finding in relationships.findings:
            observed_rules[finding.relationship_rule_id] += 1
            result_by_rule[finding.relationship_rule_id].append(finding)

        truth = _load_truth(pdf)
        if truth is not None:
            for expected in truth:
                rule_id = str(expected["relationship_rule_id"])
                discriminator = expected.get("finding_id")
                candidates = result_by_rule.get(rule_id, [])
                actual = next(
                    (
                        finding
                        for finding in candidates
                        if discriminator is not None and finding.finding_id == discriminator
                    ),
                    candidates[0] if discriminator is None and len(candidates) == 1 else None,
                )
                rows.append(
                    {
                        "source_filename": pdf.name,
                        "relationship_rule_id": rule_id,
                        "category": next(
                            (name for name, ids in CATEGORIES.items() if rule_id in ids),
                            "Uncatalogued",
                        ),
                        "expected_status": str(expected["expected_status"]),
                        "actual_status": str(actual.status) if actual is not None else "MISSING",
                        "finding_id": actual.finding_id if actual is not None else discriminator,
                        "reviewer_comment": expected.get("reviewer_comment"),
                    }
                )

        status_counts = Counter(str(item.status) for item in relationships.findings)
        timings = {
            "level1_ms": level1_ms,
            "level2_previsual_ms": base_validation.timing.level2_validation_ms,
            "level3_ms": visual.timing.total_time_ms,
            "level2_postvisual_ms": validation.timing.level2_validation_ms,
            "level4_ms": relationships.timing.level4_relationship_ms,
        }
        timings["complete_ms"] = sum(timings.values())
        samples.append(
            {
                "source_filename": pdf.name,
                "pages": len(drawing.pages),
                "relationship_findings": len(relationships.findings),
                "graph_nodes": len(relationships.graph.nodes),
                "graph_edges": len(relationships.graph.edges),
                "correlations": len(relationships.correlations),
                "overall_status": relationships.summary.overall_status,
                "pass": status_counts["PASS"],
                "fail": status_counts["FAIL"],
                "warning": status_counts["WARNING"],
                "manual_review": status_counts["MANUAL_REVIEW"],
                "not_applicable": status_counts["NOT_APPLICABLE"],
                "not_evaluated": status_counts["NOT_EVALUATED"],
                "ground_truth_available": truth is not None,
                **{key: round(value, 3) for key, value in timings.items()},
            }
        )

    category_metrics = {
        category: {
            "catalog_rule_ids": sorted(rule_ids),
            "observed_findings": sum(observed_rules[rule_id] for rule_id in rule_ids),
            **_metric_block([row for row in rows if row["category"] == category]),
        }
        for category, rule_ids in CATEGORIES.items()
    }
    payload = {
        "metrics_policy": (
            "Accuracy metrics include only MANUALLY_REVIEWED Level-4 expectations. "
            "Metrics remain null where independent ground truth is absent."
        ),
        "metrics": _metric_block(rows),
        "catalog": {
            "implemented_rule_ids": sorted(
                {rule for rules in CATEGORIES.values() for rule in rules}
            ),
            "implemented_rule_count": len(
                {rule for rules in CATEGORIES.values() for rule in rules}
            ),
            "observed_rule_ids": sorted(observed_rules),
        },
        "category_metrics": category_metrics,
        "samples": samples,
        "reviewed_results": rows,
    }
    (OUTPUT / "level4_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    sample_fields = list(samples[0]) if samples else ["source_filename"]
    with (OUTPUT / "level4_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=sample_fields)
        writer.writeheader()
        writer.writerows(samples)
    return payload


def main() -> int:
    print(json.dumps(evaluate(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
