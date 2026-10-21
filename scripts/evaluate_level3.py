"""Evaluate Level-3 detections only where independent visual ground truth exists."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.extraction import DrawingParser  # noqa: E402
from backend.app.validation import ValidationEngine  # noqa: E402
from backend.app.vision import VisionEngine  # noqa: E402
from backend.app.vision.spatial import intersection_over_union  # noqa: E402

INPUT = ROOT / "data" / "input"
GROUND_TRUTH = ROOT / "tests" / "vision_ground_truth"
OUTPUT = ROOT / "data" / "output" / "evaluation"
VISION_OUTPUT = ROOT / "data" / "output" / "vision"
CLASSES = [
    "REVISION_TRIANGLE",
    "BOM_BALLOON",
    "SCC_SYMBOL",
    "DATUM_SYMBOL",
    "GDT_FRAME",
    "FLAG_NOTE",
]


def _load_truth(pdf: Path) -> list[dict[str, Any]] | None:
    path = GROUND_TRUTH / f"{pdf.stem}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("review_status") != "MANUALLY_REVIEWED":
        return None
    return list(payload.get("objects", []))


def _metrics(predictions: list[dict[str, Any]], truth: list[dict[str, Any]]) -> dict[str, Any]:
    matched_predictions: set[int] = set()
    matched_truth: set[int] = set()
    ious: list[float] = []
    text_correct = 0
    text_total = 0
    for truth_index, expected in enumerate(truth):
        best: tuple[float, int] | None = None
        for prediction_index, prediction in enumerate(predictions):
            if prediction_index in matched_predictions:
                continue
            if prediction["page_number"] != expected["page_number"]:
                continue
            score = intersection_over_union(
                tuple(prediction["bounding_box"]), tuple(expected["bounding_box"])
            )
            if best is None or score > best[0]:
                best = (score, prediction_index)
        if best is None or best[0] < 0.5:
            continue
        matched_truth.add(truth_index)
        matched_predictions.add(best[1])
        ious.append(best[0])
        expected_text = expected.get("text")
        if expected_text is not None:
            text_total += 1
            actual = predictions[best[1]].get("normalized_text")
            text_correct += str(actual or "").casefold() == str(expected_text).casefold()
    true_positive = len(matched_truth)
    false_positive = len(predictions) - true_positive
    false_negative = len(truth) - true_positive
    precision = (
        true_positive / (true_positive + false_positive)
        if predictions
        else (1.0 if not truth else 0.0)
    )
    recall = true_positive / len(truth) if truth else (1.0 if not predictions else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "grounded_objects": len(truth),
        "predicted_objects": len(predictions),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_iou": sum(ious) / len(ious) if ious else None,
        "text_recognition_accuracy": text_correct / text_total if text_total else None,
        "object_count_accuracy": max(
            0.0, 1 - abs(len(predictions) - len(truth)) / max(len(truth), 1)
        ),
    }


def evaluate() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    VISION_OUTPUT.mkdir(parents=True, exist_ok=True)
    engine = VisionEngine()
    samples: list[dict[str, Any]] = []
    grounded_predictions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grounded_truth: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pdf in sorted(INPUT.glob("*.pdf")):
        drawing = DrawingParser().parse(pdf)
        report = engine.analyze(
            pdf,
            drawing,
            debug_directory=ROOT / "data" / "output" / "vision_debug" / pdf.stem,
        )
        (VISION_OUTPUT / f"{pdf.stem}.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        truth = _load_truth(pdf)
        validator = ValidationEngine()
        before_validation = validator.validate(drawing)
        after_validation = validator.validate(drawing, vision_report=report)
        before_by_id = {item.rule_id: item for item in before_validation.results}
        changed_rules = [
            {
                "rule_id": item.rule_id,
                "before": before_by_id[item.rule_id].status,
                "after": item.status,
            }
            for item in after_validation.results
            if before_by_id[item.rule_id].status != item.status
        ]
        if truth is not None:
            for object_type in CLASSES:
                grounded_predictions[object_type].extend(
                    item.model_dump(mode="json")
                    for item in report.objects
                    if str(item.object_type) == object_type
                )
                grounded_truth[object_type].extend(
                    item for item in truth if item["object_type"] == object_type
                )
        samples.append(
            {
                "source_filename": pdf.name,
                "pages_processed": report.summary.pages_processed,
                "visual_objects": report.summary.objects_detected,
                "objects_by_type": report.summary.objects_by_type,
                "low_confidence": report.summary.low_confidence_count,
                "ocr_regions": report.summary.objects_by_type.get("SUPPLIER_RASTER_TEXT", 0),
                "level3_time_ms": report.timing.total_time_ms,
                "ground_truth_available": truth is not None,
                "validation_before": before_validation.summary.model_dump(mode="json"),
                "validation_after": after_validation.summary.model_dump(mode="json"),
                "validation_status_changes": changed_rules,
            }
        )
    class_metrics = {
        object_type: (
            _metrics(grounded_predictions[object_type], grounded_truth[object_type])
            if grounded_truth[object_type]
            else {
                "grounded_objects": 0,
                "precision": None,
                "recall": None,
                "f1": None,
                "mean_iou": None,
                "text_recognition_accuracy": None,
                "object_count_accuracy": None,
            }
        )
        for object_type in CLASSES
    }
    payload = {
        "metrics_policy": "Metrics are null for classes without manually reviewed ground truth.",
        "class_metrics": class_metrics,
        "samples": samples,
    }
    (OUTPUT / "level3_results.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    with (OUTPUT / "level3_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "source_filename",
                "pages_processed",
                "visual_objects",
                "low_confidence",
                "ocr_regions",
                "level3_time_ms",
                "ground_truth_available",
            ],
        )
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in samples)
    return payload


def main() -> int:
    print(json.dumps(evaluate(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
