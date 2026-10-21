"""Configured part-number relationship framework."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import EntityType, RelationshipSeverity, RelationshipStatus
from backend.app.relationships.rules.base import finding


class PartNumberRule:
    rule_id = "REL-PART-001"

    def evaluate(self, context: RelationshipContext):
        items = (
            context.entities(EntityType.BOM_ITEM)
            + context.entities(EntityType.PART_LIST_ITEM)
            + context.entities(EntityType.SERVICE_PART)
            + context.entities(EntityType.SUPPLIER_PART)
        )
        configured = context.configuration.get("part_number_mappings", [])
        if not items:
            status = RelationshipStatus.NOT_APPLICABLE
            actual = "No BOM, part-list, service-part, or supplier-part entities are available."
        elif not configured:
            status = RelationshipStatus.MANUAL_REVIEW
            actual = f"{len(items)} part-related entities are available, but no authoritative mapping rules are configured."
        else:
            status = RelationshipStatus.MANUAL_REVIEW
            actual = "Configured mapping data exists; generic, instance, LH/RH, and supplier mapping semantics still require controlled client values."
        return [
            finding(
                self.rule_id,
                "Part number relationships",
                "Relates title, table, supplier, and note part numbers using explicit configured mapping semantics.",
                status,
                RelationshipSeverity.MEDIUM,
                min((item.confidence for item in items), default=0.0),
                "Part-number families are compared only under an authoritative configured mapping.",
                actual,
                "The system does not assume that all part numbers should be identical.",
                "Provide or review the controlled part-number mapping rules.",
                source=items,
                evidence=[context.evidence(item) for item in items],
                related_validation_rule_ids=["XREF-001", "XREF-002"],
            )
        ]
