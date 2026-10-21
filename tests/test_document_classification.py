from pathlib import Path

import pymupdf
import pytest

from backend.app.extraction import DocumentClassifier
from backend.app.models.drawing import DocumentClassification, DocumentType, ExtractedField

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def assert_evidence(field: ExtractedField, page_number: int = 1) -> None:
    assert field.value is not None
    assert field.page_number == page_number
    assert field.confidence > 0
    assert field.extraction_method == "coordinate_text"
    assert field.bounding_box is not None


@pytest.mark.parametrize(
    "filename",
    ["47789460_B_watermarked.pdf", "47789660_A_watermarked.pdf"],
)
def test_classifies_supplier_drawings_from_explicit_pdf_evidence(filename):
    result = DocumentClassifier().extract(SAMPLES / filename)

    assert isinstance(result, DocumentClassification)
    assert result.document_type == DocumentType.SUPPLIER_DRAWING
    assert_evidence(result.evidence)
    assert result.supplier.supplier_drawing.value is True
    assert_evidence(result.supplier.supplier_drawing)
    assert result.supplier.supplier_drawing_marker.value == ("SUPPLIER DRAWING NOT TO SCALE")
    assert_evidence(result.supplier.imported_cad_data_statement)
    assert "IMPORTED" in result.supplier.imported_cad_data_statement.value
    assert "CAD DATA" in result.supplier.imported_cad_data_statement.value


def test_extracts_single_supplier_name_and_part_number():
    result = DocumentClassifier().extract(SAMPLES / "47789660_A_watermarked.pdf")
    supplier = result.supplier

    assert supplier.supplier_name.value == "SUPREME"
    assert supplier.supplier_part_number.value == "ASBK9660001"
    assert supplier.supplier_part_numbers.value == ["ASBK9660001"]
    assert_evidence(supplier.supplier_name)
    assert_evidence(supplier.supplier_part_number)


def test_preserves_multiple_manufacturer_part_numbers_without_choosing_one():
    result = DocumentClassifier().extract(SAMPLES / "47789460_B_watermarked.pdf")
    supplier = result.supplier

    assert supplier.supplier_name.value == "UNO MINDA LIMITED"
    assert supplier.supplier_part_number.value is None
    assert supplier.supplier_part_numbers.value == [
        "KI8261054A0I",
        "KI8261085A0I",
        "KI8261089A0I",
    ]
    assert supplier.manufacturer_name.value == "UNO MINDA LIMITED"
    assert [
        (
            mapping.source_part_number.value,
            mapping.manufacturer_part_number.value,
        )
        for mapping in supplier.manufacturer_part_number_mappings or []
    ] == [
        ("47789460001", "KI8261054A0I"),
        ("47789460002", "KI8261085A0I"),
        ("47789460003", "KI8261089A0I"),
    ]
    assert_evidence(supplier.supplier_part_numbers)


def test_classifies_standard_drawing_from_positive_internal_drawing_statement():
    result = DocumentClassifier().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert result.document_type == DocumentType.STANDARD_DRAWING
    assert result.evidence.value == "LIMITED DIMENSION DRAWING BASED ON CAD MODEL"
    assert_evidence(result.evidence, page_number=2)
    assert result.supplier.supplier_drawing.value is None
    assert result.supplier.supplier_name.value is None


def test_supplier_or_manufacturer_metadata_is_sufficient_without_marker(tmp_path: Path):
    source = tmp_path / "metadata.pdf"
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_textbox(
        pymupdf.Rect(50, 50, 500, 250),
        "NOTES:\n\n"
        "1. MANUFACTURER: ACME COMPONENTS\n\n"
        "2. MANUFACTURER P/N: AX-42\n\n"
        "3. THIS DRAWING CONTAINS IMPORTED CAD DATA FROM THE SUPPLIER.",
        fontsize=11,
    )
    document.save(source)
    document.close()

    result = DocumentClassifier().extract(source)

    assert result.document_type == DocumentType.SUPPLIER_DRAWING
    assert result.supplier.supplier_drawing_marker.value is None
    assert result.supplier.supplier_name.value == "ACME COMPONENTS"
    assert result.supplier.supplier_part_number.value == "AX-42"
    assert result.supplier.supplier_drawing.value is True


def test_filename_alone_never_classifies_document(tmp_path: Path):
    source = tmp_path / "SUPPLIER_DRAWING.pdf"
    document = pymupdf.open()
    document.new_page(width=612, height=792)
    document.save(source)
    document.close()

    result = DocumentClassifier().extract(source)

    assert result.document_type == DocumentType.UNKNOWN
    assert result.evidence.value is None
    assert result.supplier.supplier_drawing.value is None
    assert result.supplier.supplier_name.value is None
    assert result.supplier.supplier_part_number.value is None
    assert result.supplier.imported_cad_data_statement.value is None
