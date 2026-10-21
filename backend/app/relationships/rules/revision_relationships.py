"""Revision-control relationship checks."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import (
    EntityType,
    RelationshipSeverity,
    RelationshipStatus,
    RelationshipType,
)
from backend.app.relationships.rules.base import finding
from backend.app.relationships.scoring import normalized_identifier, relationship_confidence


class RevisionRelationshipRule:
    rule_id = "REL-REV-001"

    def evaluate(self, context: RelationshipContext):
        revisions = context.entities(EntityType.REVISION)
        current = next(
            (item for item in revisions if item.attributes.get("role") == "CURRENT"), None
        )
        table = [item for item in revisions if item.attributes.get("role") == "TABLE_ENTRY"]
        triangles = context.entities(EntityType.REVISION_TRIANGLE)
        evidence = [
            context.evidence(item) for item in ([current] if current else []) + table + triangles
        ]
        if current is None or not table:
            return [
                finding(
                    self.rule_id,
                    "Revision ↔ revision triangle",
                    "Connects title revision, revision table, and visual revision markers.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Current revision is present in the revision table and identified by visual evidence where applicable.",
                    "Current title revision or revision-table evidence is unavailable.",
                    "The Level-1 revision dependency is incomplete.",
                    "Review Level-1 revision evidence.",
                    source=revisions,
                    target=triangles,
                    evidence=evidence,
                    related_validation_rule_ids=["REV-012"],
                )
            ]
        current_value = normalized_identifier(current.value)
        table_matches = [
            item for item in table if normalized_identifier(item.value) == current_value
        ]
        if context.vision_report is None:
            status = RelationshipStatus.NOT_EVALUATED
            actual = f"Title revision {current.value}; table match={bool(table_matches)}; Level-3 not run."
        else:
            reliable = [
                item
                for item in triangles
                if item.confidence >= context.partial_floor and normalized_identifier(item.value)
            ]
            triangle_matches = [
                item for item in reliable if normalized_identifier(item.value) == current_value
            ]
            mismatches = [
                item for item in reliable if normalized_identifier(item.value) != current_value
            ]
            if table_matches and triangle_matches and not mismatches:
                status = RelationshipStatus.PASS
            elif not table_matches:
                status = RelationshipStatus.FAIL
            elif mismatches:
                status = RelationshipStatus.WARNING
            elif triangles:
                status = RelationshipStatus.MANUAL_REVIEW
            else:
                status = RelationshipStatus.WARNING
            actual = f"Title revision={current.value}; table revisions={[item.value for item in table]}; detected triangle identifiers={[item.value for item in triangles]}."
            for triangle in triangles:
                match = next(
                    (
                        item
                        for item in table
                        if normalized_identifier(item.value)
                        == normalized_identifier(triangle.value)
                    ),
                    None,
                )
                context.graph.add_relationship(
                    RelationshipType.IDENTIFIES if match else RelationshipType.CONFLICTS_WITH,
                    triangle,
                    match or current,
                    status=RelationshipStatus.PASS if match else RelationshipStatus.WARNING,
                    confidence=relationship_confidence(triangle, match or current),
                    evidence=[context.evidence(triangle), context.evidence(match or current)],
                    explanation=f"Revision triangle {triangle.value} {'matches' if match else 'does not match'} extracted revision evidence.",
                )
        confidence = min((item.confidence for item in [current, *table] if item), default=0.0)
        return [
            finding(
                self.rule_id,
                "Revision ↔ revision triangle",
                "Connects title revision, revision table, and visual revision markers.",
                status,
                RelationshipSeverity.HIGH,
                confidence,
                "Current revision is present in the revision table and identified by matching visual revision markers where applicable.",
                actual,
                "The comparison is identifier-based and does not infer the geometry changed by a revision.",
                "Review mismatched or absent triangle evidence."
                if status != RelationshipStatus.PASS
                else "No action required.",
                source=[current, *table],
                target=triangles,
                evidence=evidence,
                related_validation_rule_ids=["REV-012", "TB-003", "REV-011"],
            )
        ]


class RevisionTraceabilityRule:
    rule_id = "REL-REV-002"

    def evaluate(self, context: RelationshipContext):
        revisions = context.entities(EntityType.REVISION)
        triangles = context.entities(EntityType.REVISION_TRIANGLE)
        if not revisions:
            status = RelationshipStatus.NOT_APPLICABLE
            actual = "No revision records were extracted."
        elif not triangles:
            status = RelationshipStatus.NOT_EVALUATED
            actual = "No revision-triangle evidence is available."
        else:
            status = RelationshipStatus.MANUAL_REVIEW
            actual = f"{len(revisions)} revision entity/entities and {len(triangles)} triangle candidate(s) are available; changed drawing regions are not classified."
        return [
            finding(
                self.rule_id,
                "Revision change traceability",
                "Framework from revision record through triangle to changed drawing region.",
                status,
                RelationshipSeverity.MEDIUM,
                min((item.confidence for item in revisions + triangles), default=0.0),
                "Each revision entry traces through its marker to an evidenced changed region.",
                actual,
                "The current system does not fabricate changed geometry from a marker.",
                "Confirm the changed drawing regions manually.",
                source=revisions,
                target=triangles,
                evidence=[context.evidence(item) for item in revisions + triangles],
                related_validation_rule_ids=["REV-012"],
            )
        ]
