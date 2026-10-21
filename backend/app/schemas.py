from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(StrEnum):
    FILE_METADATA = "file_metadata"
    PDF_METADATA = "pdf_metadata"
    NATIVE_TEXT = "native_text"
    COORDINATE_TEXT = "coordinate_text"
    TABLE = "pdfplumber_table"
    OCR = "ocr"


ValueT = TypeVar("ValueT")


class ExtractedField(BaseModel, Generic[ValueT]):
    value: ValueT | None = None
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: ExtractionMethod | None = None

    model_config = ConfigDict(use_enum_values=True)


class Note(BaseModel):
    number: str | None = None
    text: str


class BomItem(BaseModel):
    item: str | None = None
    quantity: str | None = None
    part_number: str | None = None
    description: str | None = None
    material: str | None = None
    remarks: str | None = None


class DrawingExtraction(BaseModel):
    filename: ExtractedField[str]
    document_type: ExtractedField[str]
    page_count: ExtractedField[int]
    drawing_number: ExtractedField[str]
    revision: ExtractedField[str]
    drawing_size: ExtractedField[str]
    part_name: ExtractedField[str]
    part_numbers: ExtractedField[list[str]]
    ecn: ExtractedField[str]
    revision_description: ExtractedField[str]
    drawing_date: ExtractedField[str]
    release_date: ExtractedField[str]
    drawn_by: ExtractedField[str]
    modeled_by: ExtractedField[str]
    approved_by: ExtractedField[str]
    scale: ExtractedField[str]
    units: ExtractedField[str]
    weight: ExtractedField[str]
    sheet_number: ExtractedField[int]
    total_sheets: ExtractedField[int]
    critical_component_indicator: ExtractedField[bool]
    supplier_drawing_indicator: ExtractedField[bool]
    supplier_name: ExtractedField[str]
    supplier_part_number: ExtractedField[str]
    notes: ExtractedField[list[Note]]
    bom: ExtractedField[list[BomItem]]
    referenced_engineering_standards: ExtractedField[list[str]]


class BatchExtractionResponse(BaseModel):
    drawings: list[DrawingExtraction]
