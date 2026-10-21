"""Evidence-preserving Level-1 engineering-drawing schema.

The models describe extracted PDF content only. Dates, identifiers, units, and
other engineering values remain strings so extraction does not silently
normalize, interpret, or validate the source drawing.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ExtractionMethod(StrEnum):
    """Supported evidence sources for a field value."""

    FILE_METADATA = "file_metadata"
    PDF_METADATA = "pdf_metadata"
    NATIVE_TEXT = "native_text"
    COORDINATE_TEXT = "coordinate_text"
    TABLE = "pdfplumber_table"
    OCR = "ocr"
    TARGETED_OCR = "targeted_ocr"
    IMAGE_REGION = "image_region"


class DocumentType(StrEnum):
    STANDARD_DRAWING = "STANDARD_DRAWING"
    SUPPLIER_DRAWING = "SUPPLIER_DRAWING"
    UNKNOWN = "UNKNOWN"


class TableType(StrEnum):
    BOM = "BOM"
    PART_LIST = "PART_LIST"
    SERVICE_PARTS = "SERVICE_PARTS"
    UNKNOWN = "UNKNOWN"


class ConfidenceCategory(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class WarningSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProcessingState(StrEnum):
    SUCCESS = "SUCCESS"
    SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
    FAILED = "FAILED"


ValueT = TypeVar("ValueT")
BoundingBox = tuple[float, float, float, float]


class DrawingModel(BaseModel):
    """Shared strict configuration for the public drawing schema."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )


class ExtractedField(DrawingModel, Generic[ValueT]):
    """One extracted value and the evidence describing its origin.

    Bounding boxes use PDF coordinates in ``(x0, y0, x1, y1)`` order. A field
    with no extracted value is represented by the defaults: a null value and
    provenance, with zero confidence.
    """

    value: ValueT | None = None
    page_number: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: ExtractionMethod | None = None
    bounding_box: BoundingBox | None = None
    raw_text: str | None = None
    evidence_anchor: str | None = None
    confidence_category: ConfidenceCategory = Field(
        default=ConfidenceCategory.UNKNOWN,
        validate_default=True,
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> ExtractedField[ValueT]:
        if self.bounding_box is not None:
            x0, y0, x1, y1 = self.bounding_box
            if not all(math.isfinite(coordinate) for coordinate in self.bounding_box):
                raise ValueError("bounding_box coordinates must be finite")
            if x1 < x0 or y1 < y0:
                raise ValueError("bounding_box must satisfy x0 <= x1 and y0 <= y1")
            if self.page_number is None:
                raise ValueError("bounding_box requires page_number")

        if self.value is None:
            if self.page_number is not None:
                raise ValueError("an unknown value cannot have page_number evidence")
            if self.confidence != 0.0:
                raise ValueError("an unknown value must have zero confidence")
            if self.extraction_method is not None:
                raise ValueError("an unknown value cannot have an extraction_method")
            if self.bounding_box is not None:
                raise ValueError("an unknown value cannot have a bounding_box")
            if self.raw_text is not None or self.evidence_anchor is not None:
                raise ValueError("an unknown value cannot have textual evidence")
            object.__setattr__(self, "confidence_category", ConfidenceCategory.UNKNOWN.value)
        else:
            if self.confidence <= 0.0:
                raise ValueError("an extracted value must have positive confidence")
            if self.extraction_method is None:
                raise ValueError("an extracted value requires an extraction_method")
            category = (
                ConfidenceCategory.HIGH
                if self.confidence >= 0.90
                else ConfidenceCategory.MEDIUM
                if self.confidence >= 0.75
                else ConfidenceCategory.LOW
            )
            object.__setattr__(self, "confidence_category", category.value)

        return self


def _unknown_field() -> ExtractedField[object]:
    return ExtractedField()


class TitleBlock(DrawingModel):
    drawing_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawing_size: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_name: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_numbers: ExtractedField[list[str]] = Field(default_factory=_unknown_field)
    units: ExtractedField[str] = Field(default_factory=_unknown_field)
    scale: ExtractedField[str] = Field(default_factory=_unknown_field)
    weight: ExtractedField[str] = Field(default_factory=_unknown_field)
    sheet_number: ExtractedField[int] = Field(default_factory=_unknown_field)
    sheet_count: ExtractedField[int] = Field(default_factory=_unknown_field)
    critical_component: ExtractedField[bool] = Field(default_factory=_unknown_field)
    drawing_date: ExtractedField[str] = Field(default_factory=_unknown_field)
    release_date: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawn_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    modeled_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    approved_by: ExtractedField[str] = Field(default_factory=_unknown_field)


class RevisionRecord(DrawingModel):
    revision: ExtractedField[str] = Field(default_factory=_unknown_field)
    ecn: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision_description: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision_date: ExtractedField[str] = Field(default_factory=_unknown_field)
    changed_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    approved_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None

    @property
    def description_of_change(self) -> ExtractedField[str]:
        return self.revision_description

    @property
    def date(self) -> ExtractedField[str]:
        return self.revision_date


class StandardReference(DrawingModel):
    designation: ExtractedField[str] = Field(default_factory=_unknown_field)
    description: ExtractedField[str] = Field(default_factory=_unknown_field)


class DrawingNote(DrawingModel):
    number: ExtractedField[str] = Field(default_factory=_unknown_field)
    text: ExtractedField[str] = Field(default_factory=_unknown_field)
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    standards: list[StandardReference] | None = None


class BOMItem(DrawingModel):
    table_type: TableType = Field(default=TableType.UNKNOWN, validate_default=True)
    item_no: ExtractedField[str] = Field(
        default_factory=_unknown_field,
        validation_alias=AliasChoices("item_no", "item_number"),
    )
    quantity: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    description: ExtractedField[str] = Field(default_factory=_unknown_field)
    material: ExtractedField[str] = Field(default_factory=_unknown_field)
    remarks: ExtractedField[str] = Field(default_factory=_unknown_field)
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None

    @property
    def item_number(self) -> ExtractedField[str]:
        """Backward-compatible attribute for the earlier schema spelling."""
        return self.item_no


class SupplierInfo(DrawingModel):
    supplier_drawing: ExtractedField[bool] = Field(default_factory=_unknown_field)
    supplier_name: ExtractedField[str] = Field(default_factory=_unknown_field)
    supplier_part_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    supplier_part_numbers: ExtractedField[list[str]] = Field(default_factory=_unknown_field)
    supplier_drawing_marker: ExtractedField[str] = Field(default_factory=_unknown_field)
    imported_cad_data_statement: ExtractedField[str] = Field(default_factory=_unknown_field)
    manufacturer_name: ExtractedField[str] = Field(default_factory=_unknown_field)
    manufacturer_part_number_mappings: list[ManufacturerPartMapping] | None = None


class ManufacturerPartMapping(DrawingModel):
    source_part_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    manufacturer_part_number: ExtractedField[str] = Field(default_factory=_unknown_field)


class DocumentClassification(DrawingModel):
    document_type: DocumentType = Field(
        default=DocumentType.UNKNOWN,
        validate_default=True,
    )
    evidence: ExtractedField[str] = Field(default_factory=_unknown_field)
    supplier: SupplierInfo = Field(default_factory=SupplierInfo)


class ExtractionWarning(DrawingModel):
    """A non-fatal problem encountered during one parser stage."""

    stage: str
    message: str
    page_number: int | None = Field(default=None, ge=1)
    exception_type: str | None = None
    code: str | None = None
    severity: WarningSeverity = Field(
        default=WarningSeverity.WARNING,
        validate_default=True,
    )
    field_name: str | None = None


class SupplierRasterRegion(DrawingModel):
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox
    normalized_bounding_box: BoundingBox
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: ExtractionMethod = ExtractionMethod.IMAGE_REGION
    raw_text: str | None = None
    evidence_anchor: str | None = None


class Level1Summary(DrawingModel):
    source_filename: str
    drawing_number: str | None = None
    revision: str | None = None
    part_name: str | None = None
    document_type: str | None = None
    extracted_field_count: int = Field(ge=0)
    high_confidence_count: int = Field(ge=0)
    medium_confidence_count: int = Field(ge=0)
    low_confidence_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    supplier_raster_region_count: int = Field(ge=0)
    processing_state: ProcessingState


class DrawingPage(DrawingModel):
    """Page structure and any extraction records localized to that page."""

    page_number: int = Field(ge=1)
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    template: str | None = None
    native_text_available: bool | None = None
    word_count: int | None = Field(default=None, ge=0)
    text_block_count: int | None = Field(default=None, ge=0)
    title_block: TitleBlock | None = None
    revisions: list[RevisionRecord] | None = None
    notes: list[DrawingNote] | None = None
    bom: list[BOMItem] | None = None
    supplier: SupplierInfo | None = None
    standards: list[StandardReference] | None = None
    supplier_raster_regions: list[SupplierRasterRegion] | None = None


class PageTitleBlockData(DrawingModel):
    """Requested per-page title-block projection for multi-sheet extraction."""

    drawing_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_name: ExtractedField[str] = Field(default_factory=_unknown_field)
    weight: ExtractedField[str] = Field(default_factory=_unknown_field)
    sheet_number: ExtractedField[int] = Field(default_factory=_unknown_field)
    total_sheets: ExtractedField[int] = Field(default_factory=_unknown_field)
    units: ExtractedField[str] = Field(default_factory=_unknown_field)


class TitleBlockPage(DrawingModel):
    page: int = Field(ge=1)
    title_block: PageTitleBlockData


class MultiSheetTitleBlockExtraction(DrawingModel):
    pages: list[TitleBlockPage]
    document_metadata: PageTitleBlockData


class DrawingDocument(DrawingModel):
    """Canonical Level-1 structured result for one source PDF."""

    source_filename: ExtractedField[str] = Field(default_factory=_unknown_field)
    page_count: ExtractedField[int] = Field(default_factory=_unknown_field)
    document_type: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawing_number: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawing_size: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_name: ExtractedField[str] = Field(default_factory=_unknown_field)
    part_numbers: ExtractedField[list[str]] = Field(default_factory=_unknown_field)
    units: ExtractedField[str] = Field(default_factory=_unknown_field)
    scale: ExtractedField[str] = Field(default_factory=_unknown_field)
    weight: ExtractedField[str] = Field(default_factory=_unknown_field)
    sheet_number: ExtractedField[int] = Field(default_factory=_unknown_field)
    total_sheets: ExtractedField[int] = Field(
        default_factory=_unknown_field,
        validation_alias=AliasChoices("total_sheets", "sheet_count"),
    )
    critical_component: ExtractedField[bool] = Field(default_factory=_unknown_field)
    release_date: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawing_date: ExtractedField[str] = Field(default_factory=_unknown_field)
    drawn_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    modeled_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    approved_by: ExtractedField[str] = Field(default_factory=_unknown_field)
    revision_records: list[RevisionRecord] | None = Field(
        default=None,
        validation_alias=AliasChoices("revision_records", "revisions"),
    )
    notes: list[DrawingNote] | None = None
    bom_items: list[BOMItem] | None = Field(
        default=None,
        validation_alias=AliasChoices("bom_items", "bom"),
    )
    part_list_items: list[BOMItem] | None = None
    service_part_items: list[BOMItem] | None = None
    supplier_info: SupplierInfo | None = Field(
        default=None,
        validation_alias=AliasChoices("supplier_info", "supplier"),
    )
    standard_references: list[StandardReference] | None = Field(
        default=None,
        validation_alias=AliasChoices("standard_references", "standards"),
    )
    pages: list[DrawingPage] | None = None
    supplier_raster_regions: list[SupplierRasterRegion] = Field(default_factory=list)
    extraction_warnings: list[ExtractionWarning] = Field(
        default_factory=list,
        validation_alias=AliasChoices("extraction_warnings", "warnings"),
    )
    level1_summary: Level1Summary | None = None

    @property
    def sheet_count(self) -> ExtractedField[int]:
        return self.total_sheets

    @property
    def revisions(self) -> list[RevisionRecord] | None:
        return self.revision_records

    @property
    def bom(self) -> list[BOMItem] | None:
        combined = [
            *(self.bom_items or []),
            *(self.part_list_items or []),
            *(self.service_part_items or []),
        ]
        return combined or None

    @property
    def supplier(self) -> SupplierInfo | None:
        return self.supplier_info

    @property
    def standards(self) -> list[StandardReference] | None:
        return self.standard_references

    @property
    def warnings(self) -> list[ExtractionWarning]:
        return self.extraction_warnings
