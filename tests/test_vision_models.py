from backend.app.vision.confidence import ConfidenceGate, gate_object
from backend.app.vision.models import (
    DetectorResult,
    VisionReport,
    VisionSummary,
    VisualObject,
    VisualObjectType,
)


def test_visual_model_serialization_preserves_provenance():
    visual_object = VisualObject(
        object_type=VisualObjectType.BOM_BALLOON,
        page_number=2,
        bounding_box=(10, 20, 30, 40),
        confidence=0.94,
        detector="balloon",
        raw_text="14",
        normalized_text="14",
        attributes={"item_number": "14"},
    )
    result = DetectorResult(detector_name="balloon", objects=[visual_object])
    report = VisionReport(
        source_filename="drawing.pdf",
        detector_results=[result],
        objects=[visual_object],
        summary=VisionSummary(
            pages_processed=2,
            objects_detected=1,
            objects_by_type={"BOM_BALLOON": 1},
            low_confidence_count=0,
        ),
    )

    restored = VisionReport.model_validate_json(report.model_dump_json())

    assert restored.objects[0].page_number == 2
    assert restored.objects[0].bounding_box == (10, 20, 30, 40)
    assert restored.objects[0].detector == "balloon"
    assert restored.objects[0].attributes["item_number"] == "14"


def test_confidence_gate_is_per_object_class():
    item = VisualObject(
        object_type=VisualObjectType.BOM_BALLOON,
        page_number=1,
        bounding_box=(0, 0, 10, 10),
        confidence=0.86,
        detector="test",
    )
    assert gate_object(item, {"BOM_BALLOON": 0.85}) == ConfidenceGate.AUTOMATIC
    assert gate_object(item, {"BOM_BALLOON": 0.90}) == ConfidenceGate.PARTIAL
