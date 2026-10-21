from __future__ import annotations

import io

import pymupdf as fitz
from PIL import Image

from streamlit_workspace import (
    _all_extracted_regions,
    _annotated_page,
    _evidence_regions,
    _field_region,
    _render_page,
    _visual_region,
)


def _two_page_pdf() -> bytes:
    document = fitz.open()
    for label in ("FIRST SHEET", "SECOND SHEET"):
        page = document.new_page(width=400, height=300)
        page.insert_text((50, 80), label)
    payload = document.tobytes()
    document.close()
    return payload


def test_region_adapters_preserve_provenance() -> None:
    field = {
        "value": "A-100",
        "page_number": 2,
        "bounding_box": [10, 20, 80, 40],
        "confidence": 0.91,
        "extraction_method": "coordinate_text",
        "raw_text": "A-100",
    }
    region = _field_region("Part number", field)
    assert region is not None
    assert region["page_number"] == 2
    assert region["bounding_box"] == [10.0, 20.0, 80.0, 40.0]
    assert region["confidence"] == 0.91
    assert region["method"] == "coordinate_text"

    flattened = _all_extracted_regions({"part_number": field})
    assert len(flattened) == 1
    assert flattened[0]["label"] == "drawing.part_number"


def test_validation_and_visual_regions_require_real_coordinates() -> None:
    evidence = [
        {
            "page_number": 3,
            "bounding_box": [1, 2, 3, 4],
            "confidence": 0.8,
            "extraction_method": "native_text",
        },
        {"page_number": None, "bounding_box": None, "confidence": 0.5},
    ]
    regions = _evidence_regions(evidence, label="Rule evidence", kind="validation", status="FAIL")
    assert len(regions) == 1
    assert regions[0]["page_number"] == 3
    assert regions[0]["status"] == "FAIL"

    visual = _visual_region(
        {
            "object_type": "FLAG_NOTE",
            "page_number": 4,
            "bounding_box": [11, 12, 21, 22],
            "confidence": 0.93,
            "detector": "flag_note_detector",
        }
    )
    assert visual is not None
    assert visual["page_number"] == 4
    assert visual["kind"] == "visual"


def test_every_pdf_page_can_render_and_accept_overlay() -> None:
    payload = _two_page_pdf()
    for page_number in (1, 2):
        png, width, height = _render_page(payload, page_number, 1.5)
        image = Image.open(io.BytesIO(png))
        assert image.width > 0
        assert image.height > 0
        assert width == 400
        assert height == 300

    region = {
        "label": "Located evidence",
        "page_number": 2,
        "bounding_box": [45.0, 60.0, 180.0, 90.0],
        "confidence": 0.95,
        "method": "native_text",
        "raw_text": "SECOND SHEET",
        "kind": "validation",
        "status": "FAIL",
    }
    annotated = _annotated_page(payload, 2, [(region, True)], 100)
    image = Image.open(io.BytesIO(annotated))
    assert image.format == "PNG"
    assert image.width > 0
    assert image.height > 0
