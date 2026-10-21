"""Base interface and helpers for independently executable validation rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.app.validation.context import ApplicabilityContext, ValidationContext
from backend.app.validation.models import RuleMetadata, ValidationEvidence, ValidationResult
from backend.app.validation.severity import ValidationStatus


@dataclass(frozen=True)
class RuleOutcome:
    status: ValidationStatus
    expected: str
    actual: str
    message: str
    recommendation: str
    evidence: list[ValidationEvidence]
    related_fields: list[str]


class ValidationRule(ABC):
    metadata: RuleMetadata

    def __init__(self, metadata: RuleMetadata) -> None:
        self.metadata = metadata

    def is_applicable(self, context: ValidationContext) -> bool:
        applicability = ApplicabilityContext.from_validation_context(context)
        key = self.metadata.applicability
        if key == "supplier":
            return applicability.document_type == "SUPPLIER_DRAWING"
        if key == "multi_page":
            return bool(applicability.page_count and applicability.page_count > 1)
        if key == "bom":
            return applicability.has_bom
        if key == "part_list":
            return applicability.has_part_list
        if key == "service_parts":
            return applicability.has_service_parts
        if key == "notes":
            return applicability.has_notes
        if key == "standards":
            return applicability.has_standards
        return True

    @abstractmethod
    def validate(self, context: ValidationContext) -> RuleOutcome:
        raise NotImplementedError

    def result(self, outcome: RuleOutcome, execution_time_ms: float) -> ValidationResult:
        return ValidationResult(
            rule_id=self.metadata.rule_id,
            rule_name=self.metadata.name,
            rule_category=self.metadata.category,
            rule_description=self.metadata.description,
            source_requirement=self.metadata.source_requirement,
            status=outcome.status,
            severity=self.metadata.severity,
            automation_type=self.metadata.automation_type,
            expected_condition=outcome.expected,
            actual_condition=outcome.actual,
            message=outcome.message,
            recommendation=outcome.recommendation,
            evidence=outcome.evidence,
            related_fields=outcome.related_fields,
            rule_version=self.metadata.version,
            execution_time_ms=execution_time_ms,
        )


def outcome(
    status: ValidationStatus,
    expected: str,
    actual: str,
    message: str,
    recommendation: str = "Review the cited source evidence.",
    evidence: list[ValidationEvidence] | None = None,
    related_fields: list[str] | None = None,
) -> RuleOutcome:
    return RuleOutcome(
        status=status,
        expected=expected,
        actual=actual,
        message=message,
        recommendation=recommendation,
        evidence=evidence or [],
        related_fields=related_fields or [],
    )
