"""Fault-isolated orchestration for the independent Level-3 visual layer."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path

import cv2

from backend.app.config import Settings, get_settings
from backend.app.models.drawing import DrawingDocument
from backend.app.vision.confidence import DEFAULT_THRESHOLDS, threshold_for
from backend.app.vision.detectors.base import DetectorContext
from backend.app.vision.models import (
    DetectorResult,
    VisionReport,
    VisionSummary,
    VisionTiming,
)
from backend.app.vision.ocr import OCRProvider, build_ocr_provider
from backend.app.vision.page_renderer import PageRenderer
from backend.app.vision.registry import DetectorRegistry, build_default_registry

logger = logging.getLogger(__name__)


def _configured_thresholds() -> dict[str, float]:
    path = Path(__file__).resolve().parents[3] / "config" / "vision.yaml"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        configured = payload.get("confidence_thresholds", {})
        return {str(key): float(value) for key, value in configured.items()}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Unable to load %s; using built-in visual thresholds.", path)
        return dict(DEFAULT_THRESHOLDS)


def _configured_partial_floor() -> float:
    path = Path(__file__).resolve().parents[3] / "config" / "vision.yaml"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("partial_confidence_floor", 0.75))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Unable to load partial confidence floor from %s; using 0.75.", path)
        return 0.75


class VisionEngine:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        registry: DetectorRegistry | None = None,
        ocr_provider: OCRProvider | None = None,
        confidence_thresholds: dict[str, float] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or build_default_registry()
        self.ocr_provider = ocr_provider or build_ocr_provider(
            enabled=self.settings.ocr_enabled,
            name=self.settings.ocr_provider,
        )
        self.confidence_thresholds = confidence_thresholds or _configured_thresholds()
        self.partial_confidence_floor = _configured_partial_floor()

    def analyze(
        self,
        pdf_path: str | Path,
        document: DrawingDocument,
        *,
        drawing_id: str | None = None,
        debug_directory: str | Path | None = None,
    ) -> VisionReport:
        started = time.perf_counter()
        if not self.settings.level3_enabled:
            return VisionReport(
                drawing_id=drawing_id,
                source_filename=str(document.source_filename.value or Path(pdf_path).name),
                enabled=False,
                summary=VisionSummary(
                    pages_processed=0,
                    objects_detected=0,
                    low_confidence_count=0,
                    warnings=["Level 3 is disabled by configuration."],
                ),
                confidence_thresholds=self.confidence_thresholds,
                partial_confidence_floor=self.partial_confidence_floor,
            )

        detector_results: list[DetectorResult] = []
        objects = []
        warnings: list[str] = []
        page_dimensions: dict[int, tuple[float, float]] = {}
        with PageRenderer(pdf_path, dpi=self.settings.vision_dpi) as renderer:
            context = DetectorContext(
                document=document, renderer=renderer, ocr_provider=self.ocr_provider
            )
            for detector in self.registry:
                try:
                    result = detector.detect(context)
                except Exception as exc:  # one detector must never abort Level 3
                    logger.exception("vision_detector_exception detector=%s", detector.name)
                    result = DetectorResult(
                        detector_name=detector.name,
                        warnings=[f"Technical detector failure: {type(exc).__name__}."],
                    )
                detector_results.append(result)
                objects.extend(result.objects)
                warnings.extend(f"{result.detector_name}: {warning}" for warning in result.warnings)
            for page_number in range(1, renderer.page_count + 1):
                rendered = renderer.render_page(page_number)
                page_dimensions[page_number] = (rendered.pdf_width, rendered.pdf_height)
            render_time_ms = renderer.render_time_ms
            if debug_directory is not None:
                self._write_debug_overlays(renderer, objects, Path(debug_directory))

        counts = Counter(str(item.object_type) for item in objects)
        low_confidence = sum(
            item.confidence < threshold_for(str(item.object_type), self.confidence_thresholds)
            for item in objects
        )
        total_ms = (time.perf_counter() - started) * 1000
        return VisionReport(
            drawing_id=drawing_id,
            source_filename=str(document.source_filename.value or Path(pdf_path).name),
            page_dimensions=page_dimensions,
            detector_results=detector_results,
            objects=objects,
            summary=VisionSummary(
                pages_processed=len(page_dimensions),
                objects_detected=len(objects),
                objects_by_type=dict(sorted(counts.items())),
                low_confidence_count=low_confidence,
                warnings=warnings,
            ),
            timing=VisionTiming(
                render_time_ms=render_time_ms,
                detector_time_ms={
                    result.detector_name: result.execution_time_ms for result in detector_results
                },
                ocr_time_ms=sum(result.ocr_time_ms for result in detector_results),
                total_time_ms=total_ms,
            ),
            confidence_thresholds=self.confidence_thresholds,
            partial_confidence_floor=self.partial_confidence_floor,
        )

    @staticmethod
    def _write_debug_overlays(
        renderer: PageRenderer,
        objects: list[object],
        directory: Path,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for page_number in range(1, renderer.page_count + 1):
            rendered = renderer.render_page(page_number)
            overlay = rendered.image.copy()
            for item in objects:
                if getattr(item, "page_number", None) != page_number:
                    continue
                x0, y0, x1, y1 = rendered.pdf_to_pixel_bbox(item.bounding_box)
                cv2.rectangle(overlay, (x0, y0), (x1, y1), (20, 80, 230), 2)
                label = f"{item.object_type}:{item.confidence:.2f}"
                cv2.putText(
                    overlay,
                    label,
                    (x0, max(12, y0 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (20, 80, 230),
                    1,
                    cv2.LINE_AA,
                )
            cv2.imwrite(str(directory / f"page_{page_number}_level3_overlay.png"), overlay)
