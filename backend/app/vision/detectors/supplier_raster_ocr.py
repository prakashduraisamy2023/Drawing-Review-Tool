"""Targeted OCR for Level-1 supplier raster regions only."""

from __future__ import annotations

import time

from backend.app.vision.detectors.base import DetectorContext, VisualDetector
from backend.app.vision.models import (
    DetectorResult,
    SourceImageRegion,
    VisualObject,
    VisualObjectType,
)
from backend.app.vision.preprocessing import deskew_crop, normalize_contrast, upscale_crop


class SupplierRasterOCRDetector(VisualDetector):
    name = "supplier_raster_ocr"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        warnings: list[str] = []
        ocr_time = 0.0
        regions = context.document.supplier_raster_regions
        if not regions:
            return DetectorResult(
                detector_name=self.name,
                execution_time_ms=(time.perf_counter() - started) * 1000,
            )
        if not context.ocr_provider.available:
            state = (
                "OCR is disabled by configuration."
                if context.ocr_provider.name == "disabled"
                else f"OCR provider {context.ocr_provider.name!r} is unavailable."
            )
            return DetectorResult(
                detector_name=self.name,
                warnings=[state],
                execution_time_ms=(time.perf_counter() - started) * 1000,
            )
        for region in regions:
            crop = context.renderer.render_crop(region.page_number, region.bounding_box, dpi=400)
            prepared = upscale_crop(deskew_crop(normalize_contrast(crop.image)), 1.25)
            result = context.ocr_provider.recognize(prepared)
            ocr_time += result.execution_time_ms
            warnings.extend(result.warnings)
            if not result.words:
                warnings.append(
                    f"No OCR words were recovered from supplier raster page {region.page_number}."
                )
                continue
            # The provider sees an upscaled image, so map its word coordinates back before
            # converting them into the original PDF coordinate system.
            word_boxes = []
            for word in result.words:
                scaled = tuple(round(value / 1.25) for value in word.pixel_bounding_box)
                word_boxes.append(crop.pixel_to_pdf_bbox(scaled))
            pdf_box = (
                min(box[0] for box in word_boxes),
                min(box[1] for box in word_boxes),
                max(box[2] for box in word_boxes),
                max(box[3] for box in word_boxes),
            )
            confidence = min(
                0.89, sum(word.confidence for word in result.words) / len(result.words)
            )
            objects.append(
                VisualObject(
                    object_type=VisualObjectType.SUPPLIER_RASTER_TEXT,
                    page_number=region.page_number,
                    bounding_box=pdf_box,
                    confidence=confidence,
                    detector=self.name,
                    extraction_method="TARGETED_OCR",
                    raw_text=result.raw_text,
                    normalized_text=result.raw_text.strip() or None,
                    linked_text="supplier-original raster region",
                    attributes={
                        "ocr_provider": context.ocr_provider.name,
                        "word_count": len(result.words),
                        "word_boxes": word_boxes,
                        "layout_groups": [result.raw_text],
                    },
                    source_image_region=SourceImageRegion(
                        page_number=region.page_number,
                        bounding_box=region.bounding_box,
                        dpi=400,
                    ),
                )
            )
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            warnings=list(dict.fromkeys(warnings)),
            execution_time_ms=(time.perf_counter() - started) * 1000,
            ocr_time_ms=ocr_time,
        )
