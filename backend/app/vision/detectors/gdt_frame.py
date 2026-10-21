"""Feature-control-frame localization and conservative token recovery."""

from __future__ import annotations

import re
import time

import cv2

from backend.app.vision.detectors.base import DetectorContext, VisualDetector
from backend.app.vision.models import (
    DetectorResult,
    SourceImageRegion,
    VisualObject,
    VisualObjectType,
)
from backend.app.vision.preprocessing import adaptive_threshold, upscale_crop
from backend.app.vision.spatial import center, contains, intersection_over_union


class GDTFrameDetector(VisualDetector):
    name = "gdt_frame"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        warnings: list[str] = []
        ocr_time = 0.0
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            binary = adaptive_threshold(page.image, block_size=31, c=11)
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                if perimeter <= 0:
                    continue
                polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
                if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                    continue
                x, y, width, height = cv2.boundingRect(polygon)
                pdf_box = page.pixel_to_pdf_bbox((x, y, x + width, y + height))
                pdf_width, pdf_height = pdf_box[2] - pdf_box[0], pdf_box[3] - pdf_box[1]
                if not (18 <= pdf_width <= 220 and 5 <= pdf_height <= 32):
                    continue
                if pdf_width / max(pdf_height, 0.1) < 1.8:
                    continue
                candidate_center = center(pdf_box)
                table_regions = [
                    item.bounding_box
                    for item in (context.document.bom or [])
                    if item.bounding_box is not None and item.page_number == page_number
                ]
                if any(
                    region[0] <= candidate_center[0] <= region[2]
                    and region[1] <= candidate_center[1] <= region[3]
                    for region in table_regions
                ):
                    continue
                if pdf_box[1] < 60 or pdf_box[3] > page.pdf_height - 60:
                    continue
                crop = binary[
                    max(0, y) : min(binary.shape[0], y + height),
                    max(0, x) : min(binary.shape[1], x + width),
                ]
                if crop.size == 0:
                    continue
                column_density = (crop > 0).mean(axis=0)
                separator_columns = column_density > 0.62
                separator_groups = 0
                active = False
                for value in separator_columns:
                    if value and not active:
                        separator_groups += 1
                    active = bool(value)
                # Outer borders account for two groups; at least one internal separator is required.
                if separator_groups < 3:
                    continue
                native = [
                    word for word in page.native_words if contains(pdf_box, word.bounding_box)
                ]
                tokens = [
                    word.text for word in sorted(native, key=lambda item: item.bounding_box[0])
                ]
                extraction_method = "native_text_visual_frame"
                source_region = None
                if not tokens and context.ocr_provider.available:
                    high_res = context.renderer.render_crop(page_number, pdf_box, dpi=450)
                    ocr = context.ocr_provider.recognize(upscale_crop(high_res.image, 1.5))
                    ocr_time += ocr.execution_time_ms
                    tokens = [word.text for word in ocr.words]
                    extraction_method = "targeted_ocr"
                    source_region = SourceImageRegion(
                        page_number=page_number, bounding_box=pdf_box, dpi=450
                    )
                    warnings.extend(ocr.warnings)
                if not tokens:
                    continue
                raw_text = " | ".join(tokens) if tokens else None
                tolerance = next(
                    (token for token in tokens if re.fullmatch(r"(?:Ø|⌀)?\d*\.\d+", token)), None
                )
                datums = [
                    token.upper() for token in tokens if re.fullmatch(r"[A-Z](?:\d{1,2})?", token)
                ]
                characteristic = (
                    tokens[0] if tokens and not re.fullmatch(r"[A-Z0-9.]+", tokens[0]) else None
                )
                confidence = 0.91 if tokens else 0.79
                candidate = VisualObject(
                    object_type=VisualObjectType.GDT_FRAME,
                    page_number=page_number,
                    bounding_box=pdf_box,
                    confidence=confidence,
                    detector=self.name,
                    extraction_method=extraction_method,
                    raw_text=raw_text,
                    normalized_text=raw_text,
                    linked_text=raw_text,
                    attributes={
                        "cells": tokens,
                        "recognized_tokens": tokens,
                        "characteristic": characteristic,
                        "tolerance": tolerance,
                        "diameter_modifier": any("Ø" in token or "⌀" in token for token in tokens),
                        "material_condition": next(
                            (
                                token
                                for token in tokens
                                if token in {"M", "L", "S", "MMC", "LMC", "RFS"}
                            ),
                            None,
                        ),
                        "datum_sequence": datums,
                        "token_confidence": 0.91 if tokens else 0.0,
                    },
                    source_image_region=source_region,
                )
                if not any(
                    intersection_over_union(candidate.bounding_box, existing.bounding_box) > 0.72
                    for existing in objects
                    if existing.page_number == page_number
                ):
                    objects.append(candidate)
        if ocr_time:
            warnings.append(f"OCR execution time: {ocr_time:.3f} ms")
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            warnings=list(dict.fromkeys(warnings)),
            execution_time_ms=(time.perf_counter() - started) * 1000,
            ocr_time_ms=ocr_time,
        )
