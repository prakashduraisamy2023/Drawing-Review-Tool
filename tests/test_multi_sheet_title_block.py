from pathlib import Path

import pytest

from backend.app.extraction import MultiSheetTitleBlockExtractor
from backend.app.models.drawing import (
    ExtractedField,
    ExtractionMethod,
    MultiSheetTitleBlockExtraction,
    PageTitleBlockData,
)

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def assert_value(field: ExtractedField, value, page_number: int) -> None:
    assert field.value == value
    assert field.page_number == page_number
    assert field.confidence > 0
    assert field.extraction_method == "coordinate_text"
    assert field.bounding_box is not None


def evidence(value: str, page_number: int, confidence: float = 0.95) -> ExtractedField:
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=(10, 10, 20, 20),
    )


def test_multisheet_result_preserves_each_page_and_only_normalizes_consensus():
    result = MultiSheetTitleBlockExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert isinstance(result, MultiSheetTitleBlockExtraction)
    assert len(result.pages) == 5
    for page_number, page in enumerate(result.pages, start=1):
        assert page.page == page_number
        assert_value(page.title_block.drawing_number, "47789413", page_number)
        assert_value(page.title_block.revision, "C", page_number)
        assert_value(page.title_block.sheet_number, page_number, page_number)
        assert_value(page.title_block.total_sheets, 5, page_number)
        assert_value(page.title_block.units, "mm", page_number)

    assert_value(result.pages[0].title_block.part_name, "ASM, PNL, CPLR, IN, BLK", 1)
    assert_value(result.pages[0].title_block.weight, "1.27", 1)
    assert_value(result.pages[1].title_block.part_name, "PNL, CPLR, IN, BLK", 2)
    assert_value(result.pages[1].title_block.weight, "1.26", 2)

    metadata = result.document_metadata
    assert_value(metadata.drawing_number, "47789413", 1)
    assert_value(metadata.revision, "C", 1)
    assert_value(metadata.total_sheets, 5, 1)
    assert_value(metadata.units, "mm", 1)
    assert metadata.part_name.value is None
    assert metadata.weight.value is None
    assert metadata.sheet_number.value is None

    payload = result.model_dump(mode="json")
    assert set(payload) == {"pages", "document_metadata"}
    assert set(payload["pages"][0]) == {"page", "title_block"}
    assert set(payload["pages"][0]["title_block"]) == {
        "drawing_number",
        "revision",
        "part_name",
        "weight",
        "sheet_number",
        "total_sheets",
        "units",
    }


@pytest.mark.parametrize(
    ("filename", "drawing_number", "revision", "part_name", "weight"),
    [
        (
            "47789460_B_watermarked.pdf",
            "47789460",
            "B",
            "ASM, FRT, SEAT BACK, LH",
            "11",
        ),
        (
            "47789660_A_watermarked.pdf",
            "47789660",
            "A",
            "ASM, KIT, SOUNDBAR, FP",
            "6.550",
        ),
    ],
)
def test_single_sheet_samples_normalize_all_requested_values(
    filename,
    drawing_number,
    revision,
    part_name,
    weight,
):
    result = MultiSheetTitleBlockExtractor().extract(SAMPLES / filename)

    assert len(result.pages) == 1
    assert result.pages[0].page == 1
    metadata = result.document_metadata
    assert_value(metadata.drawing_number, drawing_number, 1)
    assert_value(metadata.revision, revision, 1)
    assert_value(metadata.part_name, part_name, 1)
    assert_value(metadata.weight, weight, 1)
    assert_value(metadata.sheet_number, 1, 1)
    assert_value(metadata.total_sheets, 1, 1)
    assert_value(metadata.units, "mm", 1)


def test_normalization_leaves_disagreements_null_without_raising():
    extractor = MultiSheetTitleBlockExtractor()
    metadata = extractor.normalize(
        [
            PageTitleBlockData(drawing_number=evidence("DRAWING-A", 1)),
            PageTitleBlockData(drawing_number=evidence("DRAWING-B", 2)),
        ]
    )

    assert metadata.drawing_number.value is None
    assert metadata.drawing_number.page_number is None


def test_high_confidence_unanimous_partial_evidence_can_normalize():
    extractor = MultiSheetTitleBlockExtractor()
    metadata = extractor.normalize(
        [
            PageTitleBlockData(units=evidence("MM", 1)),
            PageTitleBlockData(),
        ]
    )

    assert_value(metadata.units, "MM", 1)
