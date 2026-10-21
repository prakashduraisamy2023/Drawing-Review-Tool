from pathlib import Path

import pytest

from backend.app.extraction.drawing_parser import DrawingParser
from backend.app.models.drawing import (
    DrawingDocument,
    DrawingPage,
    ExtractedField,
    ExtractionMethod,
    TitleBlock,
)
from backend.app.validation import ValidationEngine
from backend.app.validation.context import ValidationContext
from backend.app.validation.models import RuleMetadata
from backend.app.validation.registry import RuleRegistry
from backend.app.validation.rules.base import ValidationRule
from backend.app.validation.rules.declarative import DeclarativeRule


def field(value, confidence=0.95, page=1):
    if value is None:
        return ExtractedField()
    return ExtractedField(
        value=value,
        page_number=page,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=(1, 2, 3, 4),
        raw_text=str(value),
    )


def document(*, number="12345678", confidence=0.95, document_type="STANDARD_DRAWING"):
    title = TitleBlock(
        drawing_number=field(number, confidence),
        revision=field("A"),
        units=field("MM"),
        scale=field("1:1"),
        drawing_size=field("B"),
        sheet_number=field(1),
        sheet_count=field(1),
    )
    return DrawingDocument(
        source_filename=field("synthetic.pdf"),
        page_count=field(1),
        document_type=field(document_type),
        drawing_number=title.drawing_number,
        revision=title.revision,
        units=title.units,
        scale=title.scale,
        drawing_size=title.drawing_size,
        sheet_number=title.sheet_number,
        total_sheets=title.sheet_count,
        pages=[DrawingPage(page_number=1, title_block=title)],
    )


def metadata(rule_id="TEST-001", applicability="always"):
    return RuleMetadata(
        rule_id=rule_id,
        name="Synthetic rule",
        category="Test",
        description="Synthetic deterministic rule",
        source_requirement="Synthetic requirement",
        automation_type="RULE_BASED",
        severity="HIGH",
        applicability=applicability,
        version="1.0.0",
        automation_status="AUTOMATED",
    )


@pytest.mark.parametrize(
    ("value", "confidence", "expected"),
    [
        ("12345678", 0.95, "PASS"),
        (None, 0.0, "FAIL"),
        ("12345678", 0.50, "MANUAL_REVIEW"),
    ],
)
def test_presence_rule_pass_missing_and_low_confidence(value, confidence, expected):
    rule = DeclarativeRule(metadata(), "presence", {"field": "drawing_number"})
    context = ValidationContext(
        document(number=value, confidence=confidence), {"minimum_confidence": 0.75, "rules": {}}
    )
    assert rule.validate(context).status == expected


def test_consistency_rule_pass_fail_missing_and_ambiguous():
    rule = DeclarativeRule(metadata(), "consistency", {"field": "revision"})
    base = document()
    base.pages = [
        DrawingPage(page_number=1, title_block=TitleBlock(revision=field("A", page=1))),
        DrawingPage(page_number=2, title_block=TitleBlock(revision=field("A", page=2))),
    ]
    config = {"minimum_confidence": 0.75, "rules": {}}
    assert rule.validate(ValidationContext(base, config)).status == "PASS"
    base.pages[1].title_block.revision = field("B", page=2)
    assert rule.validate(ValidationContext(base, config)).status == "FAIL"
    base.pages[1].title_block.revision = field(None)
    assert rule.validate(ValidationContext(base, config)).status == "NOT_EVALUATED"
    base.pages[1].title_block.revision = field("B", confidence=0.50, page=2)
    assert rule.validate(ValidationContext(base, config)).status == "NOT_EVALUATED"


def test_supplier_rule_is_not_applicable_to_standard_drawing():
    engine = ValidationEngine()
    result = next(item for item in engine.validate(document()).results if item.rule_id == "SUP-001")
    assert result.status == "NOT_APPLICABLE"


class BrokenRule(ValidationRule):
    def validate(self, context):
        del context
        raise RuntimeError("synthetic failure")


def test_rule_failure_isolated_as_not_evaluated():
    registry = RuleRegistry()
    registry.register(BrokenRule(metadata()))
    report = ValidationEngine(
        configuration={"rule_set_version": "1", "rules": {}},
        registry=registry,
    ).validate(document())
    assert report.results[0].status == "NOT_EVALUATED"
    assert report.summary.not_evaluated == 1


def test_all_catalog_rules_return_structured_result_for_missing_evidence():
    report = ValidationEngine().validate(DrawingDocument())
    assert len(report.results) == 108
    assert len({result.rule_id for result in report.results}) == 108
    assert all(
        result.message and result.expected_condition and result.rule_version
        for result in report.results
    )


@pytest.mark.parametrize(
    "filename",
    [
        "47789413_C_watermarked.pdf",
        "47789460_B_watermarked.pdf",
        "47789660_A_watermarked.pdf",
    ],
)
def test_all_samples_run_level1_to_level2_without_reparsing_in_validator(filename):
    source = Path(__file__).resolve().parents[1] / "data" / "input" / filename
    drawing = DrawingParser().parse(source)
    report = ValidationEngine().validate(drawing)
    assert report.source_filename == filename
    assert report.summary.total_rules == 108
    assert report.results
    assert report.timing.level2_validation_ms >= 0
    assert report.model_dump_json()
