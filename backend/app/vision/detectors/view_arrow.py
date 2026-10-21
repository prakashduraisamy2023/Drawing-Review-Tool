"""Native-first view, section, and detail annotation detector."""

from __future__ import annotations

import re
import time

from backend.app.vision.detectors.base import DetectorContext, VisualDetector
from backend.app.vision.models import DetectorResult, VisualObject, VisualObjectType

LABEL = re.compile(r"^(VIEW|DETAIL|SECTION)$", re.IGNORECASE)
IDENTIFIER = re.compile(r"^[A-Z](?:-[A-Z])?$", re.IGNORECASE)


class ViewAnnotationDetector(VisualDetector):
    name = "view_annotation"

    def detect(self, context: DetectorContext) -> DetectorResult:
        started = time.perf_counter()
        objects: list[VisualObject] = []
        for page_number in range(1, context.renderer.page_count + 1):
            page = context.renderer.render_page(page_number)
            words = list(page.native_words)
            for index, word in enumerate(words):
                match = LABEL.fullmatch(word.text)
                if not match:
                    continue
                following = words[index + 1] if index + 1 < len(words) else None
                identifier = (
                    following.text if following and IDENTIFIER.fullmatch(following.text) else None
                )
                box = word.bounding_box
                if identifier and following:
                    box = (
                        min(box[0], following.bounding_box[0]),
                        min(box[1], following.bounding_box[1]),
                        max(box[2], following.bounding_box[2]),
                        max(box[3], following.bounding_box[3]),
                    )
                kind = match.group(1).upper()
                object_type = (
                    VisualObjectType.SECTION_ARROW
                    if kind == "SECTION"
                    else VisualObjectType.DETAIL_CALLOUT
                    if kind == "DETAIL"
                    else VisualObjectType.VIEW_ARROW
                )
                label = f"{kind} {identifier}" if identifier else kind
                objects.append(
                    VisualObject(
                        object_type=object_type,
                        page_number=page_number,
                        bounding_box=box,
                        confidence=0.92 if identifier else 0.78,
                        detector=self.name,
                        extraction_method="native_text_spatial_association",
                        raw_text=label,
                        normalized_text=label.upper(),
                        linked_text=identifier,
                        attributes={"annotation_kind": kind, "identifier": identifier},
                    )
                )
        return DetectorResult(
            detector_name=self.name,
            objects=objects,
            execution_time_ms=(time.perf_counter() - started) * 1000,
        )
