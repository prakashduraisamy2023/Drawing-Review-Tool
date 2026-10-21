"""Drawing-note to flag-callout relationships."""

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


class NoteCalloutRule:
    rule_id = "REL-NOTE-001"

    def evaluate(self, context: RelationshipContext):
        notes = context.entities(EntityType.NOTE)
        callouts = context.entities(EntityType.NOTE_CALLOUT)
        if not notes:
            return [
                finding(
                    self.rule_id,
                    "Note ↔ callout",
                    "Matches drawing note definitions to detected flag-note callouts.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.MEDIUM,
                    1.0,
                    "Callouts resolve to defined notes.",
                    "No numbered drawing notes were extracted.",
                    "The relationship is not applicable.",
                    "No action required.",
                )
            ]
        if context.vision_report is None:
            return [
                finding(
                    self.rule_id,
                    "Note ↔ callout",
                    "Matches drawing note definitions to detected flag-note callouts.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.MEDIUM,
                    0.0,
                    "Callouts resolve to defined notes.",
                    "Level-3 visual analysis has not been run.",
                    "Callout evidence is unavailable.",
                    "Run Level-3 visual analysis.",
                    source=notes,
                    evidence=[context.evidence(item) for item in notes],
                    related_validation_rule_ids=["NOTE-012"],
                )
            ]
        note_map = {normalized_identifier(note.value): note for note in notes}
        results = []
        referenced: set[str] = set()
        for callout in callouts:
            key = normalized_identifier(callout.value)
            note = note_map.get(key)
            evidence = [context.evidence(callout)] + ([context.evidence(note)] if note else [])
            if note:
                referenced.add(key)
                status = (
                    RelationshipStatus.PASS
                    if callout.confidence >= context.automatic_threshold
                    else RelationshipStatus.WARNING
                    if callout.confidence >= context.partial_floor
                    else RelationshipStatus.MANUAL_REVIEW
                )
                context.graph.add_relationship(
                    RelationshipType.REFERENCES,
                    callout,
                    note,
                    status=status,
                    confidence=relationship_confidence(callout, note),
                    evidence=evidence,
                    explanation=f"Callout {callout.value} references Note {note.value}.",
                )
                actual = f"Callout {callout.value} on sheet {callout.page_number} resolves to Note {note.value}."
            else:
                status = (
                    RelationshipStatus.WARNING
                    if callout.confidence >= context.partial_floor
                    else RelationshipStatus.MANUAL_REVIEW
                )
                context.graph.add_relationship(
                    RelationshipType.MISSING_LINK,
                    callout,
                    None,
                    status=status,
                    confidence=callout.confidence,
                    evidence=evidence,
                    explanation=f"Callout {callout.value} has no extracted note definition.",
                )
                actual = f"Callout {callout.value} on sheet {callout.page_number} has no corresponding drawing note."
            results.append(
                finding(
                    self.rule_id,
                    f"Note callout {callout.value}",
                    "Matches drawing note definitions to detected flag-note callouts.",
                    status,
                    RelationshipSeverity.MEDIUM,
                    callout.confidence,
                    "Every detected note callout resolves to a drawing note.",
                    actual,
                    "Only explicit note and callout identifiers are compared.",
                    "Review the highlighted note relationship."
                    if status != RelationshipStatus.PASS
                    else "No action required.",
                    source=[callout],
                    target=[note] if note else [],
                    evidence=evidence,
                    related_validation_rule_ids=["NOTE-012"],
                    discriminator=callout.entity_id,
                )
            )
        unreferenced = [note for key, note in note_map.items() if key not in referenced]
        if unreferenced:
            results.append(
                finding(
                    self.rule_id,
                    "Unreferenced drawing notes",
                    "Reports note definitions for which no flag callout was detected.",
                    RelationshipStatus.WARNING,
                    RelationshipSeverity.LOW,
                    min((item.confidence for item in unreferenced), default=0.0),
                    "Applicable flag-note definitions have callouts.",
                    f"No detected flag callout references notes {[item.value for item in unreferenced]}.",
                    "Detector absence does not prove that a note is unused; this is a review prompt.",
                    "Confirm whether these notes are general notes or require callouts.",
                    source=unreferenced,
                    evidence=[context.evidence(item) for item in unreferenced],
                    related_validation_rule_ids=["NOTE-012"],
                    discriminator="unreferenced",
                )
            )
        return results or [
            finding(
                self.rule_id,
                "Note ↔ callout",
                "Matches drawing note definitions to detected flag-note callouts.",
                RelationshipStatus.NOT_EVALUATED,
                RelationshipSeverity.MEDIUM,
                0.0,
                "Callouts resolve to defined notes.",
                "No note callouts were detected.",
                "Detector completeness is not established.",
                "Review note usage manually.",
                source=notes,
                evidence=[context.evidence(item) for item in notes],
            )
        ]
