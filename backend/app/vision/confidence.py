"""Configurable Level-3 confidence gating."""

from __future__ import annotations

from enum import StrEnum

from backend.app.vision.models import VisualObject, VisualObjectType


class ConfidenceGate(StrEnum):
    AUTOMATIC = "AUTOMATIC"
    PARTIAL = "PARTIAL"
    HUMAN_REVIEW = "HUMAN_REVIEW"


DEFAULT_THRESHOLDS: dict[str, float] = {
    VisualObjectType.REVISION_TRIANGLE: 0.90,
    VisualObjectType.BOM_BALLOON: 0.90,
    VisualObjectType.SCC_SYMBOL: 0.92,
    VisualObjectType.CRITICAL_SYMBOL: 0.92,
    VisualObjectType.DATUM_SYMBOL: 0.90,
    VisualObjectType.GDT_FRAME: 0.90,
    VisualObjectType.VIEW_ARROW: 0.88,
    VisualObjectType.SECTION_ARROW: 0.88,
    VisualObjectType.DETAIL_CALLOUT: 0.88,
    VisualObjectType.FLAG_NOTE: 0.90,
    VisualObjectType.SUPPLIER_RASTER_TEXT: 0.90,
    VisualObjectType.UNKNOWN: 0.95,
}


def threshold_for(object_type: str, thresholds: dict[str, float] | None = None) -> float:
    configured = thresholds or DEFAULT_THRESHOLDS
    return float(configured.get(str(object_type), DEFAULT_THRESHOLDS[VisualObjectType.UNKNOWN]))


def gate_object(
    visual_object: VisualObject,
    thresholds: dict[str, float] | None = None,
    *,
    partial_floor: float = 0.75,
) -> ConfidenceGate:
    automatic = threshold_for(str(visual_object.object_type), thresholds)
    if visual_object.confidence >= automatic:
        return ConfidenceGate.AUTOMATIC
    if visual_object.confidence >= partial_floor:
        return ConfidenceGate.PARTIAL
    return ConfidenceGate.HUMAN_REVIEW
