"""Read-only validation context built from the canonical Level-1 document."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.models.drawing import DrawingDocument, ExtractedField
from backend.app.validation.models import ValidationEvidence
from backend.app.vision.confidence import ConfidenceGate, gate_object, threshold_for
from backend.app.vision.models import VisionReport, VisualObject


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_controlled_config(path: Path) -> dict[str, Any]:
    """Load JSON-compatible YAML from a repository-controlled config directory."""
    config_root = (project_root() / "config").resolve()
    resolved = path.resolve()
    if config_root not in resolved.parents:
        raise ValueError("Validation config must be under the controlled config directory")
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Validation config root must be an object")
    return data


@dataclass(frozen=True)
class ValidationContext:
    document: DrawingDocument
    configuration: dict[str, Any]
    rule_master_data: dict[str, Any] | None = None
    vision_report: VisionReport | None = None

    @property
    def minimum_confidence(self) -> float:
        return float(self.configuration.get("minimum_confidence", 0.75))

    @property
    def document_type(self) -> str | None:
        return self.document.document_type.value

    def document_field(self, name: str) -> ExtractedField[Any]:
        value = getattr(self.document, name, None)
        return value if isinstance(value, ExtractedField) else ExtractedField()

    def page_fields(self, name: str) -> list[tuple[int, ExtractedField[Any]]]:
        fields: list[tuple[int, ExtractedField[Any]]] = []
        for page in self.document.pages or []:
            if page.title_block is not None:
                value = getattr(page.title_block, name, None)
                if isinstance(value, ExtractedField):
                    fields.append((page.page_number, value))
        return fields

    def evidence(self, source_field: str, field: ExtractedField[Any]) -> ValidationEvidence:
        return ValidationEvidence(
            page_number=field.page_number,
            bounding_box=field.bounding_box,
            source_field=source_field,
            extracted_value=field.value,
            raw_text=field.raw_text,
            extraction_method=field.extraction_method,
            confidence=field.confidence,
        )

    def has_reliable_value(self, field: ExtractedField[Any]) -> bool:
        return field.value is not None and field.confidence >= self.minimum_confidence

    def rule_config(self, rule_id: str) -> dict[str, Any]:
        value = self.configuration.get("rules", {}).get(rule_id, {})
        return value if isinstance(value, dict) else {}

    def visual_objects(self, object_type: str) -> list[VisualObject]:
        if self.vision_report is None:
            return []
        return [item for item in self.vision_report.objects if str(item.object_type) == object_type]

    def reliable_visual_objects(self, object_type: str) -> list[VisualObject]:
        if self.vision_report is None:
            return []
        threshold = threshold_for(object_type, self.vision_report.confidence_thresholds)
        return [item for item in self.visual_objects(object_type) if item.confidence >= threshold]

    def partial_visual_objects(self, object_type: str) -> list[VisualObject]:
        if self.vision_report is None:
            return []
        return [
            item
            for item in self.visual_objects(object_type)
            if gate_object(
                item,
                self.vision_report.confidence_thresholds,
                partial_floor=self.vision_report.partial_confidence_floor,
            )
            == ConfidenceGate.PARTIAL
        ]

    @staticmethod
    def visual_evidence(item: VisualObject) -> ValidationEvidence:
        return ValidationEvidence(
            page_number=item.page_number,
            bounding_box=item.bounding_box,
            source_field=f"vision.objects.{item.object_id}",
            extracted_value=item.normalized_text or item.attributes,
            raw_text=item.raw_text,
            extraction_method=item.extraction_method,
            confidence=item.confidence,
        )


@dataclass(frozen=True)
class ApplicabilityContext:
    document_type: str | None
    page_count: int | None
    has_notes: bool
    has_bom: bool
    has_part_list: bool
    has_service_parts: bool
    has_standards: bool
    has_supplier_raster: bool

    @classmethod
    def from_validation_context(cls, context: ValidationContext) -> ApplicabilityContext:
        document = context.document
        return cls(
            document_type=context.document_type,
            page_count=document.page_count.value,
            has_notes=bool(document.notes),
            has_bom=bool(document.bom_items),
            has_part_list=bool(document.part_list_items),
            has_service_parts=bool(document.service_part_items),
            has_standards=bool(document.standard_references),
            has_supplier_raster=bool(document.supplier_raster_regions),
        )
