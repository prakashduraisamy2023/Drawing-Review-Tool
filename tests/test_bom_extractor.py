from pathlib import Path

import pymupdf
import pytest

from backend.app.extraction import BOMExtractor
from backend.app.models.drawing import BOMItem, ExtractedField, TableType

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def assert_field(field: ExtractedField, value, page_number: int) -> None:
    assert field.value == value
    assert field.page_number == page_number
    assert field.confidence > 0
    assert field.extraction_method in {"coordinate_text", "pdfplumber_table"}
    assert field.bounding_box is not None


def assert_item_provenance(item: BOMItem) -> None:
    assert item.page_number is not None
    assert item.bounding_box is not None
    assert item.part_number.value is not None or item.description.value is not None
    for field_name in ("item_no", "quantity", "part_number", "description"):
        field = getattr(item, field_name)
        if field.value is not None:
            assert field.page_number == item.page_number
            assert field.bounding_box is not None


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("47789413_C_watermarked.pdf", 8),
        ("47789460_B_watermarked.pdf", 3),
        ("47789660_A_watermarked.pdf", 9),
    ],
)
def test_extracts_native_bom_rows_from_all_samples(filename, expected_count):
    items = BOMExtractor().extract(SAMPLES / filename)

    assert len(items) == expected_count
    assert all(isinstance(item, BOMItem) for item in items)
    for item in items:
        assert_item_provenance(item)


def test_extracts_full_and_partial_column_boms_without_inference():
    items = BOMExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")
    full_row = next(item for item in items if item.item_no.value == "2")
    partial_row = next(
        item for item in items if item.page_number == 2 and item.part_number.value == "47789413001"
    )

    assert_field(full_row.quantity, "4", 1)
    assert_field(full_row.item_no, "2", 1)
    assert_field(full_row.part_number, "47787199001", 1)
    assert_field(full_row.description, "CLIP, PUSH-IN, U-BASE", 1)

    assert partial_row.quantity.value is None
    assert partial_row.item_no.value is None
    assert_field(partial_row.part_number, "47789413001", 2)
    assert_field(partial_row.description, "PNL, CPLR, IN, LH, BLK", 2)


def test_extracts_outer_and_service_parts_tables_on_the_same_page():
    items = BOMExtractor().extract(SAMPLES / "47789660_A_watermarked.pdf")

    outer = items[0]
    service_rows = items[1:]
    assert_field(outer.part_number, "47789660001", 1)
    assert_field(outer.description, "ASM, KIT, SOUNDBAR, FP", 1)
    assert len(service_rows) == 8
    assert_field(service_rows[0].part_number, "47789552001", 1)
    assert_field(service_rows[0].description, "SOUNDBAR, FP", 1)
    assert all(item.quantity.value is None for item in service_rows)
    assert all(item.item_no.value is None for item in service_rows)
    assert outer.table_type == TableType.PART_LIST
    assert all(item.table_type == TableType.SERVICE_PARTS for item in service_rows)


def test_raster_supplier_table_is_not_fabricated_from_absent_native_text():
    items = BOMExtractor().extract(SAMPLES / "47789460_B_watermarked.pdf")

    assert len(items) == 3
    assert all(item.quantity.value is None for item in items)
    assert all(item.item_no.value is None for item in items)
    assert all(item.table_type == TableType.PART_LIST for item in items)


def test_supports_multiple_tables_and_multiline_descriptions(tmp_path: Path):
    source = tmp_path / "bom.pdf"
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)

    for x, text in ((50, "QTY"), (100, "ITEM"), (150, "PART NO."), (260, "DESCRIPTION")):
        page.insert_text((x, 50), text)
    for x, text in ((50, "2"), (100, "1"), (150, "AX-1001"), (260, "LONG")):
        page.insert_text((x, 75), text)
    page.insert_text((260, 90), "DESCRIPTION")

    page.insert_text((50, 200), "SERVICE PART NO.")
    page.insert_text((260, 200), "DESCRIPTION")
    page.insert_text((50, 225), "SV-2001")
    page.insert_text((260, 225), "SERVICE BRACKET")
    page.insert_text((50, 250), "SV-2002")
    page.insert_text((260, 250), "SERVICE CLIP")
    document.save(source)
    document.close()

    items = BOMExtractor().extract(source)

    assert len(items) == 3
    assert_field(items[0].quantity, "2", 1)
    assert_field(items[0].item_no, "1", 1)
    assert_field(items[0].part_number, "AX-1001", 1)
    assert_field(items[0].description, "LONG DESCRIPTION", 1)
    assert items[1].quantity.value is None
    assert items[1].item_no.value is None
    assert_field(items[1].part_number, "SV-2001", 1)
    assert_field(items[2].part_number, "SV-2002", 1)


def test_serialized_item_uses_requested_item_no_name():
    item = BOMExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")[1]
    payload = item.model_dump(mode="json")

    assert "item_no" in payload
    assert "item_number" not in payload


def test_accepts_evidence_backed_three_character_part_number(tmp_path: Path):
    source = tmp_path / "short-part-number.pdf"
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    for x, text in ((50, "QTY"), (100, "ITEM"), (150, "PART NO."), (260, "DESCRIPTION")):
        page.insert_text((x, 50), text)
    for x, text in ((50, "3"), (100, "1"), (150, "451"), (260, "LOCKWASHER")):
        page.insert_text((x, 75), text)
    document.save(source)
    document.close()

    items = BOMExtractor().extract(source)

    assert len(items) == 1
    assert_field(items[0].item_no, "1", 1)
    assert_field(items[0].quantity, "3", 1)
    assert_field(items[0].part_number, "451", 1)
