"""Helpers shared by relationship rules."""

from __future__ import annotations

from backend.app.relationships.graph import stable_id
from backend.app.relationships.models import (
    EngineeringEntity,
    RelationshipEvidence,
    RelationshipResult,
    RelationshipSeverity,
    RelationshipStatus,
)


def finding(
    rule_id: str,
    name: str,
    description: str,
    status: RelationshipStatus,
    severity: RelationshipSeverity,
    confidence: float,
    expected: str,
    actual: str,
    explanation: str,
    recommendation: str,
    *,
    source: list[EngineeringEntity] | None = None,
    target: list[EngineeringEntity] | None = None,
    evidence: list[RelationshipEvidence] | None = None,
    related_validation_rule_ids: list[str] | None = None,
    discriminator: object = "summary",
) -> RelationshipResult:
    return RelationshipResult(
        finding_id=stable_id("finding", rule_id, discriminator, actual),
        relationship_rule_id=rule_id,
        name=name,
        description=description,
        status=status,
        severity=severity,
        confidence=max(0.0, min(1.0, confidence)),
        expected_relationship=expected,
        actual_relationship=actual,
        source_entities=[item.entity_id for item in source or []],
        target_entities=[item.entity_id for item in target or []],
        evidence=evidence or [],
        explanation=explanation,
        recommendation=recommendation,
        related_validation_rule_ids=related_validation_rule_ids or [],
    )
