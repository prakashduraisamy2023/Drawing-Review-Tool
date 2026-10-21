"""Controlled Level-3 detector registry."""

from __future__ import annotations

from collections.abc import Iterable

from backend.app.vision.detectors import (
    BalloonDetector,
    DatumDetector,
    FlagNoteDetector,
    GDTFrameDetector,
    RevisionTriangleDetector,
    SCCSymbolDetector,
    SupplierRasterOCRDetector,
    ViewAnnotationDetector,
)
from backend.app.vision.detectors.base import VisualDetector


class DetectorRegistry:
    def __init__(self, detectors: Iterable[VisualDetector] = ()) -> None:
        self._detectors: dict[str, VisualDetector] = {}
        for detector in detectors:
            self.register(detector)

    def register(self, detector: VisualDetector) -> None:
        if detector.name in self._detectors:
            raise ValueError(f"Duplicate visual detector: {detector.name}")
        self._detectors[detector.name] = detector

    def __iter__(self) -> Iterable[VisualDetector]:
        return iter(self._detectors.values())

    def names(self) -> list[str]:
        return list(self._detectors)


def build_default_registry() -> DetectorRegistry:
    return DetectorRegistry(
        [
            RevisionTriangleDetector(),
            BalloonDetector(),
            SCCSymbolDetector(),
            DatumDetector(),
            GDTFrameDetector(),
            ViewAnnotationDetector(),
            FlagNoteDetector(),
            SupplierRasterOCRDetector(),
        ]
    )
