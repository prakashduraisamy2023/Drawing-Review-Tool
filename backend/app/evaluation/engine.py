"""Compare parser output with independently maintained manual ground truth."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from backend.app.evaluation.models import ErrorCategory
from backend.app.extraction.drawing_parser import DrawingParser

PATH_TOKEN = re.compile(r"(?P<name>[^.\[]+)(?:\[(?P<index>\d+)\])?")


def _value_at(payload: object, path: str) -> object:
    current = payload
    for raw_token in path.split("."):
        match = PATH_TOKEN.fullmatch(raw_token)
        if match is None or not isinstance(current, dict):
            return None
        current = current.get(match.group("name"))
        if match.group("index") is not None:
            if not isinstance(current, list):
                return None
            index = int(match.group("index"))
            if index >= len(current):
                return None
            current = current[index]
    return current


def _equal(expected: object, actual: object) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return re.sub(r"\s+", " ", actual).strip() == re.sub(r"\s+", " ", expected).strip()
    return actual == expected


def _error_category(category: str, path: str, actual: object) -> ErrorCategory:
    if actual is None:
        return ErrorCategory.WRONG_ANCHOR
    if category in {"BOM", "Part Lists", "Service Parts"}:
        return ErrorCategory.TABLE_ROW_ASSOCIATION
    if category == "Notes":
        return ErrorCategory.MULTILINE_NOTE_RECONSTRUCTION
    if category == "Supplier Information":
        return ErrorCategory.SUPPLIER_WRAPPER_RASTER_CONFUSION
    if path.endswith("scale.value"):
        return ErrorCategory.LOCAL_SCALE_CONFUSION
    return ErrorCategory.READING_ORDER


def _metric(correct: int, incorrect: int, missing: int, false: int = 0) -> dict[str, object]:
    expected = correct + incorrect + missing
    covered = correct + incorrect
    return {
        "expected_count": expected,
        "correct_count": correct,
        "incorrect_count": incorrect,
        "missing_count": missing,
        "false_extraction_count": false,
        "accuracy": round(correct / expected, 4) if expected else None,
        "coverage": round(covered / expected, 4) if expected else None,
    }


class Level1Evaluator:
    """Run production extraction and score only manually entered expectations."""

    def __init__(self, parser: DrawingParser | None = None) -> None:
        self.parser = parser or DrawingParser()

    def evaluate(self, input_dir: Path, ground_truth_dir: Path) -> dict[str, object]:
        drawings: list[dict[str, object]] = []
        field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        category_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        overall = [0, 0, 0, 0]
        detail_rows: list[dict[str, object]] = []

        for truth_path in sorted(ground_truth_dir.glob("*.json")):
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            source_filename = truth["source_filename"]
            pdf_path = input_dir / source_filename
            started = perf_counter()
            document = self.parser.parse(pdf_path)
            elapsed = perf_counter() - started
            payload = document.model_dump(mode="json")
            drawing_counts = [0, 0, 0, 0]
            errors: list[dict[str, object]] = []

            for category, category_data in truth.get("categories", {}).items():
                category_counts[category]
                for path, expected in category_data.get("fields", {}).items():
                    actual = _value_at(payload, path)
                    if actual is None:
                        state = "missing"
                        count_index = 2
                    elif _equal(expected, actual):
                        state = "correct"
                        count_index = 0
                    else:
                        state = "incorrect"
                        count_index = 1
                    drawing_counts[count_index] += 1
                    overall[count_index] += 1
                    category_counts[category][count_index] += 1
                    field_counts[path][count_index] += 1
                    error_code = None
                    if state != "correct":
                        error_code = str(_error_category(category, path, actual))
                        errors.append(
                            {
                                "path": path,
                                "category": category,
                                "expected": expected,
                                "actual": actual,
                                "state": state,
                                "error_category": error_code,
                            }
                        )
                    detail_rows.append(
                        {
                            "drawing": source_filename,
                            "category": category,
                            "field": path,
                            "expected": expected,
                            "actual": actual,
                            "state": state,
                            "error_category": error_code,
                        }
                    )

            for path in truth.get("expected_null", []):
                actual = _value_at(payload, path)
                if actual is None:
                    continue
                drawing_counts[3] += 1
                overall[3] += 1
                field_counts[path][3] += 1
                error_code = str(ErrorCategory.MULTIPLE_CANDIDATES)
                errors.append(
                    {
                        "path": path,
                        "expected": None,
                        "actual": actual,
                        "state": "false_extraction",
                        "error_category": error_code,
                    }
                )
                detail_rows.append(
                    {
                        "drawing": source_filename,
                        "category": "Expected null",
                        "field": path,
                        "expected": None,
                        "actual": actual,
                        "state": "false_extraction",
                        "error_category": error_code,
                    }
                )

            drawings.append(
                {
                    "source_filename": source_filename,
                    "metrics": _metric(*drawing_counts),
                    "processing_time_seconds": round(elapsed, 3),
                    "warning_count": len(document.extraction_warnings),
                    "processing_state": document.level1_summary.processing_state
                    if document.level1_summary
                    else "FAILED",
                    "errors": errors,
                }
            )

        return {
            "schema_version": 1,
            "metric_definitions": {
                "accuracy": "correct expected fields / total expected fields",
                "coverage": "non-null extracted expected fields / total expected fields",
            },
            "overall": _metric(*overall),
            "by_drawing": drawings,
            "by_category": {
                name: _metric(*counts) for name, counts in sorted(category_counts.items())
            },
            "by_field": {name: _metric(*counts) for name, counts in sorted(field_counts.items())},
            "detail_rows": detail_rows,
        }

    @staticmethod
    def write_results(results: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "level1_results.json"
        csv_path = output_dir / "level1_results.csv"
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        columns = [
            "drawing",
            "category",
            "field",
            "expected",
            "actual",
            "state",
            "error_category",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(results["detail_rows"])
        return json_path, csv_path


def evaluate_level1(
    input_dir: Path,
    ground_truth_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    evaluator = Level1Evaluator()
    results = evaluator.evaluate(input_dir, ground_truth_dir)
    evaluator.write_results(results, output_dir)
    return results
