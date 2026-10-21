from pathlib import Path

import pytest

from backend.app.extraction.title_block import TitleBlockExtractor
from backend.app.models.drawing import ExtractedField, TitleBlock

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def assert_value(field: ExtractedField, value, page_number: int) -> None:
    assert field.value == value
    assert field.page_number == page_number
    assert field.confidence > 0
    assert field.extraction_method == "coordinate_text"
    assert field.bounding_box is not None
    assert field.raw_text is not None
    assert field.evidence_anchor == "title-block label and relative position"
    x0, y0, x1, y1 = field.bounding_box
    assert x0 <= x1
    assert y0 <= y1


def test_extracts_every_sheet_from_multisheet_b_size_drawing():
    blocks = TitleBlockExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert len(blocks) == 5
    for page_number, block in enumerate(blocks, start=1):
        assert isinstance(block, TitleBlock)
        assert_value(block.drawing_number, "47789413", page_number)
        assert_value(block.revision, "C", page_number)
        assert_value(block.drawing_size, "B", page_number)
        assert_value(block.drawing_date, "02/25/2026", page_number)
        assert_value(block.drawn_by, "K_MURUGAN", page_number)
        assert_value(block.modeled_by, "ONE3", page_number)
        assert_value(block.units, "mm", page_number)
        assert_value(block.scale, "0.125", page_number)
        assert_value(block.sheet_number, page_number, page_number)
        assert_value(block.sheet_count, 5, page_number)
        assert block.critical_component.value is None

    assert_value(blocks[0].part_name, "ASM, PNL, CPLR, IN, BLK", 1)
    assert_value(blocks[0].weight, "1.27", 1)
    assert_value(blocks[1].part_name, "PNL, CPLR, IN, BLK", 2)
    assert_value(blocks[1].weight, "1.26", 2)


@pytest.mark.parametrize(
    (
        "filename",
        "drawing_number",
        "revision",
        "size",
        "part_name",
        "date",
        "drawn",
        "modeled",
        "weight",
        "critical",
    ),
    [
        (
            "47789460_B_watermarked.pdf",
            "47789460",
            "B",
            "D",
            "ASM, FRT, SEAT BACK, LH",
            "04/24/2026",
            "S_BHANU",
            "UML",
            "11",
            True,
        ),
        (
            "47789660_A_watermarked.pdf",
            "47789660",
            "A",
            "B",
            "ASM, KIT, SOUNDBAR, FP",
            "05/14/2026",
            "P_DINESH",
            "SUPREME",
            "6.550",
            None,
        ),
    ],
)
def test_extracts_single_sheet_b_and_d_size_samples(
    filename,
    drawing_number,
    revision,
    size,
    part_name,
    date,
    drawn,
    modeled,
    weight,
    critical,
):
    block = TitleBlockExtractor().extract(SAMPLES / filename)[0]

    assert_value(block.drawing_number, drawing_number, 1)
    assert_value(block.revision, revision, 1)
    assert_value(block.drawing_size, size, 1)
    assert_value(block.part_name, part_name, 1)
    assert_value(block.drawing_date, date, 1)
    assert_value(block.drawn_by, drawn, 1)
    assert_value(block.modeled_by, modeled, 1)
    assert_value(block.weight, weight, 1)
    assert_value(block.units, "mm", 1)
    assert_value(block.scale, "0.125", 1)
    assert_value(block.sheet_number, 1, 1)
    assert_value(block.sheet_count, 1, 1)
    assert block.critical_component.value is critical
    if critical is not None:
        assert block.critical_component.bounding_box is not None
