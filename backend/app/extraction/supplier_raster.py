"""Detect large supplier-original raster regions without applying OCR."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.extraction.page_context import DocumentContext, build_document_context
from backend.app.models.drawing import ExtractionMethod, SupplierRasterRegion

SUPPLIER_EVIDENCE = re.compile(
    r"\b(?:SUPPLIER\s+DRAWING|SUPPLIER\s*:|MANUFACTURER\s*:)",
    re.IGNORECASE,
)
MIN_REGION_AREA = 0.25


class SupplierRasterRegionExtractor:
    """Return large image regions only when explicit supplier evidence exists."""

    def extract(
        self,
        pdf_path: str | Path,
        *,
        context: DocumentContext | None = None,
    ) -> list[SupplierRasterRegion]:
        document = context or build_document_context(pdf_path)
        if not any(SUPPLIER_EVIDENCE.search(page.text) for page in document.pages):
            return []

        score = calculate_confidence(
            ConfidenceEvidence(
                anchor_found=True,
                expected_region=True,
                format_match=True,
                relative_position=True,
            )
        ).score
        regions: list[SupplierRasterRegion] = []
        for page in document.pages:
            for image in page.image_regions:
                x0, y0, x1, y1 = image.normalized_bounding_box
                area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
                if area < MIN_REGION_AREA or x0 > 0.25 or y0 > 0.20:
                    continue
                regions.append(
                    SupplierRasterRegion(
                        page_number=page.page_number,
                        bounding_box=image.bounding_box,
                        normalized_bounding_box=image.normalized_bounding_box,
                        confidence=score,
                        extraction_method=ExtractionMethod.IMAGE_REGION,
                        evidence_anchor="SUPPLIER DRAWING / SUPPLIER / MANUFACTURER",
                    )
                )
        return regions
