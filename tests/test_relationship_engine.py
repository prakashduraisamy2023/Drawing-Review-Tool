from backend.app.models.drawing import (
    BOMItem,
    DrawingDocument,
    DrawingNote,
    ExtractedField,
    ExtractionMethod,
    RevisionRecord,
    TableType,
)
from backend.app.relationships import RelationshipEngine
from backend.app.vision.models import VisionReport, VisionSummary, VisualObject, VisualObjectType


def field(value, box=(10, 10, 20, 20), confidence=0.96):
    return ExtractedField(
        value=value,
        page_number=1,
        bounding_box=box,
        confidence=confidence,
        extraction_method=ExtractionMethod.NATIVE_TEXT,
    )


def relationship_document() -> DrawingDocument:
    return DrawingDocument(
        source_filename=ExtractedField(
            value="relationship.pdf",
            confidence=1,
            extraction_method=ExtractionMethod.FILE_METADATA,
        ),
        page_count=ExtractedField(
            value=1,
            confidence=1,
            extraction_method=ExtractionMethod.PDF_METADATA,
        ),
        drawing_number=field("D-100"),
        revision=field("C", (20, 20, 30, 30)),
        revision_records=[
            RevisionRecord(
                revision=field("C", (30, 20, 40, 30)),
                page_number=1,
                bounding_box=(30, 20, 100, 35),
            )
        ],
        notes=[
            DrawingNote(
                number=field("6", (30, 40, 40, 50)),
                text=field("APPLY FINISH", (40, 40, 100, 50)),
                page_number=1,
                bounding_box=(30, 40, 100, 50),
            )
        ],
        bom_items=[
            BOMItem(
                table_type=TableType.BOM,
                item_no=field("1", (30, 60, 40, 70)),
                quantity=field("1", (40, 60, 50, 70)),
                part_number=field("P-1", (50, 60, 80, 70)),
                page_number=1,
                bounding_box=(30, 60, 100, 72),
            )
        ],
    )


def relationship_vision() -> VisionReport:
    objects = [
        VisualObject(
            object_type=VisualObjectType.BOM_BALLOON,
            page_number=1,
            bounding_box=(200, 100, 220, 120),
            confidence=0.96,
            detector="balloon",
            normalized_text="1",
            attributes={
                "item_number": "1",
                "shape": "split_circle",
                "lower_compartment_text": "1",
            },
        ),
        VisualObject(
            object_type=VisualObjectType.FLAG_NOTE,
            page_number=1,
            bounding_box=(230, 100, 250, 120),
            confidence=0.95,
            detector="flag_note",
            normalized_text="6",
            attributes={"note_number": "6"},
        ),
        VisualObject(
            object_type=VisualObjectType.REVISION_TRIANGLE,
            page_number=1,
            bounding_box=(260, 100, 280, 120),
            confidence=0.95,
            detector="revision_triangle",
            normalized_text="C",
            attributes={"candidate_revision_identifier": "C"},
        ),
        VisualObject(
            object_type=VisualObjectType.DATUM_SYMBOL,
            page_number=1,
            bounding_box=(290, 100, 310, 120),
            confidence=0.95,
            detector="datum",
            normalized_text="A",
            attributes={"identifier": "A"},
        ),
        VisualObject(
            object_type=VisualObjectType.GDT_FRAME,
            page_number=1,
            bounding_box=(320, 100, 380, 120),
            confidence=0.95,
            detector="gdt_frame",
            normalized_text="POSITION | A",
            attributes={"recognized_tokens": ["POSITION", "A"], "datum_sequence": ["A"]},
        ),
    ]
    return VisionReport(
        source_filename="relationship.pdf",
        objects=objects,
        summary=VisionSummary(
            pages_processed=1,
            objects_detected=len(objects),
            objects_by_type={str(item.object_type): 1 for item in objects},
            low_confidence_count=0,
        ),
        confidence_thresholds={str(item.object_type): 0.90 for item in objects},
    )


def test_relationship_engine_builds_traceable_graph_and_findings():
    report = RelationshipEngine().analyze(
        relationship_document(),
        drawing_id="drawing-id",
        vision_report=relationship_vision(),
    )

    rule_ids = {item.relationship_rule_id for item in report.findings}
    assert {
        "REL-BOM-001",
        "REL-BOM-002",
        "REL-BOM-003",
        "REL-REV-001",
        "REL-REV-002",
        "REL-NOTE-001",
        "REL-SCC-001",
        "REL-GDT-001",
        "REL-GDT-002",
        "REL-SUP-001",
        "REL-PART-001",
        "REL-DOC-001",
    }.issubset(rule_ids)
    bom = next(item for item in report.findings if item.relationship_rule_id == "REL-BOM-001")
    note = next(item for item in report.findings if item.relationship_rule_id == "REL-NOTE-001")
    gdt = next(item for item in report.findings if item.relationship_rule_id == "REL-GDT-001")
    quantity = next(
        item for item in report.findings if item.relationship_rule_id == "REL-BOM-003"
    )
    assert bom.status == "PASS"
    assert note.status == "PASS"
    assert gdt.status == "PASS"
    assert quantity.status == "MANUAL_REVIEW"
    assert "lower-compartment total=1" in quantity.actual_relationship
    assert all(item.evidence for item in [bom, note, gdt])
    assert all(evidence.page_number == 1 for item in [bom, note, gdt] for evidence in item.evidence)
    assert report.graph.nodes
    assert any(edge.relationship_type == "CALLED_OUT_BY" for edge in report.graph.edges)
    assert report.timing.level4_relationship_ms >= 0


def test_relationship_engine_does_not_infer_missing_visual_dependencies():
    report = RelationshipEngine().analyze(relationship_document())
    bom = next(item for item in report.findings if item.relationship_rule_id == "REL-BOM-001")
    revision = next(item for item in report.findings if item.relationship_rule_id == "REL-REV-001")
    assert bom.status == "NOT_EVALUATED"
    assert revision.status == "NOT_EVALUATED"


def test_split_balloon_quantity_difference_remains_review_assistance():
    document = relationship_document()
    document.bom_items[0].quantity = field("2", (40, 60, 50, 70))

    report = RelationshipEngine().analyze(document, vision_report=relationship_vision())

    quantity = next(
        item for item in report.findings if item.relationship_rule_id == "REL-BOM-003"
    )
    assert quantity.status == "WARNING"
    assert "BOM quantity=2" in quantity.actual_relationship
    assert "lower-compartment total=1" in quantity.actual_relationship
    assert "not proof" in quantity.explanation
