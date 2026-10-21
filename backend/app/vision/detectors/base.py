"""Detector protocol and shared evidence-association helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.app.models.drawing import BoundingBox, DrawingDocument
from backend.app.vision.models import DetectorResult
from backend.app.vision.ocr import OCRProvider
from backend.app.vision.page_renderer import PageRenderer, RenderedPage
from backend.app.vision.spatial import center_distance, expand_bbox


@dataclass(frozen=True)
class DetectorContext:
    document: DrawingDocument
    renderer: PageRenderer
    ocr_provider: OCRProvider


class VisualDetector(ABC):
    name: str

    @abstractmethod
    def detect(self, context: DetectorContext) -> DetectorResult:
        raise NotImplementedError


def nearby_native_text(
    page: RenderedPage,
    bounding_box: BoundingBox,
    *,
    margin: float = 12.0,
    pattern: str | None = None,
) -> tuple[str | None, BoundingBox | None]:
    search = expand_bbox(bounding_box, margin)
    candidates = [
        word
        for word in page.native_words
        if word.bounding_box[2] >= search[0]
        and word.bounding_box[0] <= search[2]
        and word.bounding_box[3] >= search[1]
        and word.bounding_box[1] <= search[3]
        and (pattern is None or re.fullmatch(pattern, word.text, re.IGNORECASE))
    ]
    nearest = min(
        candidates,
        key=lambda word: center_distance(bounding_box, word.bounding_box),
        default=None,
    )
    return (nearest.text, nearest.bounding_box) if nearest else (None, None)
