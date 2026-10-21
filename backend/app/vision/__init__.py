"""Level-3 visual evidence layer.

The vision package detects observable drawing objects. It does not make
engineering approval or standards-compliance decisions.
"""

from backend.app.vision.engine import VisionEngine
from backend.app.vision.models import (
    DetectorResult,
    ReviewAction,
    VisionReport,
    VisionSummary,
    VisualObject,
    VisualObjectType,
    VisualReview,
)

__all__ = [
    "DetectorResult",
    "ReviewAction",
    "VisionEngine",
    "VisionReport",
    "VisionSummary",
    "VisualObject",
    "VisualObjectType",
    "VisualReview",
]
