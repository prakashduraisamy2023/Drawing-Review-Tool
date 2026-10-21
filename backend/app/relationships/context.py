"""Read-only bridge from Levels 1-3 into Level-4 engineering entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.models.drawing import BOMItem, DrawingDocument, ExtractedField
from backend.app.relationships.graph import EngineeringGraph, stable_id
from backend.app.relationships.models import (
    EngineeringEntity,
    EntityType,
    RelationshipEvidence,
    SourceLevel,
)
from backend.app.validation.models import ValidationReport
from backend.app.vision.models import VisionReport

VISUAL_ENTITY_TYPES = {
    "REVISION_TRIANGLE": EntityType.REVISION_TRIANGLE,
    "BOM_BALLOON": EntityType.BALLOON,
    "SCC_SYMBOL": EntityType.SCC_SYMBOL,
    "CRITICAL_SYMBOL": EntityType.SCC_SYMBOL,
    "DATUM_SYMBOL": EntityType.DATUM,
    "GDT_FRAME": EntityType.GDT_FRAME,
    "FLAG_NOTE": EntityType.NOTE_CALLOUT,
}


@dataclass
class RelationshipContext:
    document: DrawingDocument
    validation_report: ValidationReport | None
    vision_report: VisionReport | None
    configuration: dict[str, Any]
    graph: EngineeringGraph = field(default_factory=EngineeringGraph)
    by_type: dict[str, list[EngineeringEntity]] = field(default_factory=dict)

    @property
    def automatic_threshold(self) -> float:
        return float(self.configuration.get("automatic_confidence", 0.90))

    @property
    def partial_floor(self) -> float:
        return float(self.configuration.get("partial_confidence_floor", 0.75))

    def add(self, entity: EngineeringEntity) -> EngineeringEntity:
        self.graph.add_entity(entity)
        self.by_type.setdefault(str(entity.entity_type), []).append(entity)
        return entity

    def entities(self, entity_type: EntityType) -> list[EngineeringEntity]:
        return self.by_type.get(str(entity_type), [])

    @staticmethod
    def evidence(entity: EngineeringEntity) -> RelationshipEvidence:
        return RelationshipEvidence(
            page_number=entity.page_number,
            bounding_box=entity.bounding_box,
            source_level=entity.source_level,
            source_reference=entity.source_reference,
            value=entity.value,
            confidence=entity.confidence,
            extraction_method=entity.attributes.get("extraction_method"),
        )

    def build_entities(self) -> None:
        drawing = self.add(
            EngineeringEntity(
                entity_id=stable_id("drawing", self.document.source_filename.value),
                entity_type=EntityType.DRAWING,
                value=self.document.drawing_number.value,
                page_number=self.document.drawing_number.page_number,
                bounding_box=self.document.drawing_number.bounding_box,
                source_level=SourceLevel.LEVEL_1,
                confidence=self.document.drawing_number.confidence,
                source_reference="drawing.drawing_number",
                attributes={
                    "source_filename": self.document.source_filename.value,
                    "extraction_method": self.document.drawing_number.extraction_method,
                },
            )
        )
        for page in self.document.pages or []:
            sheet = self.add(
                EngineeringEntity(
                    entity_id=stable_id("sheet", drawing.entity_id, page.page_number),
                    entity_type=EntityType.SHEET,
                    value=page.page_number,
                    page_number=page.page_number,
                    source_level=SourceLevel.LEVEL_1,
                    confidence=1.0,
                    source_reference=f"drawing.pages[{page.page_number - 1}]",
                    attributes={"width": page.width, "height": page.height},
                )
            )
            self.graph.add_relationship(
                "BELONGS_TO",
                sheet,
                drawing,
                status="PASS",
                confidence=1.0,
                evidence=[self.evidence(sheet)],
                explanation=f"Sheet {page.page_number} belongs to the uploaded drawing.",
            )

        self._add_field_entity(
            EntityType.TITLE_BLOCK, self.document.drawing_number, "drawing.drawing_number"
        )
        self._add_field_entity(
            EntityType.REVISION,
            self.document.revision,
            "drawing.revision",
            attributes={"role": "CURRENT"},
        )

        for index, record in enumerate(self.document.revision_records or []):
            self._add_field_entity(
                EntityType.REVISION,
                record.revision,
                f"drawing.revision_records[{index}].revision",
                page_number=record.page_number,
                bounding_box=record.bounding_box,
                attributes={"role": "TABLE_ENTRY", "index": index},
            )
        for index, note in enumerate(self.document.notes or []):
            self._add_field_entity(
                EntityType.NOTE,
                note.number,
                f"drawing.notes[{index}].number",
                page_number=note.page_number,
                bounding_box=note.bounding_box,
                attributes={"text": note.text.value, "index": index},
            )
        self._add_table_entities(self.document.bom_items or [], EntityType.BOM_ITEM, "bom_items")
        self._add_table_entities(
            self.document.part_list_items or [], EntityType.PART_LIST_ITEM, "part_list_items"
        )
        self._add_table_entities(
            self.document.service_part_items or [], EntityType.SERVICE_PART, "service_part_items"
        )

        for index, standard in enumerate(self.document.standard_references or []):
            self._add_field_entity(
                EntityType.STANDARD_REFERENCE,
                standard.designation,
                f"drawing.standard_references[{index}].designation",
                attributes={"description": standard.description.value},
            )

        supplier = self.document.supplier_info
        if supplier is not None and supplier.supplier_name.value:
            self._add_field_entity(
                EntityType.SUPPLIER,
                supplier.supplier_name,
                "drawing.supplier_info.supplier_name",
            )
        if supplier is not None:
            values: list[str] = []
            if supplier.supplier_part_number.value:
                values.append(str(supplier.supplier_part_number.value))
            values.extend(str(value) for value in supplier.supplier_part_numbers.value or [])
            for index, value in enumerate(dict.fromkeys(values)):
                field = supplier.supplier_part_number
                self.add(
                    EngineeringEntity(
                        entity_id=stable_id("supplier-part", index, value),
                        entity_type=EntityType.SUPPLIER_PART,
                        value=value,
                        page_number=field.page_number,
                        bounding_box=field.bounding_box,
                        source_level=SourceLevel.LEVEL_1,
                        confidence=field.confidence,
                        source_reference="drawing.supplier_info.supplier_part_numbers",
                        attributes={"extraction_method": field.extraction_method},
                    )
                )

        if self.vision_report is not None:
            for visual in self.vision_report.objects:
                entity_type = VISUAL_ENTITY_TYPES.get(
                    str(visual.object_type), EntityType.VISUAL_OBJECT
                )
                value = (
                    visual.attributes.get("item_number")
                    or visual.attributes.get("identifier")
                    or visual.attributes.get("note_number")
                    or visual.attributes.get("candidate_revision_identifier")
                    or visual.normalized_text
                    or visual.raw_text
                )
                self.add(
                    EngineeringEntity(
                        entity_id=f"visual-{visual.object_id}",
                        entity_type=entity_type,
                        value=value,
                        page_number=visual.page_number,
                        bounding_box=visual.bounding_box,
                        source_level=SourceLevel.LEVEL_3,
                        confidence=visual.confidence,
                        source_reference=f"vision.objects.{visual.object_id}",
                        attributes={
                            **visual.attributes,
                            "visual_object_type": visual.object_type,
                            "detector": visual.detector,
                            "extraction_method": visual.extraction_method,
                        },
                    )
                )

    def _add_field_entity(
        self,
        entity_type: EntityType,
        extracted: ExtractedField[Any],
        source_reference: str,
        *,
        page_number: int | None = None,
        bounding_box: tuple[float, float, float, float] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> EngineeringEntity | None:
        if extracted.value is None:
            return None
        return self.add(
            EngineeringEntity(
                entity_id=stable_id(entity_type.lower(), source_reference, extracted.value),
                entity_type=entity_type,
                value=extracted.value,
                page_number=extracted.page_number or page_number,
                bounding_box=extracted.bounding_box or bounding_box,
                source_level=SourceLevel.LEVEL_1,
                confidence=extracted.confidence,
                source_reference=source_reference,
                attributes={
                    **(attributes or {}),
                    "raw_text": extracted.raw_text,
                    "extraction_method": extracted.extraction_method,
                },
            )
        )

    def _add_table_entities(
        self, rows: list[BOMItem], entity_type: EntityType, source_name: str
    ) -> None:
        for index, row in enumerate(rows):
            if row.item_no.value is None:
                continue
            self._add_field_entity(
                entity_type,
                row.item_no,
                f"drawing.{source_name}[{index}].item_no",
                page_number=row.page_number,
                bounding_box=row.bounding_box,
                attributes={
                    "quantity": row.quantity.value,
                    "part_number": row.part_number.value,
                    "description": row.description.value,
                    "table_type": row.table_type,
                    "index": index,
                },
            )
