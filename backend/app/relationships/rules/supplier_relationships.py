"""Native supplier evidence to targeted OCR relationships."""

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


class SupplierRelationshipRule:
    rule_id = "REL-SUP-001"

    def evaluate(self, context: RelationshipContext):
        suppliers = context.entities(EntityType.SUPPLIER)
        parts = context.entities(EntityType.SUPPLIER_PART)
        ocr = [
            item
            for item in context.entities(EntityType.VISUAL_OBJECT)
            if item.attributes.get("visual_object_type") == "SUPPLIER_RASTER_TEXT"
        ]
        if not suppliers and not parts:
            return [
                finding(
                    self.rule_id,
                    "Supplier wrapper ↔ supplier original",
                    "Compares native wrapper supplier identifiers with acceptable-confidence targeted OCR without overwriting either source.",
                    RelationshipStatus.NOT_APPLICABLE,
                    RelationshipSeverity.MEDIUM,
                    1.0,
                    "Applicable supplier identifiers are traceable across wrapper and supplier-original evidence.",
                    "No supplier name or supplier part number was extracted.",
                    "The relationship is not applicable.",
                    "No action required.",
                )
            ]
        reliable_ocr = [item for item in ocr if item.confidence >= context.automatic_threshold]
        if not reliable_ocr:
            return [
                finding(
                    self.rule_id,
                    "Supplier wrapper ↔ supplier original",
                    "Compares native wrapper supplier identifiers with acceptable-confidence targeted OCR without overwriting either source.",
                    RelationshipStatus.NOT_EVALUATED,
                    RelationshipSeverity.HIGH,
                    0.0,
                    "Native wrapper supplier identifiers can be compared with acceptable-confidence supplier-original OCR.",
                    "No supplier raster OCR region meets the automatic confidence threshold.",
                    "Native evidence remains authoritative and has not been overwritten.",
                    "Enable/configure local OCR and review the supplier original.",
                    source=suppliers + parts,
                    target=ocr,
                    evidence=[context.evidence(item) for item in suppliers + parts + ocr],
                    related_validation_rule_ids=["SUP-010"],
                )
            ]
        text = " ".join(str(item.value or "") for item in reliable_ocr).upper()
        expected = suppliers + parts
        unmatched = [
            item
            for item in expected
            if normalized_identifier(item.value) not in normalized_identifier(text)
        ]
        status = RelationshipStatus.WARNING if unmatched else RelationshipStatus.PASS
        for item in expected:
            target = next(
                (
                    candidate
                    for candidate in reliable_ocr
                    if normalized_identifier(item.value) in normalized_identifier(candidate.value)
                ),
                None,
            )
            context.graph.add_relationship(
                RelationshipType.MATCHES if target else RelationshipType.MISSING_LINK,
                item,
                target,
                status=RelationshipStatus.PASS if target else RelationshipStatus.WARNING,
                confidence=relationship_confidence(item, target) if target else item.confidence,
                evidence=[context.evidence(item)] + ([context.evidence(target)] if target else []),
                explanation=f"Supplier value {item.value} {'appears' if target else 'does not appear'} in acceptable-confidence OCR evidence.",
            )
        return [
            finding(
                self.rule_id,
                "Supplier wrapper ↔ supplier original",
                "Compares native wrapper supplier identifiers with acceptable-confidence targeted OCR without overwriting either source.",
                status,
                RelationshipSeverity.HIGH,
                min((item.confidence for item in reliable_ocr), default=0.0),
                "Applicable native supplier identifiers appear in acceptable-confidence supplier-original OCR.",
                f"Unmatched native supplier values={[item.value for item in unmatched]}.",
                "OCR is compared as a separate evidence source and never replaces native wrapper information.",
                "Review unmatched supplier identifiers." if unmatched else "No action required.",
                source=expected,
                target=reliable_ocr,
                evidence=[context.evidence(item) for item in expected + reliable_ocr],
                related_validation_rule_ids=["SUP-010"],
            )
        ]
