"""Small deterministic in-memory engineering relationship graph."""

from __future__ import annotations

from hashlib import sha1

from backend.app.relationships.models import (
    EngineeringEntity,
    EngineeringRelationship,
    RelationshipEvidence,
    RelationshipGraph,
    RelationshipStatus,
    RelationshipType,
)


def stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return f"{prefix}-{sha1(payload.encode('utf-8')).hexdigest()[:14]}"


class EngineeringGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, EngineeringEntity] = {}
        self._edges: dict[str, EngineeringRelationship] = {}

    def add_entity(self, entity: EngineeringEntity) -> EngineeringEntity:
        self._nodes[entity.entity_id] = entity
        return entity

    def add_relationship(
        self,
        relationship_type: RelationshipType,
        source: EngineeringEntity,
        target: EngineeringEntity | None,
        *,
        status: RelationshipStatus,
        confidence: float,
        evidence: list[RelationshipEvidence],
        explanation: str,
    ) -> EngineeringRelationship:
        edge = EngineeringRelationship(
            relationship_id=stable_id(
                "rel",
                relationship_type,
                source.entity_id,
                target.entity_id if target else "missing",
                explanation,
            ),
            relationship_type=relationship_type,
            source_entity_id=source.entity_id,
            target_entity_id=target.entity_id if target else None,
            status=status,
            confidence=confidence,
            evidence=evidence,
            explanation=explanation,
        )
        self._edges[edge.relationship_id] = edge
        return edge

    def entities(self, entity_type: str | None = None) -> list[EngineeringEntity]:
        nodes = list(self._nodes.values())
        return (
            nodes
            if entity_type is None
            else [node for node in nodes if node.entity_type == entity_type]
        )

    def export(self) -> RelationshipGraph:
        return RelationshipGraph(
            nodes=sorted(self._nodes.values(), key=lambda item: item.entity_id),
            edges=sorted(self._edges.values(), key=lambda item: item.relationship_id),
        )
