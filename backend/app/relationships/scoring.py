"""Evidence confidence helpers for Level-4 matching."""

from __future__ import annotations

from backend.app.relationships.models import EngineeringEntity


def normalized_identifier(value: object) -> str:
    return "".join(str(value or "").upper().split())


def relationship_confidence(*entities: EngineeringEntity) -> float:
    scores = [entity.confidence for entity in entities if entity.confidence > 0]
    return min(scores) if scores else 0.0


def confidence_band(confidence: float, *, automatic: float = 0.90, partial: float = 0.75) -> str:
    if confidence >= automatic:
        return "AUTOMATIC"
    if confidence >= partial:
        return "PARTIAL"
    return "MANUAL"
