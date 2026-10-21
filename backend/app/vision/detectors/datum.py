"""Conservative datum-feature-symbol detector."""

from __future__ import annotations

import time

import cv2

from backend.app.vision.detectors.base import DetectorContext, VisualDetector, nearby_native_text
from backend.app.vision.models import DetectorResult, VisualObject, VisualObjectType
from backend.app.vision.preprocessing import adaptive_threshold
from backend.app.vision.spatial import intersection_over_union


class DatumDetector(VisualDetector):
    name = "datum"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            binary = adaptive_threshold(page.image, block_size=31, c=11)
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                if perimeter <= 0:
                    continue
                polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
                if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                    continue
                x, y, width, height = cv2.boundingRect(polygon)
                pdf_box = page.pixel_to_pdf_bbox((x, y, x + width, y + height))
                pdf_width, pdf_height = pdf_box[2] - pdf_box[0], pdf_box[3] - pdf_box[1]
                if not (6 <= pdf_width <= 32 and 6 <= pdf_height <= 24):
                    continue
                if not 0.55 <= pdf_width / max(pdf_height, 0.1) <= 2.2:
                    continue
                identifier, _ = nearby_native_text(
                    page, pdf_box, margin=1.5, pattern=r"[A-Z](?:\d{1,2})?"
                )
                if not identifier:
                    continue
                # Require a line touching the box to distinguish boxed datum labels from
                # ordinary table cells and title-block text.
                margin = round(max(width, height) * 0.75)
                x0, y0 = max(0, x - margin), max(0, y - margin)
                x1 = min(binary.shape[1], x + width + margin)
                y1 = min(binary.shape[0], y + height + margin)
                region = binary[y0:y1, x0:x1]
                lines = cv2.HoughLinesP(
                    region,
                    1,
                    3.14159 / 180,
                    threshold=18,
                    minLineLength=max(8, width // 2),
                    maxLineGap=4,
                )
                if lines is None:
                    continue
                candidate = VisualObject(
                    object_type=VisualObjectType.DATUM_SYMBOL,
                    page_number=page_number,
                    bounding_box=pdf_box,
                    confidence=0.91,
                    detector=self.name,
                    raw_text=identifier,
                    normalized_text=identifier.upper(),
                    linked_text=identifier.upper(),
                    attributes={"identifier": identifier.upper(), "context": "CALLOUT"},
                )
                if not any(
                    intersection_over_union(candidate.bounding_box, existing.bounding_box) > 0.70
                    for existing in objects
                    if existing.page_number == page_number
                ):
                    objects.append(candidate)
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            execution_time_ms=(time.perf_counter() - started) * 1000,
        )
