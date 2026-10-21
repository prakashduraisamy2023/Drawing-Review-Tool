from pathlib import Path

import pymupdf

from backend.app.extraction.page_context import (
    PageTemplate,
    build_document_context,
    detect_page_template,
)

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def test_detects_supported_normalized_page_templates():
    assert detect_page_template(1224, 792) == PageTemplate.CLUB_CAR_17X11
    assert detect_page_template(2448, 1584) == PageTemplate.CLUB_CAR_34X22
    assert detect_page_template(612, 792) == PageTemplate.UNKNOWN


def test_builds_single_pass_page_context_for_multisheet_sample():
    context = build_document_context(SAMPLES / "47789413_C_watermarked.pdf")

    assert context.page_count == 5
    assert all(page.native_text_available for page in context.pages)
    assert all(page.template == PageTemplate.CLUB_CAR_17X11 for page in context.pages)
    assert [len(page.words) for page in context.pages] == [371, 526, 210, 265, 327]


def test_context_handles_unknown_layout_and_missing_native_text(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    document = pymupdf.open()
    document.new_page(width=500, height=500)
    document.save(path)
    document.close()

    context = build_document_context(path)
    assert context.pages[0].template == PageTemplate.UNKNOWN
    assert context.pages[0].native_text_available is False
