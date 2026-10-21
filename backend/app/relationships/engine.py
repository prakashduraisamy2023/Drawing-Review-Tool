"""Fault-isolated Level-4 relationship analysis orchestration."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from backend.app.models.drawing import DrawingDocument
from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.graph import stable_id
from backend.app.relationships.models import (
    IssueCorrelation,
    RelationshipReport,
    RelationshipResult,
    RelationshipSeverity,
    RelationshipStatus,
    RelationshipSummary,
    RelationshipTiming,
    ReviewPriority,
)
from backend.app.relationships.prioritization import apply_priorities
from backend.app.relationships.registry import RelationshipRegistry, build_default_registry
from backend.app.relationships.rules.base import finding
from backend.app.validation.context import load_controlled_config, project_root
from backend.app.validation.models import ValidationReport
from backend.app.vision.models import VisionReport


class RelationshipEngine:
    def __init__(
        self,
        *,
        configuration: dict | None = None,
        registry: RelationshipRegistry | None = None,
    ) -> None:
        self.configuration = configuration or load_controlled_config(
            project_root() / "config" / "relationships.yaml"
        )
        self.registry = registry or build_default_registry()

    @classmethod
    def from_config(cls, path: str | Path) -> RelationshipEngine:
        return cls(configuration=load_controlled_config(Path(path)))

    def analyze(
        self,
        document: DrawingDocument,
        *,
        drawing_id: str | None = None,
        validation_report: ValidationReport | None = None,
        vision_report: VisionReport | None = None,
    ) -> RelationshipReport:
        started = time.perf_counter()
        context = RelationshipContext(
            document=document,
            validation_report=validation_report,
            vision_report=vision_report,
            configuration=self.configuration,
        )
        context.build_entities()
        findings: list[RelationshipResult] = []
        for rule in self.registry:
            try:
                findings.extend(rule.evaluate(context))
            except Exception as exc:  # one relationship must never abort the report
                findings.append(
                    finding(
                        rule.rule_id,
                        f"{rule.rule_id} technical evaluation",
                        "Relationship rule execution is fault-isolated.",
                        RelationshipStatus.NOT_EVALUATED,
                        RelationshipSeverity.HIGH,
                        0.0,
                        "The relationship rule executes successfully.",
                        f"Technical relationship failure: {type(exc).__name__}.",
                        "The technical failure is not an engineering finding.",
                        "Review the application log and assess this relationship manually.",
                        discriminator=type(exc).__name__,
                    )
                )
        findings = apply_priorities(findings)
        correlations = self._correlate(findings, validation_report)
        graph = context.graph.export()
        counts = Counter(item.status for item in findings)
        broken = sum(edge.relationship_type == "MISSING_LINK" for edge in graph.edges)
        if counts[RelationshipStatus.FAIL]:
            overall = "FAIL"
        elif counts[RelationshipStatus.MANUAL_REVIEW] or counts[RelationshipStatus.NOT_EVALUATED]:
            overall = "REVIEW_REQUIRED"
        elif counts[RelationshipStatus.WARNING]:
            overall = "PASS_WITH_WARNINGS"
        else:
            overall = "PASS"
        return RelationshipReport(
            drawing_id=drawing_id,
            source_filename=str(document.source_filename.value or "unknown.pdf"),
            level4_version=str(self.configuration.get("level4_version", "1.0.0")),
            graph=graph,
            findings=findings,
            correlations=correlations,
            summary=RelationshipSummary(
                relationships_checked=len(findings),
                passed=counts[RelationshipStatus.PASS],
                broken=broken,
                warnings=counts[RelationshipStatus.WARNING],
                manual_review=counts[RelationshipStatus.MANUAL_REVIEW],
                not_applicable=counts[RelationshipStatus.NOT_APPLICABLE],
                not_evaluated=counts[RelationshipStatus.NOT_EVALUATED],
                high_priority_findings=sum(
                    item.priority in {ReviewPriority.P1, ReviewPriority.P2}
                    and item.status != RelationshipStatus.PASS
                    for item in findings
                ),
                overall_status=overall,
            ),
            timing=RelationshipTiming(
                level4_relationship_ms=(time.perf_counter() - started) * 1000
            ),
        )

    def _correlate(
        self,
        findings: list[RelationshipResult],
        validation_report: ValidationReport | None,
    ) -> list[IssueCorrelation]:
        correlations: list[IssueCorrelation] = []
        validation_issues = [
            item
            for item in (validation_report.results if validation_report else [])
            if item.status in {"FAIL", "WARNING", "MANUAL_REVIEW"}
        ]
        for category, rule_ids in self.configuration.get("relationship_categories", {}).items():
            related = [
                item
                for item in findings
                if item.relationship_rule_id in rule_ids
                and item.status in {"FAIL", "WARNING", "MANUAL_REVIEW", "NOT_EVALUATED"}
            ]
            linked_ids = sorted(
                {
                    rule_id
                    for item in related
                    for rule_id in item.related_validation_rule_ids
                    if any(issue.rule_id == rule_id for issue in validation_issues)
                }
            )
            if len(related) + len(linked_ids) < 2:
                continue
            priority = min(
                (ReviewPriority(item.priority) for item in related),
                key=lambda value: [
                    ReviewPriority.P1,
                    ReviewPriority.P2,
                    ReviewPriority.P3,
                    ReviewPriority.P4,
                ].index(value),
            )
            correlations.append(
                IssueCorrelation(
                    correlation_id=stable_id(
                        "correlation", category, *[item.finding_id for item in related]
                    ),
                    category=category,
                    title=category.title(),
                    priority=priority,
                    finding_ids=[item.finding_id for item in related],
                    related_validation_rule_ids=linked_ids,
                    explanation=(
                        f"{len(related)} Level-4 finding(s) and {len(linked_ids)} related "
                        "Level-2 issue(s) concern the same engineering relationship family."
                    ),
                )
            )
        return correlations
