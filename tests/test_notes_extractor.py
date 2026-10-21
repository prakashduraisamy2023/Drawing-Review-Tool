from pathlib import Path

import pymupdf
import pytest

from backend.app.extraction import NotesExtractor
from backend.app.models.drawing import DrawingNote

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def standards(note: DrawingNote) -> list[str]:
    return [reference.designation.value for reference in note.standards or []]


def assert_note_provenance(note: DrawingNote) -> None:
    assert note.number.value is not None
    assert note.text.value
    assert note.page_number == note.number.page_number == note.text.page_number
    assert note.bounding_box is not None
    assert note.number.bounding_box is not None
    assert note.text.bounding_box is not None
    assert note.number.extraction_method == "coordinate_text"
    assert note.text.extraction_method == "coordinate_text"
    assert note.text.raw_text == note.text.value
    assert note.text.evidence_anchor == "NOTE/NOTES heading and numbered marker"
    x0, y0, x1, y1 = note.bounding_box
    assert x0 <= x1
    assert y0 <= y1


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("47789413_C_watermarked.pdf", 15),
        ("47789460_B_watermarked.pdf", 14),
        ("47789660_A_watermarked.pdf", 6),
    ],
)
def test_extracts_numbered_notes_from_all_sample_pdfs(filename, expected_count):
    notes = NotesExtractor().extract(SAMPLES / filename)

    assert len(notes) == expected_count
    assert all(isinstance(note, DrawingNote) for note in notes)
    for note in notes:
        assert_note_provenance(note)


def test_preserves_multiline_wording_and_page_numbers():
    notes = NotesExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")
    first = notes[0]
    page_two_note_six = next(
        note for note in notes if note.page_number == 2 and note.number.value == "6"
    )

    assert first.number.value == "1"
    assert first.page_number == 1
    assert "PART SHALL BE LABELED WITH A DATAMATRIX PART IDENTIFICATION" in first.text.value
    assert "\nLABEL THAT IS IN COMPLIANCE" in first.text.value
    assert "VALUES QUERIED FROM THE CAD MODEL ARE BASIC" in page_two_note_six.text.value
    assert "\n" in page_two_note_six.text.value


def test_detects_standard_references_with_source_bounding_boxes():
    standard_drawing = NotesExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")
    supplier_d = NotesExtractor().extract(SAMPLES / "47789460_B_watermarked.pdf")
    supplier_b = NotesExtractor().extract(SAMPLES / "47789660_A_watermarked.pdf")
    references = {
        designation
        for note in [*standard_drawing, *supplier_d, *supplier_b]
        for designation in standards(note)
    }

    assert {
        "PES000059",
        "PES000063",
        "PES000073",
        "PES000087",
        "ASME Y14.41-2012",
        "SAE J1885",
        "ASTM D4329",
        "FMVSS-302",
    }.issubset(references)

    for note in [*standard_drawing, *supplier_d, *supplier_b]:
        for reference in note.standards or []:
            assert reference.designation.page_number == note.page_number
            assert reference.designation.bounding_box is not None
            assert reference.description.value is None


def test_supports_singular_note_heading_and_separate_multiline_blocks(tmp_path: Path):
    source = tmp_path / "notes.pdf"
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((50, 50), "NOTE:")
    page.insert_text((50, 75), "1. FOLLOW ASME Y14.5 AND SAE J1885.")
    page.insert_text((70, 90), "KEEP ORIGINAL WORDING ON SECOND LINE.")
    page.insert_text((50, 115), "2. TEST ASTM D4329 AND FMVSS-302.")
    document.save(source)
    document.close()

    notes = NotesExtractor().extract(source)

    assert [note.number.value for note in notes] == ["1", "2"]
    assert notes[0].text.value == (
        "FOLLOW ASME Y14.5 AND SAE J1885.\nKEEP ORIGINAL WORDING ON SECOND LINE."
    )
    assert standards(notes[0]) == ["ASME Y14.5", "SAE J1885"]
    assert standards(notes[1]) == ["ASTM D4329", "FMVSS-302"]


def test_attached_note_numbers_are_split_without_losing_wording():
    notes = NotesExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")
    note_ten = next(note for note in notes if note.page_number == 2 and note.number.value == "10")

    assert note_ten.text.value == "PART MUST CONFORM TO CCL SPECIFICATION PES000063."
    assert standards(note_ten) == ["PES000063"]
