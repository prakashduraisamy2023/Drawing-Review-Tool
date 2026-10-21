"""Transparent deterministic review prioritization."""

from backend.app.relationships.models import (
    RelationshipResult,
    RelationshipSeverity,
    RelationshipStatus,
    ReviewPriority,
)


def priority_for(result: RelationshipResult) -> ReviewPriority:
    if (
        result.status == RelationshipStatus.FAIL
        and result.severity == RelationshipSeverity.CRITICAL
    ):
        return ReviewPriority.P1
    if result.status == RelationshipStatus.FAIL or result.severity in {
        RelationshipSeverity.CRITICAL,
        RelationshipSeverity.HIGH,
    }:
        return ReviewPriority.P2
    if result.status in {
        RelationshipStatus.WARNING,
        RelationshipStatus.MANUAL_REVIEW,
        RelationshipStatus.NOT_EVALUATED,
    }:
        return ReviewPriority.P3
    return ReviewPriority.P4


def apply_priorities(findings: list[RelationshipResult]) -> list[RelationshipResult]:
    for finding in findings:
        finding.priority = priority_for(finding)
    order = {ReviewPriority.P1: 0, ReviewPriority.P2: 1, ReviewPriority.P3: 2, ReviewPriority.P4: 3}
    return sorted(
        findings,
        key=lambda item: (
            order[ReviewPriority(item.priority)],
            item.relationship_rule_id,
            item.finding_id,
        ),
    )
