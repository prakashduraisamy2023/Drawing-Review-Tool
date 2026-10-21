from backend.app.config import Settings
from backend.app.extraction import DrawingExtractionPipeline


def pipeline() -> DrawingExtractionPipeline:
    return DrawingExtractionPipeline(Settings(ocr_enabled=False))


def test_extracts_explicit_fields_with_provenance(synthetic_drawing):
    result = pipeline().extract(synthetic_drawing)

    assert result.filename.value == synthetic_drawing.name
    assert result.page_count.value == 1
    assert result.document_type.value == "supplier drawing"
    assert result.drawing_number.value == "ZX-42017"
    assert result.revision.value == "D"
    assert result.drawing_size.value == "B"
    assert result.part_name.value == "ACTUATOR BRACKET"
    assert result.ecn.value == "ECN-2041"
    assert result.revision_description.value == "UPDATED MOUNTING SLOT"
    assert result.drawing_date.value == "03/14/2026"
    assert result.release_date.value == "17/Mar/2026"
    assert result.drawn_by.value == "J_SMITH"
    assert result.modeled_by.value == "A_JONES"
    assert result.approved_by.value == "R_APPROVER"
    assert result.scale.value == "1:2"
    assert result.units.value.lower() == "mm"
    assert result.weight.value == "2.45"
    assert result.sheet_number.value == 1
    assert result.total_sheets.value == 2
    assert result.critical_component_indicator.value is True
    assert result.supplier_drawing_indicator.value is True
    assert result.supplier_name.value == "ACME FABRICATION"
    assert result.supplier_part_number.value == "SF-88"
    assert result.notes.value and len(result.notes.value) == 2
    assert "ASME Y14.5-2018" in result.referenced_engineering_standards.value

    for _, field in result:
        assert 0 <= field.confidence <= 1
        if field.value is not None and field.page is not None:
            assert field.extraction_method is not None


def test_unknown_fields_remain_null(blank_pdf):
    result = pipeline().extract(blank_pdf)

    assert result.filename.value == "blank.pdf"
    assert result.page_count.value == 1
    assert result.drawing_number.value is None
    assert result.drawing_number.page is None
    assert result.drawing_number.confidence == 0
    assert result.drawing_number.extraction_method is None
    assert result.critical_component_indicator.value is None
    assert result.supplier_drawing_indicator.value is None


def test_serialized_contract_contains_all_required_fields(blank_pdf):
    payload = pipeline().extract(blank_pdf).model_dump()
    expected = {
        "filename",
        "document_type",
        "page_count",
        "drawing_number",
        "revision",
        "drawing_size",
        "part_name",
        "part_numbers",
        "ecn",
        "revision_description",
        "drawing_date",
        "release_date",
        "drawn_by",
        "modeled_by",
        "approved_by",
        "scale",
        "units",
        "weight",
        "sheet_number",
        "total_sheets",
        "critical_component_indicator",
        "supplier_drawing_indicator",
        "supplier_name",
        "supplier_part_number",
        "notes",
        "bom",
        "referenced_engineering_standards",
    }
    assert set(payload) == expected
    assert all(
        set(field) == {"value", "page", "confidence", "extraction_method"}
        for field in payload.values()
    )
