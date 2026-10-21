import pytest
from pydantic import ValidationError

from backend.app.models.drawing import (
    BOMItem,
    DrawingDocument,
    DrawingNote,
    DrawingPage,
    ExtractedField,
    ExtractionMethod,
    RevisionRecord,
    StandardReference,
    SupplierInfo,
    TitleBlock,
)


def field(value, *, page_number=1, bounding_box=None):
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=0.95,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=bounding_box,
    )


def test_extracted_field_serializes_complete_provenance():
    extracted = field("DWG-100", bounding_box=(10.0, 20.0, 80.0, 40.0))

    assert extracted.model_dump(mode="json") == {
        "value": "DWG-100",
        "page_number": 1,
        "confidence": 0.95,
        "extraction_method": "coordinate_text",
        "bounding_box": [10.0, 20.0, 80.0, 40.0],
        "raw_text": None,
        "evidence_anchor": None,
        "confidence_category": "HIGH",
    }


def test_unknown_field_uses_null_provenance_without_guessing():
    assert ExtractedField[str]().model_dump() == {
        "value": None,
        "page_number": None,
        "confidence": 0.0,
        "extraction_method": None,
        "bounding_box": None,
        "raw_text": None,
        "evidence_anchor": None,
        "confidence_category": "UNKNOWN",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "A", "confidence": 0.9},
        {"value": "A", "confidence": 0.0, "extraction_method": "native_text"},
        {"value": None, "confidence": 0.5},
        {"value": None, "page_number": 1},
        {
            "value": "A",
            "page_number": 1,
            "confidence": 0.9,
            "extraction_method": "native_text",
            "bounding_box": (20, 10, 5, 30),
        },
        {
            "value": "A",
            "confidence": 0.9,
            "extraction_method": "native_text",
            "bounding_box": (0, 0, 10, 10),
        },
    ],
)
def test_extracted_field_rejects_inconsistent_evidence(payload):
    with pytest.raises(ValidationError):
        ExtractedField[str](**payload)


def test_document_defaults_every_requested_unknown_to_null():
    payload = DrawingDocument().model_dump()
    extracted_names = {
        "source_filename",
        "page_count",
        "document_type",
        "drawing_number",
        "revision",
        "drawing_size",
        "part_name",
        "part_numbers",
        "units",
        "scale",
        "weight",
        "sheet_number",
        "total_sheets",
        "critical_component",
        "release_date",
        "drawing_date",
        "drawn_by",
        "modeled_by",
        "approved_by",
    }

    assert extracted_names.issubset(payload)
    assert all(payload[name]["value"] is None for name in extracted_names)
    assert payload["revision_records"] is None
    assert payload["notes"] is None
    assert payload["bom_items"] is None
    assert payload["part_list_items"] is None
    assert payload["service_part_items"] is None
    assert payload["supplier_info"] is None
    assert payload["standard_references"] is None
    assert payload["pages"] is None


def test_nested_drawing_models_preserve_item_level_evidence():
    title_block = TitleBlock(drawing_number=field("DWG-100"), revision=field("C"))
    revision = RevisionRecord(
        revision=field("C"),
        ecn=field("ECN-42"),
        revision_description=field("UPDATED SLOT"),
    )
    note = DrawingNote(number=field("1"), text=field("REMOVE BURRS"))
    bom_item = BOMItem(
        item_number=field("1"),
        quantity=field("2"),
        part_number=field("PN-20"),
    )
    supplier = SupplierInfo(
        supplier_drawing=field(True),
        supplier_name=field("EXAMPLE SUPPLIER"),
    )
    standard = StandardReference(designation=field("ASME Y14.5-2018"))
    page = DrawingPage(
        page_number=1,
        width=1224,
        height=792,
        title_block=title_block,
        revisions=[revision],
        notes=[note],
        bom=[bom_item],
        supplier=supplier,
        standards=[standard],
    )
    document = DrawingDocument(
        source_filename=ExtractedField(
            value="drawing.pdf",
            confidence=1.0,
            extraction_method=ExtractionMethod.FILE_METADATA,
        ),
        page_count=ExtractedField(
            value=1,
            confidence=1.0,
            extraction_method=ExtractionMethod.PDF_METADATA,
        ),
        drawing_number=field("DWG-100"),
        revisions=[revision],
        notes=[note],
        bom=[bom_item],
        supplier=supplier,
        standards=[standard],
        pages=[page],
    )

    payload = document.model_dump(mode="json")
    assert payload["drawing_number"]["bounding_box"] is None
    assert payload["revision_records"][0]["ecn"]["value"] == "ECN-42"
    assert payload["pages"][0]["title_block"]["revision"]["value"] == "C"
    assert payload["supplier_info"]["supplier_drawing"]["value"] is True
    assert payload["standard_references"][0]["designation"]["page_number"] == 1
