"""Conservative SCC relationship framework."""

# ruff: noqa: E501 - controlled relationship wording remains readable.

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import EntityType, RelationshipSeverity, RelationshipStatus
from backend.app.relationships.rules.base import finding


class SCCRelationshipRule:
    rule_id = "REL-SCC-001"

    def evaluate(self, context: RelationshipContext):
        symbols = context.entities(EntityType.SCC_SYMBOL)
        if context.vision_report is None:
            status = RelationshipStatus.NOT_EVALUATED
            actual = "Level-3 visual analysis has not been run."
        elif not symbols:
            status = RelationshipStatus.NOT_EVALUATED
            actual = "No controlled SCC symbol evidence is available."
        else:
            status = RelationshipStatus.MANUAL_REVIEW
            actual = f"{len(symbols)} SCC/critical symbol candidate(s) require client-rule semantic association."
        return [
            finding(
                self.rule_id,
                "SCC ↔ note/BOM/callout",
                "Links controlled SCC evidence to its governing note, BOM item, or callout only when client semantics are configured.",
                status,
                RelationshipSeverity.CRITICAL,
                min((item.confidence for item in symbols), default=0.0),
                "SCC symbols are associated using configured client semantics.",
                actual,
                "The system does not assume that every critical symbol has the same meaning.",
                "Supply or apply the approved SCC symbol reference and client relationship rules.",
                source=symbols,
                evidence=[context.evidence(item) for item in symbols],
                related_validation_rule_ids=["BOM-014", "XREF-006"],
            )
        ]
