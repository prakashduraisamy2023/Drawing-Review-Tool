"""BOM balloon shape detection with native-text/OCR evidence fusion."""

from __future__ import annotations

import math
import re
import time

import cv2
import numpy as np

from backend.app.vision.detectors.base import (
    DetectorContext,
    VisualDetector,
    nearby_native_text,
)
from backend.app.vision.models import DetectorResult, VisualObject, VisualObjectType
from backend.app.vision.page_renderer import RenderedPage
from backend.app.vision.preprocessing import adaptive_threshold
from backend.app.vision.spatial import intersection_over_union

_ITEM_TOKEN = re.compile(r"\d{1,4}")


def _deduplicated_append(objects: list[VisualObject], candidate: VisualObject) -> None:
    if not any(
        intersection_over_union(candidate.bounding_box, existing.bounding_box) > 0.70
        for existing in objects
        if existing.page_number == candidate.page_number
    ):
        objects.append(candidate)


def _aligned_split_tokens(page: RenderedPage):
    """Yield vertically stacked numeric tokens that can occupy a split balloon.

    This is only a text-geometry proposal stage. A circular image boundary is
    still required before a visual object is emitted, which rejects stacked BOM
    table cells and ordinary drawing dimensions.
    """

    numeric_words = [word for word in page.native_words if _ITEM_TOKEN.fullmatch(word.text)]
    for upper in numeric_words:
        upper_x = (upper.bounding_box[0] + upper.bounding_box[2]) / 2
        upper_height = upper.bounding_box[3] - upper.bounding_box[1]
        if upper_height <= 0:
            continue
        for lower in numeric_words:
            vertical_offset = lower.bounding_box[1] - upper.bounding_box[1]
            if not (0.45 * upper_height <= vertical_offset <= 0.90 * upper_height):
                continue
            lower_x = (lower.bounding_box[0] + lower.bounding_box[2]) / 2
            lower_height = lower.bounding_box[3] - lower.bounding_box[1]
            if abs(lower_x - upper_x) > max(2.5, 0.18 * upper_height):
                continue
            if not (0.82 * upper_height <= lower_height <= 1.18 * upper_height):
                continue
            yield upper, lower


def _circle_boundary(
    page: RenderedPage,
    text_box: tuple[float, float, float, float],
    edge_distance: np.ndarray,
) -> tuple[tuple[float, float, float, float] | None, float]:
    """Locate a mostly circular boundary around a split text pair.

    Leaders frequently touch the balloon boundary and merge its contour with a
    long line. Circumference coverage remains stable in that case, so this check
    samples Canny-edge proximity around plausible circles instead of requiring a
    closed contour.
    """

    x0, y0, x1, y1 = text_box
    text_height = y1 - y0
    center_x = (x0 + x1) / 2
    center_y = (y0 + y1) / 2
    angles = np.linspace(0, 2 * math.pi, 144, endpoint=False)
    cosines = np.cos(angles)
    sines = np.sin(angles)
    best_score = 0.0
    best_circle: tuple[float, float, float] | None = None
    # Native font boxes in these drawings overlap across the separator, so the
    # combined text height can be close to the full diameter or even exceed it.
    minimum_radius = max(8.0, text_height * 0.35)
    maximum_radius = min(25.0, text_height * 0.80)
    if maximum_radius < minimum_radius:
        return None, 0.0

    for offset_x in (-2.0, 0.0, 2.0):
        for offset_y in (-2.0, 0.0, 2.0):
            candidate_x = center_x + offset_x
            candidate_y = center_y + offset_y
            for radius in np.arange(minimum_radius, maximum_radius + 0.1, 1.0):
                sample_x = np.rint((candidate_x + radius * cosines) * page.x_scale).astype(int)
                sample_y = np.rint((candidate_y + radius * sines) * page.y_scale).astype(int)
                if (
                    sample_x.min() < 0
                    or sample_y.min() < 0
                    or sample_x.max() >= edge_distance.shape[1]
                    or sample_y.max() >= edge_distance.shape[0]
                ):
                    continue
                near_edge = edge_distance[sample_y, sample_x] <= max(
                    2.0, 0.8 * max(page.x_scale, page.y_scale)
                )
                quadrant_scores = [
                    float(near_edge[index : index + 36].mean())
                    for index in range(0, 144, 36)
                ]
                coverage = float(near_edge.mean())
                score = min(coverage, min(quadrant_scores) + 0.18)
                if score > best_score:
                    best_score = score
                    best_circle = (candidate_x, candidate_y, float(radius))

    if best_circle is None or best_score < 0.78:
        return None, best_score
    circle_x, circle_y, radius = best_circle
    return (
        circle_x - radius,
        circle_y - radius,
        circle_x + radius,
        circle_y + radius,
    ), best_score


class BalloonDetector(VisualDetector):
    name = "balloon"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        warnings: list[str] = []
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            # Split balloons are detected first so their upper item token wins
            # over the lower compartment when the enclosing contour is also found.
            split_pairs = list(_aligned_split_tokens(page))
            edge_distance = None
            if split_pairs:
                edges = cv2.Canny(cv2.cvtColor(page.image, cv2.COLOR_BGR2GRAY), 80, 180)
                edge_distance = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)
            for upper, lower in split_pairs:
                pair_box = (
                    min(upper.bounding_box[0], lower.bounding_box[0]),
                    min(upper.bounding_box[1], lower.bounding_box[1]),
                    max(upper.bounding_box[2], lower.bounding_box[2]),
                    max(upper.bounding_box[3], lower.bounding_box[3]),
                )
                circle_box, boundary_score = _circle_boundary(page, pair_box, edge_distance)
                if circle_box is None:
                    continue
                item_number = upper.text.strip()
                candidate = VisualObject(
                    object_type=VisualObjectType.BOM_BALLOON,
                    page_number=page_number,
                    bounding_box=circle_box,
                    confidence=min(0.98, 0.90 + 0.08 * boundary_score),
                    detector=self.name,
                    raw_text=f"{upper.text}|{lower.text}",
                    normalized_text=item_number,
                    linked_text=item_number,
                    attributes={
                        "balloon_text": upper.text,
                        "item_number": item_number,
                        "shape": "split_circle",
                        "upper_compartment_text": upper.text,
                        "lower_compartment_text": lower.text,
                        "boundary_score": round(boundary_score, 4),
                        "leader_association_confidence": 0.0,
                    },
                )
                _deduplicated_append(objects, candidate)

            binary = adaptive_threshold(page.image, block_size=41, c=13)
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area_pixels = abs(cv2.contourArea(contour))
                perimeter = cv2.arcLength(contour, True)
                if area_pixels <= 0 or perimeter <= 0:
                    continue
                x, y, width, height = cv2.boundingRect(contour)
                pdf_box = page.pixel_to_pdf_bbox((x, y, x + width, y + height))
                pdf_width = pdf_box[2] - pdf_box[0]
                pdf_height = pdf_box[3] - pdf_box[1]
                ratio = pdf_width / max(pdf_height, 0.1)
                circularity = 4 * math.pi * area_pixels / (perimeter * perimeter)
                polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
                supported_shape = 0.68 <= ratio <= 1.45 and (
                    (circularity >= 0.82 and len(polygon) >= 7)
                    or (5 <= len(polygon) <= 8 and circularity >= 0.70)
                )
                if not supported_shape or not (7 <= pdf_width <= 45 and 7 <= pdf_height <= 45):
                    continue
                text, text_box = nearby_native_text(
                    page, pdf_box, margin=2.5, pattern=r"\d{1,4}"
                )
                # Internal annotation evidence is mandatory; this rejects ordinary holes.
                if not text or text_box is None:
                    continue
                text_width = text_box[2] - text_box[0]
                text_height = text_box[3] - text_box[1]
                # A balloon boundary must enclose the token rather than merely be the
                # contour of the digit glyph itself.
                if pdf_width < text_width * 1.35 or pdf_height < text_height * 1.25:
                    continue
                item_number = re.sub(r"\s+", "", text).upper()
                confidence = min(0.98, 0.82 + 0.13 + (0.02 if circularity >= 0.72 else 0.0))
                candidate = VisualObject(
                    object_type=VisualObjectType.BOM_BALLOON,
                    page_number=page_number,
                    bounding_box=pdf_box,
                    confidence=confidence,
                    detector=self.name,
                    raw_text=text,
                    normalized_text=item_number,
                    linked_text=item_number,
                    attributes={
                        "balloon_text": text,
                        "item_number": item_number,
                        "shape": "circle_or_ellipse" if len(polygon) > 6 else "polygon",
                        "circularity": round(float(circularity), 4),
                        "leader_association_confidence": 0.0,
                    },
                )
                _deduplicated_append(objects, candidate)
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            warnings=warnings,
            execution_time_ms=(time.perf_counter() - started) * 1000,
        )
