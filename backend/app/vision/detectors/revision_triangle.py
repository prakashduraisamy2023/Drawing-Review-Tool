"""Rule-based revision-triangle detector."""

from __future__ import annotations

import time

import cv2

from backend.app.vision.detectors.base import DetectorContext, VisualDetector, nearby_native_text
from backend.app.vision.models import DetectorResult, VisualObject, VisualObjectType
from backend.app.vision.preprocessing import edge_detection
from backend.app.vision.spatial import intersection_over_union


class RevisionTriangleDetector(VisualDetector):
    name = "revision_triangle"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            edges = edge_detection(page.image)
            contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            page_area = page.pdf_width * page.pdf_height
            for contour in contours:
                perimeter = cv2.arcLength(contour, True)
                if perimeter <= 0:
                    continue
                polygon = cv2.approxPolyDP(contour, 0.035 * perimeter, True)
                if len(polygon) != 3 or not cv2.isContourConvex(polygon):
                    continue
                x, y, width, height = cv2.boundingRect(polygon)
                pdf_box = page.pixel_to_pdf_bbox((x, y, x + width, y + height))
                pdf_width = pdf_box[2] - pdf_box[0]
                pdf_height = pdf_box[3] - pdf_box[1]
                area = abs(cv2.contourArea(contour)) / (page.x_scale * page.y_scale)
                if not (5 <= pdf_width <= 45 and 5 <= pdf_height <= 45):
                    continue
                if area / max(pdf_width * pdf_height, 1) < 0.22 or area > page_area * 0.002:
                    continue
                # Wrapper title blocks contain projection and logo geometry that should not
                # be interpreted as drawing-area revision markers.
                if pdf_box[0] > page.pdf_width * 0.68 and pdf_box[1] > page.pdf_height * 0.72:
                    continue
                text, _ = nearby_native_text(page, pdf_box, margin=10, pattern=r"[A-Z0-9]{1,3}")
                confidence = min(0.97, 0.79 + (0.14 if text else 0.0))
                points = [
                    (float(point[0][0]) / page.x_scale, float(point[0][1]) / page.y_scale)
                    for point in polygon
                ]
                candidate = VisualObject(
                    object_type=VisualObjectType.REVISION_TRIANGLE,
                    page_number=page_number,
                    bounding_box=pdf_box,
                    polygon=points,
                    confidence=confidence,
                    detector=self.name,
                    raw_text=text,
                    normalized_text=text.upper() if text else None,
                    linked_text=text,
                    attributes={"candidate_revision_identifier": text, "shape": "triangle"},
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
