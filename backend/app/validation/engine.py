"""Fault-isolated deterministic Level-2 validation engine."""

from __future__ import annotations

import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.models.drawing import DrawingDocument
from backend.app.validation.context import ValidationContext, load_controlled_config, project_root
from backend.app.validation.models import (
    ValidationReport,
    ValidationSummary,
    ValidationTiming,
)
from backend.app.validation.registry import RuleRegistry, build_default_registry
from backend.app.validation.rules.base import outcome
from backend.app.validation.severity import (
    OverallStatus,
    ValidationSeverity,
    ValidationStatus,
)
from backend.app.vision.models import VisionReport

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Execute controlled rules independently against an existing DrawingDocument."""

    def __init__(
        self,
        configuration: dict[str, Any] | None = None,
        registry: RuleRegistry | None = None,
    ) -> None:
        self.configuration = configuration or load_controlled_config(
            project_root() / "config" / "validation_rules.yaml"
        )
        self.registry = registry or build_default_registry(self.configuration)

    @classmethod
    def from_config(cls, path: str | Path) -> ValidationEngine:
        return cls(configuration=load_controlled_config(Path(path)))

    def validate(
        self,
        document: DrawingDocument,
        *,
        drawing_id: str | None = None,
        rule_master_data: dict[str, Any] | None = None,
        vision_report: VisionReport | None = None,
    ) -> ValidationReport:
        started = time.perf_counter()
        context = ValidationContext(document, self.configuration, rule_master_data, vision_report)
        results = []
        for rule in self.registry:
            rule_started = time.perf_counter()
            try:
                if not rule.is_applicable(context):
                    rule_outcome = outcome(
                        ValidationStatus.NOT_APPLICABLE,
                        rule.metadata.applicability,
                        "The drawing does not meet this rule's explicit applicability condition.",
                        f"{rule.metadata.rule_id}: rule is not applicable to this drawing.",
                        "No action required.",
                    )
                else:
                    rule_outcome = rule.validate(context)
            except Exception as exc:  # an individual rule must never abort the document
                logger.exception(
                    "validation_rule_exception drawing_id=%s rule_id=%s exception=%s",
                    drawing_id,
                    rule.metadata.rule_id,
                    type(exc).__name__,
                )
                rule_outcome = outcome(
                    ValidationStatus.NOT_EVALUATED,
                    "Rule executes successfully when its dependencies are available.",
                    f"Technical rule failure: {type(exc).__name__}.",
                    f"{rule.metadata.rule_id}: technical failure prevented evaluation.",
                    "Review the application log; do not interpret this as an engineering failure.",
                )
            elapsed = (time.perf_counter() - rule_started) * 1000
            result = rule.result(rule_outcome, elapsed)
            results.append(result)
            logger.info(
                "validation_rule drawing_id=%s rule_id=%s status=%s execution_time_ms=%.3f",
                drawing_id,
                result.rule_id,
                result.status,
                result.execution_time_ms,
            )

        level2_ms = (time.perf_counter() - started) * 1000
        summary = self._summarize(results)
        level1_ms = None
        return ValidationReport(
            drawing_id=drawing_id,
            source_filename=str(document.source_filename.value or "unknown.pdf"),
            rule_set_version=str(self.configuration.get("rule_set_version", "1.0.0")),
            summary=summary,
            results=results,
            timing=ValidationTiming(
                level1_processing_ms=level1_ms,
                level2_validation_ms=level2_ms,
                total_processing_ms=None if level1_ms is None else level1_ms + level2_ms,
            ),
        )

    def _summarize(self, results: list[Any]) -> ValidationSummary:
        counts = Counter(result.status for result in results)
        critical = sum(
            result.status == ValidationStatus.FAIL
            and result.severity == ValidationSeverity.CRITICAL
            for result in results
        )
        high = sum(
            result.status == ValidationStatus.FAIL and result.severity == ValidationSeverity.HIGH
            for result in results
        )
        policy = self.configuration.get("overall_status", {})
        if critical and policy.get("critical_failure", "FAIL") == "FAIL":
            overall = OverallStatus.FAIL
        elif high:
            overall = OverallStatus.REVIEW_REQUIRED
        elif counts[ValidationStatus.MANUAL_REVIEW] or counts[ValidationStatus.NOT_EVALUATED]:
            overall = OverallStatus.REVIEW_REQUIRED
        elif counts[ValidationStatus.FAIL]:
            overall = OverallStatus.REVIEW_REQUIRED
        elif counts[ValidationStatus.WARNING]:
            overall = OverallStatus.PASS_WITH_WARNINGS
        else:
            overall = OverallStatus.PASS
        return ValidationSummary(
            total_rules=len(results),
            passed=counts[ValidationStatus.PASS],
            failed=counts[ValidationStatus.FAIL],
            warnings=counts[ValidationStatus.WARNING],
            manual_review=counts[ValidationStatus.MANUAL_REVIEW],
            not_applicable=counts[ValidationStatus.NOT_APPLICABLE],
            not_evaluated=counts[ValidationStatus.NOT_EVALUATED],
            critical_failures=critical,
            high_failures=high,
            overall_status=overall,
        )
