from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.app.config import Settings, get_settings
from backend.app.extraction.document import DocumentContent, read_document
from backend.app.extraction.fields import (
    evidence_field,
    extract_compact_title_metrics,
    extract_native_bom,
    extract_notes,
    extract_revision_record,
    extract_standards,
    extract_title_identifiers,
    find_first,
    known,
    page_search_text,
    part_numbers_from_bom,
    unknown,
)
from backend.app.extraction.tables import extract_bom_tables
from backend.app.schemas import DrawingExtraction, ExtractedField, ExtractionMethod

logger = logging.getLogger(__name__)


class DrawingExtractionPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def extract(self, pdf_path: str | Path, *, filename: str | None = None) -> DrawingExtraction:
        path = Path(pdf_path)
        logger.info("Starting extraction for %s", path.name)
        document = read_document(
            path,
            ocr_enabled=self.settings.ocr_enabled,
            native_text_min_characters=self.settings.native_text_min_characters,
        )
        result = self._extract_fields(document, filename=filename or path.name)
        populated = sum(
            field.value is not None for _, field in result if isinstance(field, ExtractedField)
        )
        logger.info("Completed extraction for %s (%s fields populated)", path.name, populated)
        return result

    def _extract_fields(self, document: DocumentContent, *, filename: str) -> DrawingExtraction:
        ecn, revision_description, approved_by = extract_revision_record(document)
        drawing_number, revision, drawing_size = extract_title_identifiers(document)
        compact_weight, compact_scale, compact_units, compact_sheet, compact_total = (
            extract_compact_title_metrics(document)
        )

        table_candidates = [
            page.number
            for page in document.pages
            if re.search(
                r"\b(?:BOM|QTY\s+ITEM\s+PART\s+NO|SERVICE\s+PART\s+NO)\b",
                page_search_text(page),
                re.IGNORECASE,
            )
        ]
        bom_items, bom_page = extract_bom_tables(document.path, table_candidates)
        bom_method = ExtractionMethod.TABLE
        bom_confidence = 0.92
        if not bom_items:
            bom_items, bom_page = extract_native_bom(document)
            bom_method = ExtractionMethod.NATIVE_TEXT
            bom_confidence = 0.78
        bom = (
            known(bom_items, bom_page, bom_confidence, bom_method)
            if bom_items and bom_page is not None
            else unknown()
        )

        part_numbers = part_numbers_from_bom(bom_items)
        part_number_page = bom_page
        part_number_method = bom_method
        part_number_confidence = bom_confidence
        if not part_numbers:
            part_numbers, part_number_page, part_number_method = self._extract_labeled_part_numbers(
                document
            )
            part_number_confidence = 0.86

        if drawing_number.value is None:
            drawing_number = evidence_field(
                find_first(
                    document,
                    [r"\bDWG(?:\s+NO\.?)?\s*[:#]?\s*([A-Z0-9][A-Z0-9._/-]{4,})\b"],
                    confidence=0.96,
                )
            )
        if revision.value is None:
            revision = evidence_field(
                find_first(
                    document,
                    [
                        r"\bDWG(?:\s+NO\.?)?\s+[A-Z0-9][A-Z0-9._/-]{4,}"
                        r"\s+REV(?:ISION)?\s*[:#]?\s*([A-Z0-9]{1,4})\b"
                    ],
                    confidence=0.93,
                )
            )
        if drawing_size.value is None:
            drawing_size = evidence_field(
                find_first(
                    document,
                    [r"\bSIZE\s*[:#]?\s*([A-E](?:[0-4])?)\s+(?=DWG\b)"],
                    confidence=0.94,
                )
            )
        part_name = evidence_field(
            find_first(
                document,
                [
                    r"\bPART\s+NAME\s*[:#]?\s*(.{2,100}?)(?=\s+(?:SIZE|DWG\s+NO|REV|DRAWN|MODELED|DATE)\b|\n)",
                    r"\bNAME\s*[:#]?\s*(.{2,100}?)(?=\s+(?:SIZE|DWG\s+NO|REV)\b|\n)",
                ],
                confidence=0.89,
            )
        )
        release_date = evidence_field(
            find_first(
                document,
                [r"\bRELEASED\s+(\d{1,2}/[A-Z]{3}/\d{4})\b"],
                confidence=0.98,
            )
        )
        drawing_date = evidence_field(
            find_first(
                document,
                [
                    r"\bDATE\s*[:#]?\s*(?:[A-Z]\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
                ],
                confidence=0.88,
            )
        )
        drawn_by = evidence_field(
            find_first(
                document,
                [
                    r"\bDRAWN(?:\s+BY)?\s*[:#]?\s*([A-Z][A-Z0-9_.-]{1,30})(?=\s|$)",
                ],
                confidence=0.91,
            )
        )
        modeled_by = evidence_field(
            find_first(
                document,
                [
                    r"\bMODELL?ED(?:\s+BY)?\s*[:#]?\s*"
                    r"([A-Z][A-Z0-9_. -]{1,30}?)"
                    r"(?=\s+(?:DATE|DRAWN|CHECKED|CHKD|APPROVED|APPR|SIZE|DWG)\b|\n)",
                ],
                confidence=0.88,
            )
        )
        scale = evidence_field(
            find_first(
                document,
                [r"\bSCALE\s*[:#]?\s*([0-9.]+(?:\s*:\s*[0-9.]+)?)\s+(?=UNITS\b)"],
                confidence=0.96,
            )
        )
        if scale.value is None:
            scale = compact_scale
        units = evidence_field(
            find_first(
                document,
                [r"\bUNITS\s*[:#]?\s*([A-Zµ\"]{1,12})\s+(?=SHEET\b)"],
                confidence=0.96,
            )
        )
        if units.value is None:
            units = compact_units
        weight = evidence_field(
            find_first(
                document,
                [
                    r"\bWEIGHT\s*(?:\([^)]*\))?\s*(?:KILOGRAMS?|KG|GRAMS?|G)?\s*[:#]?\s*(\d+(?:\.\d+)?)\s+(?=SCALE\b)",
                    r"\bWEIGHT\s*[:#]?\s*(\d+(?:\.\d+)?)\s*(?:KILOGRAMS?|KG|GRAMS?|G)\b",
                    r"\bKILOGRAMS?\s+(\d+(?:\.\d+)?)\s+(?=SCALE\b)",
                ],
                confidence=0.9,
            )
        )
        if weight.value is None:
            weight = compact_weight
        sheet = find_first(
            document,
            [r"\bSHEET\s*[:#]?\s*(\d+)\s+OF\s+(\d+)\b"],
            confidence=0.98,
        )
        if sheet:
            full_match = re.search(
                r"\bSHEET\s*[:#]?\s*(\d+)\s+OF\s+(\d+)\b",
                page_search_text(document.pages[sheet.page - 1]),
                re.IGNORECASE,
            )
            sheet_number = known(int(sheet.value), sheet.page, sheet.confidence, sheet.method)
            total_sheets = (
                known(int(full_match.group(2)), sheet.page, sheet.confidence, sheet.method)
                if full_match
                else unknown()
            )
        else:
            sheet_number = compact_sheet
            total_sheets = compact_total

        supplier_name = evidence_field(
            find_first(
                document,
                [
                    r"\bSUPPLIER\s*:\s*([^\n]{2,80})",
                    r"\bMANUFACTURER\s*:\s*([^\n]{2,80})",
                ],
                confidence=0.93,
            )
        )
        supplier_part_number = evidence_field(
            find_first(
                document,
                [r"\bSUPPLIER\s+P\s*/?\s*N\s*[:#]?\s*([A-Z0-9._/-]{3,})\b"],
                confidence=0.95,
            )
        )

        return DrawingExtraction(
            filename=known(filename, None, 1.0, ExtractionMethod.FILE_METADATA),
            document_type=self._document_type(document),
            page_count=known(document.page_count, None, 1.0, ExtractionMethod.PDF_METADATA),
            drawing_number=drawing_number,
            revision=revision,
            drawing_size=drawing_size,
            part_name=part_name,
            part_numbers=(
                known(
                    part_numbers,
                    part_number_page,
                    part_number_confidence,
                    part_number_method,
                )
                if part_numbers and part_number_page and part_number_method
                else unknown()
            ),
            ecn=ecn,
            revision_description=revision_description,
            drawing_date=drawing_date,
            release_date=release_date,
            drawn_by=drawn_by,
            modeled_by=modeled_by,
            approved_by=approved_by,
            scale=scale,
            units=units,
            weight=weight,
            sheet_number=sheet_number,
            total_sheets=total_sheets,
            critical_component_indicator=self._indicator(
                document,
                true_patterns=[
                    r"\bIDENTIFIED AS (?:A )?CRITICAL (?:ITEM|COMPONENT)\b",
                    r"\bCRITICAL (?:ITEM|COMPONENT)\s*[:=]\s*(?:YES|TRUE)\b",
                ],
                false_patterns=[
                    r"\bNOT (?:A )?CRITICAL (?:ITEM|COMPONENT)\b",
                    r"\bCRITICAL (?:ITEM|COMPONENT)\s*[:=]\s*(?:NO|FALSE)\b",
                ],
            ),
            supplier_drawing_indicator=self._indicator(
                document,
                true_patterns=[r"\bSUPPLIER DRAWING\b"],
                false_patterns=[r"\bNOT (?:A )?SUPPLIER DRAWING\b"],
            ),
            supplier_name=supplier_name,
            supplier_part_number=supplier_part_number,
            notes=extract_notes(document, bom_items),
            bom=bom,
            referenced_engineering_standards=extract_standards(document),
        )

    @staticmethod
    def _document_type(document: DocumentContent) -> ExtractedField[str]:
        for page in document.pages:
            text = page_search_text(page)
            if re.search(r"\bSUPPLIER DRAWING\b", text, re.IGNORECASE):
                method = (
                    ExtractionMethod.OCR
                    if page.method == ExtractionMethod.OCR
                    else ExtractionMethod.NATIVE_TEXT
                )
                return known("supplier drawing", page.number, 0.97, method)
            if re.search(r"\bDWG(?:\s+NO\.?)?\b", text, re.IGNORECASE):
                method = (
                    ExtractionMethod.OCR
                    if page.method == ExtractionMethod.OCR
                    else ExtractionMethod.NATIVE_TEXT
                )
                return known("engineering drawing", page.number, 0.86, method)
        return unknown()

    @staticmethod
    def _indicator(
        document: DocumentContent,
        *,
        true_patterns: list[str],
        false_patterns: list[str],
    ) -> ExtractedField[bool]:
        for page in document.pages:
            text = page_search_text(page)
            for value, patterns in ((False, false_patterns), (True, true_patterns)):
                if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                    method = (
                        ExtractionMethod.OCR
                        if page.method == ExtractionMethod.OCR
                        else ExtractionMethod.NATIVE_TEXT
                    )
                    confidence = 0.68 if method == ExtractionMethod.OCR else 0.96
                    return known(value, page.number, confidence, method)
        return unknown()

    @staticmethod
    def _extract_labeled_part_numbers(
        document: DocumentContent,
    ) -> tuple[list[str], int | None, ExtractionMethod | None]:
        values: list[str] = []
        first_page: int | None = None
        first_method: ExtractionMethod | None = None
        pattern = re.compile(
            r"\bPART\s+(?:NUMBER|NO\.?)\s+(?:FOR\s+[^\n:]{2,50}\s+)?[:#]?\s*"
            r"([A-Z0-9][A-Z0-9._/-]{4,})\b",
            re.IGNORECASE,
        )
        for page in document.pages:
            for match in pattern.finditer(page_search_text(page)):
                value = match.group(1).strip()
                if not any(character.isdigit() for character in value):
                    continue
                if value not in values:
                    values.append(value)
                    first_page = first_page or page.number
                    first_method = first_method or (
                        ExtractionMethod.OCR
                        if page.method == ExtractionMethod.OCR
                        else ExtractionMethod.COORDINATE_TEXT
                    )
        return values, first_page, first_method
