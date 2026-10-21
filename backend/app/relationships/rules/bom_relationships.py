"""BOM-to-balloon relationship checks."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import (
    EntityType,
    RelationshipSeverity,
    RelationshipStatus,
    RelationshipType,
)
from backend.app.relationships.rules.base import finding
from backend.app.relationships.scoring import (
    confidence_band,
    normalized_identifier,
    relationship_confidence,
)


class BOMBalloonRule:
    rule_id = "REL-BOM-001"

    def evaluate(self, context: RelationshipContext):
        items = context.entities(EntityType.BOM_ITEM)
        balloons = context.entities(EntityType.BALLOON)
        if not items:
            return [
                finding(
                    self.rule_id,
                    "BOM item to balloon",
                    "Matches BOM item numbers to detected balloon numbers.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.MEDIUM,
                    1.0,
                    "Each applicable BOM item has a corresponding balloon.",
                    "No BOM items were extracted.",
                    "The relationship is not applicable without a BOM.",
                    "No action required.",
                )
            ]
        if context.vision_report is None:
            return [
                finding(
                    self.rule_id,
                    "BOM item to balloon",
                    "Matches BOM item numbers to detected balloon numbers.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Each applicable BOM item has a corresponding balloon.",
                    "Level-3 visual analysis has not been run.",
                    "Balloon evidence is unavailable.",
                    "Run Level-3 visual analysis.",
                    source=items,
                    evidence=[context.evidence(item) for item in items],
                )
            ]

        by_number: dict[str, list] = {}
        for balloon in balloons:
            by_number.setdefault(normalized_identifier(balloon.value), []).append(balloon)
        results = []
        missing_status = RelationshipStatus(
            context.configuration.get("bom_missing_status", "WARNING")
        )
        for item in items:
            matches = by_number.get(normalized_identifier(item.value), [])
            if not matches:
                evidence = [context.evidence(item)]
                context.graph.add_relationship(
                    RelationshipType.MISSING_LINK,
                    item,
                    None,
                    status=missing_status,
                    confidence=item.confidence,
                    evidence=evidence,
                    explanation=f"No detected balloon matches BOM item {item.value}.",
                )
                results.append(
                    finding(
                        self.rule_id,
                        f"BOM item {item.value} ↔ balloon",
                        "Matches BOM item numbers to detected balloon numbers.",
                        missing_status,
                        RelationshipSeverity.HIGH,
                        item.confidence,
                        f"BOM item {item.value} has a corresponding balloon.",
                        f"No balloon numbered {item.value} was detected.",
                        "A missing visual link is observed, but detector completeness is not independently established.",
                        "Review the drawing area for the expected balloon.",
                        source=[item],
                        evidence=evidence,
                        related_validation_rule_ids=["BOM-011", "XREF-007"],
                        discriminator=item.entity_id,
                    )
                )
                continue
            best = max(matches, key=lambda candidate: candidate.confidence)
            confidence = relationship_confidence(item, best)
            band = confidence_band(
                confidence, automatic=context.automatic_threshold, partial=context.partial_floor
            )
            status = (
                RelationshipStatus.PASS
                if band == "AUTOMATIC"
                else RelationshipStatus.WARNING
                if band == "PARTIAL"
                else RelationshipStatus.MANUAL_REVIEW
            )
            evidence = [context.evidence(item), context.evidence(best)]
            context.graph.add_relationship(
                RelationshipType.CALLED_OUT_BY,
                item,
                best,
                status=status,
                confidence=confidence,
                evidence=evidence,
                explanation=f"BOM item {item.value} is linked to balloon {best.value}.",
            )
            results.append(
                finding(
                    self.rule_id,
                    f"BOM item {item.value} ↔ balloon",
                    "Matches BOM item numbers to detected balloon numbers.",
                    status,
                    RelationshipSeverity.HIGH,
                    confidence,
                    f"BOM item {item.value} has a corresponding balloon.",
                    f"Balloon {best.value} was detected on sheet {best.page_number}.",
                    "The identifiers match; confidence gating determines whether the link is automatic or reviewable.",
                    "No action required."
                    if status == RelationshipStatus.PASS
                    else "Confirm the highlighted balloon.",
                    source=[item],
                    target=[best],
                    evidence=evidence,
                    related_validation_rule_ids=["BOM-011", "XREF-007"],
                    discriminator=item.entity_id,
                )
            )
        return results


class OrphanBalloonRule:
    rule_id = "REL-BOM-002"

    def evaluate(self, context: RelationshipContext):
        balloons = context.entities(EntityType.BALLOON)
        items = context.entities(EntityType.BOM_ITEM)
        if context.vision_report is None:
            return [
                finding(
                    self.rule_id,
                    "Orphan balloon",
                    "Finds detected balloons without a BOM item.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.MEDIUM,
                    0.0,
                    "Every detected BOM balloon maps to a BOM item.",
                    "Level-3 visual evidence is unavailable.",
                    "The visual dependency has not run.",
                    "Run Level-3 visual analysis.",
                )
            ]
        if not balloons:
            return [
                finding(
                    self.rule_id,
                    "Orphan balloon",
                    "Finds detected balloons without a BOM item.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.MEDIUM,
                    1.0,
                    "Every detected BOM balloon maps to a BOM item.",
                    "No BOM balloon candidates were detected.",
                    "No orphan candidate can be assessed.",
                    "No action required.",
                )
            ]
        item_numbers = {normalized_identifier(item.value): item for item in items}
        results = []
        for balloon in balloons:
            item = item_numbers.get(normalized_identifier(balloon.value))
            evidence = [context.evidence(balloon)] + ([context.evidence(item)] if item else [])
            if item:
                status = (
                    RelationshipStatus.PASS
                    if balloon.confidence >= context.automatic_threshold
                    else RelationshipStatus.WARNING
                    if balloon.confidence >= context.partial_floor
                    else RelationshipStatus.MANUAL_REVIEW
                )
                context.graph.add_relationship(
                    RelationshipType.MATCHES,
                    balloon,
                    item,
                    status=status,
                    confidence=relationship_confidence(balloon, item),
                    evidence=evidence,
                    explanation=f"Balloon {balloon.value} maps to BOM item {item.value}.",
                )
                actual = f"Balloon {balloon.value} maps to BOM item {item.value}."
            else:
                status = (
                    RelationshipStatus.WARNING
                    if balloon.confidence >= context.partial_floor
                    else RelationshipStatus.MANUAL_REVIEW
                )
                context.graph.add_relationship(
                    RelationshipType.MISSING_LINK,
                    balloon,
                    None,
                    status=status,
                    confidence=balloon.confidence,
                    evidence=evidence,
                    explanation=f"Balloon {balloon.value} has no extracted BOM item.",
                )
                actual = f"Balloon {balloon.value} detected on sheet {balloon.page_number}, but no matching BOM item was found."
            results.append(
                finding(
                    self.rule_id,
                    f"Balloon {balloon.value} ↔ BOM item",
                    "Finds detected balloons without a BOM item.",
                    status,
                    RelationshipSeverity.MEDIUM,
                    balloon.confidence,
                    "Every detected BOM balloon maps to a BOM item.",
                    actual,
                    "The result uses only the detected balloon number and extracted BOM identifiers.",
                    "Review the highlighted balloon and BOM."
                    if status != RelationshipStatus.PASS
                    else "No action required.",
                    source=[balloon],
                    target=[item] if item else [],
                    evidence=evidence,
                    related_validation_rule_ids=["BOM-011", "XREF-007"],
                    discriminator=balloon.entity_id,
                )
            )
        return results


class BOMQuantityRule:
    rule_id = "REL-BOM-003"

    def evaluate(self, context: RelationshipContext):
        items = context.entities(EntityType.BOM_ITEM)
        balloons = context.entities(EntityType.BALLOON)
        if not items:
            return [
                finding(
                    self.rule_id,
                    "BOM quantity to drawing references",
                    "Compares BOM quantity with drawing references only when occurrence semantics are reliable.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.MEDIUM,
                    1.0,
                    "BOM quantities correspond to understood drawing occurrences.",
                    "No BOM items were extracted.",
                    "The relationship is not applicable.",
                    "No action required.",
                )
            ]
        by_number: dict[str, list] = {}
        for balloon in balloons:
            by_number.setdefault(normalized_identifier(balloon.value), []).append(balloon)

        results = []
        for item in items:
            expected_text = str(item.attributes.get("quantity") or "").strip()
            expected = int(expected_text) if expected_text.isdigit() else None
            matches = by_number.get(normalized_identifier(item.value), [])
            lower_values = [
                str(balloon.attributes.get("lower_compartment_text") or "").strip()
                for balloon in matches
            ]
            split_evidence_complete = bool(matches) and all(
                balloon.attributes.get("shape") == "split_circle" and value.isdigit()
                for balloon, value in zip(matches, lower_values, strict=True)
            )
            observed = (
                sum(int(value) for value in lower_values) if split_evidence_complete else None
            )
            evidence = [context.evidence(item)] + [
                context.evidence(balloon) for balloon in matches
            ]
            if expected is not None and observed is not None:
                agrees = expected == observed
                status = (
                    RelationshipStatus.MANUAL_REVIEW
                    if agrees
                    else RelationshipStatus.WARNING
                )
                actual = (
                    f"BOM quantity={expected}; visible lower-compartment total={observed} "
                    f"from values {lower_values}."
                )
                explanation = (
                    "The numeric comparison agrees, but the lower compartment's semantic "
                    "meaning must still be confirmed by an authorized reviewer."
                    if agrees
                    else "The visible numeric values differ; this is review assistance, not "
                    "proof of a BOM or drawing error."
                )
            else:
                status = RelationshipStatus.MANUAL_REVIEW
                actual = (
                    "Complete numeric lower-compartment evidence is unavailable for this item."
                )
                explanation = (
                    "Counting geometry or unlabeled callouts would not prove part-instance quantity."
                )
            results.append(
                finding(
                    self.rule_id,
                    f"BOM item {item.value} quantity review",
                    "Compares BOM quantity with explicit split-balloon lower-compartment text.",
                    status,
                    RelationshipSeverity.MEDIUM,
                    min([item.confidence, *[balloon.confidence for balloon in matches]]),
                    "BOM quantity corresponds to the visible split-balloon lower-compartment total after its convention is confirmed.",
                    actual,
                    explanation,
                    "Confirm the split-balloon convention and quantity comparison manually.",
                    source=[item],
                    target=matches,
                    evidence=evidence,
                    related_validation_rule_ids=["BOM-012"],
                    discriminator=item.entity_id,
                )
            )
        return results
