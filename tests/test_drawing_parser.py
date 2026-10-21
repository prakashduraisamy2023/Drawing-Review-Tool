from pathlib import Path

import pymupdf
import pytest

from backend.app.extraction import DrawingParser, StandardsExtractor, SupplierInfoExtractor
from backend.app.models.drawing import (
    BOMItem,
    DocumentClassification,
    DocumentType,
    DrawingNote,
    ExtractedField,
    ExtractionMethod,
    RevisionRecord,
    StandardReference,
    SupplierInfo,
    TitleBlock,
)

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def evidence(value, page_number: int = 1) -> ExtractedField:
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=0.96,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=(10, 10, 20, 20),
    )


class StubExtractor:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def extract(self, _path: Path):
        if self.error is not None:
            raise self.error
        return self.result


def make_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((50, 50), "NATIVE DRAWING TEXT")
    document.save(path)
    document.close()
    return path


def parser_with_stubs(*, failing_stage: str | None = None) -> DrawingParser:
    classification = DocumentClassification(
        document_type=DocumentType.STANDARD_DRAWING,
        evidence=evidence("STANDARD DRAWING"),
    )
    title = TitleBlock(
        drawing_number=evidence("DWG-42"),
        revision=evidence("C"),
        units=evidence("mm"),
    )
    revision = RevisionRecord(
        ecn=evidence("ECN-7"),
        revision_description=evidence("INITIAL RELEASE"),
        page_number=1,
        bounding_box=(10, 10, 20, 20),
    )
    note = DrawingNote(
        number=evidence("1"),
        text=evidence("FOLLOW ASME Y14.5"),
        page_number=1,
        bounding_box=(10, 10, 20, 20),
    )
    bom_item = BOMItem(
        item_no=evidence("1"),
        part_number=evidence("PN-42"),
        page_number=1,
        bounding_box=(10, 10, 20, 20),
    )
    supplier = SupplierInfo(supplier_drawing=evidence(False))
    standard = StandardReference(designation=evidence("ASME Y14.5"))
    values = {
        "document_classification": classification,
        "title_block": [title],
        "revision_table": [revision],
        "notes": [note],
        "bom": [bom_item],
        "supplier_info": supplier,
        "standards": [standard],
    }

    def stage(name: str) -> StubExtractor:
        error = RuntimeError(f"{name} unavailable") if name == failing_stage else None
        return StubExtractor(values[name], error)

    return DrawingParser(
        classifier=stage("document_classification"),
        title_block_extractor=stage("title_block"),
        revision_extractor=stage("revision_table"),
        notes_extractor=stage("notes"),
        bom_extractor=stage("bom"),
        supplier_extractor=stage("supplier_info"),
        standards_extractor=stage("standards"),
    )


def test_builds_complete_document_and_page_views(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "drawing.pdf")

    result = parser_with_stubs().parse(source)

    assert result.source_filename.value == "drawing.pdf"
    assert result.page_count.value == 1
    assert result.document_type.value == "STANDARD_DRAWING"
    assert result.drawing_number.value == "DWG-42"
    assert result.revision.value == "C"
    assert result.units.value == "mm"
    assert len(result.revisions or []) == 1
    assert len(result.notes or []) == 1
    assert len(result.bom or []) == 1
    assert len(result.standards or []) == 1
    assert any(warning.code == "E10" for warning in result.warnings)

    page = result.pages[0]
    assert page.native_text_available is True
    assert page.word_count == 3
    assert page.text_block_count == 1
    assert page.title_block.drawing_number.value == "DWG-42"
    assert page.revisions[0].ecn.value == "ECN-7"
    assert page.notes[0].number.value == "1"
    assert page.bom[0].part_number.value == "PN-42"
    assert page.standards[0].designation.value == "ASME Y14.5"

    payload = result.model_dump_json()
    assert '"source_filename"' in payload
    assert '"extraction_warnings"' in payload


@pytest.mark.parametrize(
    "failing_stage",
    [
        "document_classification",
        "title_block",
        "revision_table",
        "notes",
        "bom",
        "supplier_info",
        "standards",
    ],
)
def test_each_extractor_failure_is_non_fatal(
    tmp_path: Path,
    failing_stage: str,
) -> None:
    source = make_pdf(tmp_path / f"{failing_stage}.pdf")

    result = parser_with_stubs(failing_stage=failing_stage).parse(source)

    assert result.source_filename.value == source.name
    assert result.page_count.value == 1
    assert result.pages[0].native_text_available is True
    assert any(
        warning.stage == failing_stage
        and warning.exception_type == "RuntimeError"
        and warning.message == f"{failing_stage} unavailable"
        for warning in result.warnings
    )


def test_invalid_pdf_returns_partial_document_with_warnings(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a PDF")

    result = DrawingParser().parse(source)

    assert result.source_filename.value == "broken.pdf"
    assert result.page_count.value is None
    assert result.pages == []
    assert {warning.stage for warning in result.warnings}.issuperset(
        {
            "document_inspection",
            "page_text_blocks",
            "document_classification",
            "title_block",
            "revision_table",
            "notes",
            "bom",
            "supplier_info",
            "standards",
        }
    )


def test_blank_unknown_layout_returns_null_fields_and_readable_warnings(
    tmp_path: Path,
) -> None:
    source = tmp_path / "blank.pdf"
    document = pymupdf.open()
    document.new_page(width=500, height=500)
    document.save(source)
    document.close()

    result = DrawingParser().parse(source)

    assert result.page_count.value == 1
    assert result.drawing_number.value is None
    assert result.notes == []
    assert result.bom == [] or result.bom is None
    assert {warning.code for warning in result.extraction_warnings} >= {
        "E02",
        "E09",
        "E10",
    }
    assert result.level1_summary.processing_state == "SUCCESS_WITH_WARNINGS"


def test_real_multisheet_drawing_is_assembled_without_warnings() -> None:
    result = DrawingParser().parse(SAMPLES / "47789413_C_watermarked.pdf")

    assert result.page_count.value == 5
    assert result.document_type.value == "STANDARD_DRAWING"
    assert result.drawing_number.value == "47789413"
    assert result.revision.value == "C"
    assert result.part_name.value is None
    assert len(result.pages) == 5
    assert len(result.revisions) == 5
    assert len(result.notes) == 15
    assert len(result.bom) == 8
    assert len(result.bom_items) == 6
    assert len(result.part_list_items) == 2
    assert result.service_part_items == []
    assert result.warnings == []


def test_supplier_and_standards_extractors_return_structured_evidence() -> None:
    supplier = SupplierInfoExtractor().extract(SAMPLES / "47789660_A_watermarked.pdf")
    standards = StandardsExtractor().extract(SAMPLES / "47789413_C_watermarked.pdf")

    assert supplier.supplier_drawing.value is True
    assert supplier.supplier_name.value == "SUPREME"
    assert supplier.supplier_part_number.value == "ASBK9660001"
    assert all(reference.designation.bounding_box is not None for reference in standards)
    assert len({reference.designation.value for reference in standards}) == len(standards)
