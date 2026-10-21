"""Pydantic contracts for provenance-bearing Level-3 visual evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.drawing import BoundingBox


class VisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class VisualObjectType(StrEnum):
    REVISION_TRIANGLE = "REVISION_TRIANGLE"
    BOM_BALLOON = "BOM_BALLOON"
    SCC_SYMBOL = "SCC_SYMBOL"
    CRITICAL_SYMBOL = "CRITICAL_SYMBOL"
    DATUM_SYMBOL = "DATUM_SYMBOL"
    GDT_FRAME = "GDT_FRAME"
    VIEW_ARROW = "VIEW_ARROW"
    SECTION_ARROW = "SECTION_ARROW"
    DETAIL_CALLOUT = "DETAIL_CALLOUT"
    FLAG_NOTE = "FLAG_NOTE"
    SUPPLIER_RASTER_TEXT = "SUPPLIER_RASTER_TEXT"
    UNKNOWN = "UNKNOWN"


class SourceImageRegion(VisionModel):
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox
    dpi: int = Field(ge=72)


class VisualObject(VisionModel):
    object_id: str = Field(default_factory=lambda: str(uuid4()))
    object_type: VisualObjectType
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox
    polygon: list[tuple[float, float]] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    detector: str
    extraction_method: str = "visual_detection"
    raw_text: str | None = None
    normalized_text: str | None = None
    linked_text: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_image_region: SourceImageRegion | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> VisualObject:
        x0, y0, x1, y1 = self.bounding_box
        if x1 < x0 or y1 < y0:
            raise ValueError("bounding_box must satisfy x0 <= x1 and y0 <= y1")
        return self


class DetectorResult(VisionModel):
    detector_name: str
    objects: list[VisualObject] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    ocr_time_ms: float = Field(default=0.0, ge=0.0)


class VisionSummary(VisionModel):
    pages_processed: int = Field(ge=0)
    objects_detected: int = Field(ge=0)
    objects_by_type: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class VisionTiming(VisionModel):
    render_time_ms: float = Field(default=0.0, ge=0.0)
    detector_time_ms: dict[str, float] = Field(default_factory=dict)
    ocr_time_ms: float = Field(default=0.0, ge=0.0)
    total_time_ms: float = Field(default=0.0, ge=0.0)


class VisionReport(VisionModel):
    drawing_id: str | None = None
    source_filename: str
    level3_version: str = "1.1.0"
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    page_dimensions: dict[int, tuple[float, float]] = Field(default_factory=dict)
    detector_results: list[DetectorResult] = Field(default_factory=list)
    objects: list[VisualObject] = Field(default_factory=list)
    summary: VisionSummary
    timing: VisionTiming = Field(default_factory=VisionTiming)
    confidence_thresholds: dict[str, float] = Field(default_factory=dict)
    partial_confidence_floor: float = Field(default=0.75, ge=0.0, le=1.0)
    disclaimer: str = (
        "Visual detections are review assistance only and do not establish drawing "
        "correctness, ASME compliance, manufacturing readiness, or engineering approval."
    )


class ReviewAction(StrEnum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    CORRECT_LABEL = "CORRECT_LABEL"


class VisualReview(VisionModel):
    object_id: str
    action: ReviewAction
    corrected_label: str | None = None
    reviewer_comment: str | None = None
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_corrected_label(self) -> VisualReview:
        if self.action == ReviewAction.CORRECT_LABEL and not self.corrected_label:
            raise ValueError("corrected_label is required for CORRECT_LABEL")
        return self
