"""Syntactic datum-to-GD&T frame relationships."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from collections import Counter

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import (
    EntityType,
    RelationshipSeverity,
    RelationshipStatus,
    RelationshipType,
)
from backend.app.relationships.rules.base import finding
from backend.app.relationships.scoring import normalized_identifier, relationship_confidence


class DatumGdtRule:
    rule_id = "REL-GDT-001"

    def evaluate(self, context: RelationshipContext):
        datums = context.entities(EntityType.DATUM)
        frames = context.entities(EntityType.GDT_FRAME)
        if context.vision_report is None:
            return [
                finding(
                    self.rule_id,
                    "Datum ↔ GD&T frame",
                    "Checks whether datum identifiers referenced by detected frames exist as detected datum symbols.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Every recognized frame datum reference resolves to a detected datum symbol.",
                    "Level-3 visual analysis has not been run.",
                    "Datum and frame evidence is unavailable.",
                    "Run Level-3 visual analysis.",
                )
            ]
        if not frames:
            return [
                finding(
                    self.rule_id,
                    "Datum ↔ GD&T frame",
                    "Checks whether datum identifiers referenced by detected frames exist as detected datum symbols.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Every recognized frame datum reference resolves to a detected datum symbol.",
                    "No tokenized GD&T frame was detected.",
                    "Frame completeness is not established.",
                    "Review GD&T frames manually.",
                    source=datums,
                    evidence=[context.evidence(item) for item in datums],
                )
            ]
        datum_map = {normalized_identifier(item.value): item for item in datums}
        results = []
        for frame in frames:
            references = [
                normalized_identifier(value)
                for value in frame.attributes.get("datum_sequence", [])
                if normalized_identifier(value)
            ]
            if not references:
                results.append(
                    finding(
                        self.rule_id,
                        "GD&T frame datum references",
                        "Checks whether datum identifiers referenced by detected frames exist as detected datum symbols.",
                        RelationshipStatus.MANUAL_REVIEW,
                        RelationshipSeverity.HIGH,
                        frame.confidence,
                        "Recognized datum references resolve to datum symbols.",
                        f"Frame on sheet {frame.page_number} has no reliably recognized datum sequence.",
                        "Frame geometry alone does not establish datum references.",
                        "Read the highlighted frame manually.",
                        source=[frame],
                        evidence=[context.evidence(frame)],
                        discriminator=frame.entity_id,
                    )
                )
                continue
            missing = [reference for reference in references if reference not in datum_map]
            matched = [datum_map[reference] for reference in references if reference in datum_map]
            evidence = [context.evidence(frame), *[context.evidence(item) for item in matched]]
            status = (
                RelationshipStatus.FAIL
                if missing and frame.confidence >= context.automatic_threshold
                else RelationshipStatus.WARNING
                if missing
                else RelationshipStatus.PASS
            )
            for reference in references:
                target = datum_map.get(reference)
                context.graph.add_relationship(
                    RelationshipType.REFERENCES if target else RelationshipType.MISSING_LINK,
                    frame,
                    target,
                    status=RelationshipStatus.PASS if target else status,
                    confidence=relationship_confidence(frame, target)
                    if target
                    else frame.confidence,
                    evidence=[context.evidence(frame)]
                    + ([context.evidence(target)] if target else []),
                    explanation=f"GD&T frame datum reference {reference} {'resolves' if target else 'does not resolve'} to a detected datum symbol.",
                )
            results.append(
                finding(
                    self.rule_id,
                    f"GD&T frame on sheet {frame.page_number}",
                    "Checks whether datum identifiers referenced by detected frames exist as detected datum symbols.",
                    status,
                    RelationshipSeverity.HIGH,
                    frame.confidence,
                    "All recognized datum references resolve to detected datum symbols.",
                    f"References={references}; missing={missing}.",
                    "This is a syntactic existence check, not a judgment that the selected datums are functionally correct.",
                    "Review missing datum symbols." if missing else "No action required.",
                    source=[frame],
                    target=matched,
                    evidence=evidence,
                    related_validation_rule_ids=["GDT-001", "GDT-004"],
                    discriminator=frame.entity_id,
                )
            )
        return results


class DatumUsageRule:
    rule_id = "REL-GDT-002"

    def evaluate(self, context: RelationshipContext):
        datums = context.entities(EntityType.DATUM)
        frames = context.entities(EntityType.GDT_FRAME)
        if not datums:
            return [
                finding(
                    self.rule_id,
                    "Duplicate / unused datum analysis",
                    "Reports duplicate and apparently unused datum identifiers without judging design intent.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.MEDIUM,
                    0.0,
                    "Detected datum identifiers are unambiguous and referenced where applicable.",
                    "No datum symbols were detected.",
                    "Datum completeness is not established.",
                    "Review datum usage manually.",
                )
            ]
        identifiers = [
            normalized_identifier(item.value)
            for item in datums
            if normalized_identifier(item.value)
        ]
        duplicates = sorted(value for value, count in Counter(identifiers).items() if count > 1)
        referenced = {
            normalized_identifier(value)
            for frame in frames
            for value in frame.attributes.get("datum_sequence", [])
        }
        unused = sorted(set(identifiers) - referenced)
        status = RelationshipStatus.WARNING if duplicates or unused else RelationshipStatus.PASS
        return [
            finding(
                self.rule_id,
                "Duplicate / unused datum analysis",
                "Reports duplicate and apparently unused datum identifiers without judging design intent.",
                status,
                RelationshipSeverity.MEDIUM,
                min((item.confidence for item in datums), default=0.0),
                "Detected datum identifiers are unambiguous and referenced where applicable.",
                f"Duplicate identifiers={duplicates}; apparently unused identifiers={unused}.",
                "Duplicate or unused datum semantics can be legitimate; this is not a functional GD&T conclusion.",
                "Review the highlighted datum usage."
                if status == RelationshipStatus.WARNING
                else "No action required.",
                source=datums,
                target=frames,
                evidence=[context.evidence(item) for item in datums + frames],
                related_validation_rule_ids=["GDT-002", "GDT-003"],
                discriminator="datum-usage",
            )
        ]
