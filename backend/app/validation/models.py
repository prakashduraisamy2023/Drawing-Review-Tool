"""Pydantic contracts for deterministic Level-2 validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.drawing import BoundingBox
from backend.app.validation.severity import (
    AutomationType,
    OverallStatus,
    ValidationSeverity,
    ValidationStatus,
)


class ValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ValidationEvidence(ValidationModel):
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    source_field: str
    extracted_value: object | None = None
    raw_text: str | None = None
    extraction_method: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RuleMetadata(ValidationModel):
    rule_id: str
    name: str
    category: str
    description: str
    source_requirement: str
    automation_type: AutomationType
    severity: ValidationSeverity
    applicability: str
    version: str
    automation_status: str
    dependencies: list[str] = Field(default_factory=list)


class ValidationResult(ValidationModel):
    rule_id: str
    rule_name: str
    rule_category: str
    rule_description: str
    source_requirement: str
    status: ValidationStatus
    severity: ValidationSeverity
    automation_type: AutomationType
    expected_condition: str
    actual_condition: str
    message: str
    recommendation: str
    evidence: list[ValidationEvidence] = Field(default_factory=list)
    related_fields: list[str] = Field(default_factory=list)
    rule_version: str
    execution_time_ms: float = Field(ge=0.0)


class ValidationSummary(ValidationModel):
    total_rules: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    warnings: int = Field(ge=0)
    manual_review: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    not_evaluated: int = Field(ge=0)
    critical_failures: int = Field(ge=0)
    high_failures: int = Field(ge=0)
    overall_status: OverallStatus


class ValidationTiming(ValidationModel):
    level1_processing_ms: float | None = Field(default=None, ge=0.0)
    level2_validation_ms: float = Field(ge=0.0)
    total_processing_ms: float | None = Field(default=None, ge=0.0)


class ValidationReport(ValidationModel):
    drawing_id: str | None = None
    source_filename: str
    rule_set_version: str
    summary: ValidationSummary
    results: list[ValidationResult]
    timing: ValidationTiming
    disclaimer: str = (
        "Automated validation assists engineering drawing review. Final engineering "
        "approval remains the responsibility of the authorized reviewer."
    )
