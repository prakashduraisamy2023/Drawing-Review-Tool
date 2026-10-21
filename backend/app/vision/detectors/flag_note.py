"""Flag-note detector using triangle geometry plus an internal numeric token."""

from __future__ import annotations

import time

import cv2

from backend.app.vision.detectors.base import DetectorContext, VisualDetector, nearby_native_text
from backend.app.vision.models import DetectorResult, VisualObject, VisualObjectType
from backend.app.vision.preprocessing import edge_detection
from backend.app.vision.spatial import intersection_over_union


class FlagNoteDetector(VisualDetector):
    name = "flag_note"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            edges = edge_detection(page.image)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                if perimeter <= 0:
                    continue
                polygon = cv2.approxPolyDP(contour, 0.035 * perimeter, True)
                if len(polygon) != 3 or not cv2.isContourConvex(polygon):
                    continue
                x, y, width, height = cv2.boundingRect(polygon)
                pdf_box = page.pixel_to_pdf_bbox((x, y, x + width, y + height))
                pdf_width, pdf_height = pdf_box[2] - pdf_box[0], pdf_box[3] - pdf_box[1]
                if not (5 <= pdf_width <= 36 and 5 <= pdf_height <= 36):
                    continue
                note_number, _ = nearby_native_text(page, pdf_box, margin=3, pattern=r"\d{1,3}")
                if not note_number:
                    continue
                candidate = VisualObject(
                    object_type=VisualObjectType.FLAG_NOTE,
                    page_number=page_number,
                    bounding_box=pdf_box,
                    confidence=0.93,
                    detector=self.name,
                    raw_text=note_number,
                    normalized_text=note_number,
                    linked_text=note_number,
                    attributes={"note_number": note_number, "shape": "triangle"},
                )
                if not any(
                    intersection_over_union(candidate.bounding_box, existing.bounding_box) > 0.65
                    for existing in objects
                    if existing.page_number == page_number
                ):
                    objects.append(candidate)
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            execution_time_ms=(time.perf_counter() - started) * 1000,
        )
