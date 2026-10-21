"""Cross-sheet issue connection using existing Level-2 results."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import (
    RelationshipEvidence,
    RelationshipSeverity,
    RelationshipStatus,
    SourceLevel,
)
from backend.app.relationships.rules.base import finding


class CrossSheetRule:
    rule_id = "REL-DOC-001"
    linked_rules = ["TB-002", "TB-004", "TB-007", "TB-009", "TB-010"]

    def evaluate(self, context: RelationshipContext):
        page_count = context.document.page_count.value or len(context.document.pages or [])
        if page_count <= 1:
            return [
                finding(
                    self.rule_id,
                    "Cross-sheet consistency",
                    "Connects existing Level-2 drawing number, revision, units, and sheet-sequence checks.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.HIGH,
                    1.0,
                    "Multi-sheet metadata is consistent.",
                    "The drawing has one sheet.",
                    "Cross-sheet consistency is not applicable.",
                    "No action required.",
                    related_validation_rule_ids=self.linked_rules,
                )
            ]
        if context.validation_report is None:
            return [
                finding(
                    self.rule_id,
                    "Cross-sheet consistency",
                    "Connects existing Level-2 drawing number, revision, units, and sheet-sequence checks.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Multi-sheet metadata is consistent.",
                    "Level-2 validation has not been run.",
                    "Level 4 reuses rather than duplicates the underlying checks.",
                    "Run Level-2 validation.",
                    related_validation_rule_ids=self.linked_rules,
                )
            ]
        results = [
            item for item in context.validation_report.results if item.rule_id in self.linked_rules
        ]
        statuses = {item.status for item in results}
        if "FAIL" in statuses:
            status = RelationshipStatus.FAIL
        elif "WARNING" in statuses:
            status = RelationshipStatus.WARNING
        elif "MANUAL_REVIEW" in statuses:
            status = RelationshipStatus.MANUAL_REVIEW
        elif "NOT_EVALUATED" in statuses:
            status = RelationshipStatus.NOT_EVALUATED
        else:
            status = RelationshipStatus.PASS
        evidence = [
            RelationshipEvidence(
                page_number=item.page_number,
                bounding_box=item.bounding_box,
                source_level=SourceLevel.LEVEL_2,
                source_reference=f"validation.results.{result.rule_id}.{item.source_field}",
                value=item.extracted_value,
                confidence=item.confidence,
                extraction_method=item.extraction_method,
            )
            for result in results
            for item in result.evidence
        ]
        return [
            finding(
                self.rule_id,
                "Cross-sheet consistency",
                "Connects existing Level-2 drawing number, revision, units, and sheet-sequence checks.",
                status,
                RelationshipSeverity.HIGH,
                min((item.confidence for item in evidence), default=0.0),
                "Multi-sheet drawing number, revision, units, and sheet sequence are consistent.",
                "; ".join(f"{item.rule_id}={item.status}" for item in results),
                "The Level-4 result summarizes and connects existing Level-2 evidence without reimplementing its checks.",
                "Open the linked Level-2 checks for details."
                if status != RelationshipStatus.PASS
                else "No action required.",
                evidence=evidence,
                related_validation_rule_ids=self.linked_rules,
            )
        ]
