import json
from pathlib import Path

from backend.app.evaluation.engine import Level1Evaluator
from backend.app.models.drawing import DrawingDocument, ExtractedField, ExtractionMethod


def metadata(value):
    return ExtractedField(
        value=value,
        confidence=1.0,
        extraction_method=ExtractionMethod.PDF_METADATA,
    )


class StubParser:
    def parse(self, _path: Path) -> DrawingDocument:
        return DrawingDocument(
            source_filename=metadata("sample.pdf"),
            page_count=metadata(1),
            drawing_number=metadata("ACTUAL"),
        )


def test_evaluation_calculates_accuracy_coverage_and_error_taxonomy(tmp_path: Path):
    input_dir = tmp_path / "input"
    truth_dir = tmp_path / "truth"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    truth_dir.mkdir()
    (input_dir / "sample.pdf").write_bytes(b"placeholder")
    truth = {
        "schema_version": 1,
        "source_filename": "sample.pdf",
        "categories": {
            "Title Block": {
                "fields": {
                    "page_count.value": 1,
                    "drawing_number.value": "EXPECTED",
                    "revision.value": "A",
                },
                "records": [],
            },
            "Notes": {"fields": {}, "records": []},
        },
        "expected_null": ["drawing_size.value"],
    }
    (truth_dir / "sample.json").write_text(json.dumps(truth), encoding="utf-8")

    evaluator = Level1Evaluator(parser=StubParser())
    results = evaluator.evaluate(input_dir, truth_dir)
    json_path, csv_path = evaluator.write_results(results, output_dir)

    assert results["overall"]["correct_count"] == 1
    assert results["overall"]["incorrect_count"] == 1
    assert results["overall"]["missing_count"] == 1
    assert results["overall"]["accuracy"] == 0.3333
    assert results["overall"]["coverage"] == 0.6667
    assert results["by_category"]["Notes"]["accuracy"] is None
    errors = results["by_drawing"][0]["errors"]
    assert {error["error_category"] for error in errors} == {
        "E02 WRONG_ANCHOR",
        "E04 READING_ORDER",
    }
    assert json_path.is_file()
    assert csv_path.is_file()
