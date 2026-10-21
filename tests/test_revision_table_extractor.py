from pathlib import Path

import pymupdf
import pytest

from backend.app.extraction import RevisionTableExtractor
from backend.app.models.drawing import ExtractedField, RevisionRecord

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def assert_field(field: ExtractedField, value: str, page_number: int) -> None:
    assert field.value == value
    assert field.page_number == page_number
    assert field.confidence > 0
    assert field.extraction_method == "coordinate_text"
    assert field.bounding_box is not None


def assert_record_provenance(record: RevisionRecord) -> None:
    assert record.page_number is not None
    assert record.bounding_box is not None
    for field_name in (
        "ecn",
        "revision_description",
        "revision_date",
        "changed_by",
        "approved_by",
    ):
        field = getattr(record, field_name)
        if field.value is not None:
            assert field.page_number == record.page_number
            assert field.bounding_box is not None
            assert field.extraction_method == "coordinate_text"


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("47789413_C_watermarked.pdf", 5),
        ("47789460_B_watermarked.pdf", 1),
        ("47789660_A_watermarked.pdf", 1),
    ],
)
def test_extracts_revision_rows_from_every_sample(filename: str, expected_count: int) -> None:
    records = RevisionTableExtractor().extract(SAMPLES / filename)

    assert len(records) == expected_count
    assert all(isinstance(record, RevisionRecord) for record in records)
    for record in records:
        assert_record_provenance(record)


def test_preserves_multiline_release_description_verbatim() -> None:
    records = RevisionTableExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert_field(records[0].ecn, "1478359", 1)
    assert_field(
        records[0].revision_description,
        'REV "B" NOT RELEASED\nC: PRODUCTION RELEASE',
        1,
    )
    assert_field(records[0].revision_date, "05/05/2026", 1)
    assert_field(records[0].changed_by, "K_MATHAN", 1)
    assert_field(records[0].approved_by, "M_LORENTZ", 1)
    assert records[0].revision.value is None


def test_extracts_sheet_one_revision_reference_on_following_sheets() -> None:
    records = RevisionTableExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert [record.page_number for record in records] == [1, 2, 3, 4, 5]
    assert all(
        record.revision_description.value == "SEE SHEET 1 FOR REVISIONS" for record in records[1:]
    )


@pytest.mark.parametrize(
    ("filename", "description", "ecn", "date", "changed_by", "approved_by"),
    [
        (
            "47789460_B_watermarked.pdf",
            "B: PRODUCTION RELEASE",
            "1478648",
            "04/30/2026",
            "S_BHANU",
            "J_BRADWAY",
        ),
        (
            "47789660_A_watermarked.pdf",
            "INITIAL RELEASE",
            "1478636",
            "05/20/2026",
            "P_DINESH",
            "J_BRADWAY",
        ),
    ],
)
def test_extracts_supplier_revision_rows(
    filename: str,
    description: str,
    ecn: str,
    date: str,
    changed_by: str,
    approved_by: str,
) -> None:
    record = RevisionTableExtractor().extract(SAMPLES / filename)[0]

    assert_field(record.ecn, ecn, 1)
    assert_field(record.revision_description, description, 1)
    assert_field(record.revision_date, date, 1)
    assert_field(record.changed_by, changed_by, 1)
    assert_field(record.approved_by, approved_by, 1)


def test_supports_multiple_rows_and_leaves_absent_cells_null(tmp_path: Path) -> None:
    source = tmp_path / "revision-table.pdf"
    document = pymupdf.open()
    page = document.new_page(width=720, height=540)

    rows = [
        ("ECN-1001", "INITIAL RELEASE", "01/02/2026", "A_USER", "B_USER"),
        ("ECN-1002", "B: PRODUCTION RELEASE", "02/03/2026", "C_USER", "D_USER"),
        ("ECN-1003", "REV B NOT RELEASED", "03/04/2026", "E_USER", None),
    ]
    for y, row in zip((210, 235, 260), rows, strict=True):
        for x, value in zip((50, 140, 360, 440, 540), row, strict=True):
            if value is not None:
                page.insert_text((x, y), value, fontsize=9)

    for x, heading in (
        (50, "ECN"),
        (140, "DESCRIPTION OF CHANGE"),
        (360, "DATE"),
        (440, "CHANGED BY"),
        (540, "APPROVED BY"),
    ):
        page.insert_text((x, 300), heading, fontsize=9)
    document.save(source)
    document.close()

    records = RevisionTableExtractor().extract(source)

    assert len(records) == 3
    assert [record.ecn.value for record in records] == ["ECN-1001", "ECN-1002", "ECN-1003"]
    assert [record.revision_description.value for record in records] == [
        "INITIAL RELEASE",
        "B: PRODUCTION RELEASE",
        "REV B NOT RELEASED",
    ]
    assert records[2].approved_by.value is None
    assert records[2].approved_by.page_number is None
    assert records[2].approved_by.bounding_box is None
    assert all(record.revision.value is None for record in records)
