"""SCC detector framework requiring controlled client-specific symbol templates."""

from __future__ import annotations

import time

from backend.app.vision.detectors.base import DetectorContext, VisualDetector
from backend.app.vision.models import DetectorResult


class SCCSymbolDetector(VisualDetector):
    """Do not guess an SCC shape when no explicit reference symbol is supplied."""

    name = "scc_symbol"

    def __init__(self, templates: tuple[str, ...] = ()) -> None:
        self.templates = templates

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        if not self.templates:
            return DetectorResult(
                detector_name=self.name,
                warnings=[
                    "SCC detection not executed: no controlled SCC symbol template or manually "
                    "verified example is available."
                ],
                execution_time_ms=(time.perf_counter() - started) * 1000,
            )
        return DetectorResult(
            detector_name=self.name,
            warnings=[
                "Configured SCC template matching is reserved for a verified client template."
            ],
            execution_time_ms=(time.perf_counter() - started) * 1000,
        )
