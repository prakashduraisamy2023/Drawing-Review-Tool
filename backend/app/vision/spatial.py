"""Deterministic coordinate and spatial-association helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable

from backend.app.models.drawing import BoundingBox


def bbox_area(box: BoundingBox) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection_over_union(first: BoundingBox, second: BoundingBox) -> float:
    intersection = (
        max(first[0], second[0]),
        max(first[1], second[1]),
        min(first[2], second[2]),
        min(first[3], second[3]),
    )
    intersection_area = bbox_area(intersection)
    union = bbox_area(first) + bbox_area(second) - intersection_area
    return intersection_area / union if union > 0 else 0.0


def center(box: BoundingBox) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def center_distance(first: BoundingBox, second: BoundingBox) -> float:
    a, b = center(first), center(second)
    return math.hypot(a[0] - b[0], a[1] - b[1])


def expand_bbox(box: BoundingBox, margin: float) -> BoundingBox:
    return (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)


def contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def nearest_bbox(reference: BoundingBox, candidates: Iterable[BoundingBox]) -> BoundingBox | None:
    return min(candidates, key=lambda item: center_distance(reference, item), default=None)
