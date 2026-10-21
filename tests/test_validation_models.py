import pytest
from pydantic import ValidationError

from backend.app.validation.models import ValidationEvidence, ValidationSummary


def test_validation_evidence_validates_confidence_and_bbox():
    evidence = ValidationEvidence(
        page_number=1,
        bounding_box=(1, 2, 3, 4),
        source_field="drawing_number",
        extracted_value="12345678",
        extraction_method="coordinate_text",
        confidence=0.95,
    )
    assert evidence.page_number == 1
    with pytest.raises(ValidationError):
        ValidationEvidence(source_field="x", confidence=1.1)


def test_validation_summary_is_strict_and_serializable():
    summary = ValidationSummary(
        total_rules=1,
        passed=1,
        failed=0,
        warnings=0,
        manual_review=0,
        not_applicable=0,
        not_evaluated=0,
        critical_failures=0,
        high_failures=0,
        overall_status="PASS",
    )
    assert summary.model_dump(mode="json")["overall_status"] == "PASS"
