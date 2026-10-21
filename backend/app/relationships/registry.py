"""Controlled Level-4 relationship rule registry."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from backend.app.relationships.context import RelationshipContext
from backend.app.relationships.models import RelationshipResult


class RelationshipRule(Protocol):
    rule_id: str

    def evaluate(self, context: RelationshipContext) -> list[RelationshipResult]: ...


class RelationshipRegistry:
    def __init__(self, rules: Iterable[RelationshipRule] = ()) -> None:
        self._rules: dict[str, RelationshipRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: RelationshipRule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"Duplicate relationship rule ID: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def __iter__(self) -> Iterable[RelationshipRule]:
        return iter(self._rules.values())


def build_default_registry() -> RelationshipRegistry:
    from backend.app.relationships.rules.bom_relationships import (
        BOMBalloonRule,
        BOMQuantityRule,
        OrphanBalloonRule,
    )
    from backend.app.relationships.rules.datum_gdt_relationships import (
        DatumGdtRule,
        DatumUsageRule,
    )
    from backend.app.relationships.rules.document_relationships import CrossSheetRule
    from backend.app.relationships.rules.note_relationships import NoteCalloutRule
    from backend.app.relationships.rules.part_relationships import PartNumberRule
    from backend.app.relationships.rules.revision_relationships import (
        RevisionRelationshipRule,
        RevisionTraceabilityRule,
    )
    from backend.app.relationships.rules.scc_relationships import SCCRelationshipRule
    from backend.app.relationships.rules.supplier_relationships import SupplierRelationshipRule

    return RelationshipRegistry(
        [
            BOMBalloonRule(),
            OrphanBalloonRule(),
            BOMQuantityRule(),
            RevisionRelationshipRule(),
            RevisionTraceabilityRule(),
            NoteCalloutRule(),
            SCCRelationshipRule(),
            DatumGdtRule(),
            DatumUsageRule(),
            SupplierRelationshipRule(),
            PartNumberRule(),
            CrossSheetRule(),
        ]
    )
