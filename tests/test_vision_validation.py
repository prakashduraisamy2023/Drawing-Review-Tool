from backend.app.models.drawing import (
    BOMItem,
    DrawingDocument,
    ExtractedField,
    ExtractionMethod,
    TableType,
)
from backend.app.validation import ValidationEngine
from backend.app.vision.models import VisionReport, VisionSummary, VisualObject, VisualObjectType


def _field(value):
    return ExtractedField(
        value=value,
        page_number=1,
        confidence=0.96,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        bounding_box=(10, 10, 20, 20),
    )


def test_visual_balloon_evidence_upgrades_xref_without_changing_level1():
    document = DrawingDocument(
        source_filename=ExtractedField(
            value="drawing.pdf",
            confidence=1,
            extraction_method=ExtractionMethod.FILE_METADATA,
        ),
        page_count=ExtractedField(
            value=1,
            confidence=1,
            extraction_method=ExtractionMethod.PDF_METADATA,
        ),
        bom_items=[
            BOMItem(table_type=TableType.BOM, item_no=_field("1")),
            BOMItem(table_type=TableType.BOM, item_no=_field("2")),
        ],
    )
    objects = [
        VisualObject(
            object_type=VisualObjectType.BOM_BALLOON,
            page_number=1,
            bounding_box=(30 + index * 20, 30, 42 + index * 20, 42),
            confidence=0.95,
            detector="balloon",
            normalized_text=str(index + 1),
            attributes={"item_number": str(index + 1)},
        )
        for index in range(2)
    ]
    vision = VisionReport(
        source_filename="drawing.pdf",
        objects=objects,
        summary=VisionSummary(
            pages_processed=1,
            objects_detected=2,
            objects_by_type={"BOM_BALLOON": 2},
            low_confidence_count=0,
        ),
    )

    without_visual = ValidationEngine().validate(document)
    with_visual = ValidationEngine().validate(document, vision_report=vision)

    before = next(item for item in without_visual.results if item.rule_id == "BOM-011")
    after = next(item for item in with_visual.results if item.rule_id == "BOM-011")
    assert before.status == "NOT_EVALUATED"
    assert after.status == "PASS"
    assert len(after.evidence) == 2
    assert document.bom_items[0].item_no.value == "1"


def test_visual_confidence_gate_separates_partial_from_low_confidence():
    document = DrawingDocument(
        source_filename=ExtractedField(
            value="drawing.pdf",
            confidence=1,
            extraction_method=ExtractionMethod.FILE_METADATA,
        ),
        page_count=ExtractedField(
            value=1,
            confidence=1,
            extraction_method=ExtractionMethod.PDF_METADATA,
        ),
        bom_items=[BOMItem(table_type=TableType.BOM, item_no=_field("1"))],
    )

    def status_for(confidence: float) -> str:
        visual_object = VisualObject(
            object_type=VisualObjectType.BOM_BALLOON,
            page_number=1,
            bounding_box=(30, 30, 42, 42),
            confidence=confidence,
            detector="balloon",
            normalized_text="1",
            attributes={"item_number": "1"},
        )
        report = VisionReport(
            source_filename="drawing.pdf",
            objects=[visual_object],
            summary=VisionSummary(
                pages_processed=1,
                objects_detected=1,
                objects_by_type={"BOM_BALLOON": 1},
                low_confidence_count=1,
            ),
            confidence_thresholds={"BOM_BALLOON": 0.90},
            partial_confidence_floor=0.75,
        )
        validation = ValidationEngine().validate(document, vision_report=report)
        return next(
            result.status for result in validation.results if result.rule_id == "BOM-011"
        )

    assert status_for(0.80) == "WARNING"
    assert status_for(0.70) == "MANUAL_REVIEW"
