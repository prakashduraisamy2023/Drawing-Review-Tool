"""Evidence-only classification of standard and supplier drawings."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.extraction.notes import NotesExtractor
from backend.app.models.drawing import (
    DocumentClassification,
    DocumentType,
    ExtractedField,
    ExtractionMethod,
    ManufacturerPartMapping,
    SupplierInfo,
)

SUPPLIER_MARKERS = (
    "SUPPLIER DRAWING NOT TO SCALE",
    "SUPPLIER DRAWING",
)
STANDARD_MARKERS = (
    "STANDARD DRAWING",
    "STANDARD ENGINEERING DRAWING",
    "LIMITED DIMENSION DRAWING BASED ON CAD MODEL",
)
SUPPLIER_NAME = re.compile(
    r"(?:^|\n)\s*(?P<label>SUPPLIER|MANUFACTURER)\s*:\s*(?P<value>[^\n]+)",
    re.IGNORECASE,
)
SUPPLIER_PART_LABEL = re.compile(
    r"(?:^|\n)\s*(?:SUPPLIER|MANUFACTURER)\s*"
    r"(?:P\s*/\s*N|PART\s*(?:NO\.?|NUMBER))\s*:\s*([^\n]*)",
    re.IGNORECASE,
)
PART_MAPPING = re.compile(
    r"(?:^|\n)\s*FOR\s+(?P<source>[A-Z0-9][A-Z0-9._/-]*)\s*"
    r"-\s*(?P<manufacturer>[A-Z0-9][A-Z0-9._/-]*)",
    re.IGNORECASE,
)
IMPORTED_CAD_DATA = re.compile(r"\bIMPORTED\b[\s\S]{0,160}\bCAD\s+DATA\b", re.IGNORECASE)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    page_number: int
    order: int

    @property
    def normalized(self) -> str:
        return re.sub(r"[^A-Z0-9]+", "", self.text.upper())

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2


def _unknown() -> ExtractedField:
    return ExtractedField()


def _union_bbox(words: list[NativeWord]) -> tuple[float, float, float, float]:
    return (
        min(word.x0 for word in words),
        min(word.y0 for word in words),
        max(word.x1 for word in words),
        max(word.y1 for word in words),
    )


def _field(
    value,
    words: list[NativeWord],
) -> ExtractedField:
    confidence = calculate_confidence(
        ConfidenceEvidence(
            anchor_found=True,
            expected_region=True,
            format_match=True,
            relative_position=True,
        )
    ).score
    return ExtractedField(
        value=value,
        page_number=words[0].page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=_union_bbox(words),
        raw_text=" ".join(word.text for word in words),
        evidence_anchor="explicit supplier metadata",
    )


def _page_words(page: pymupdf.Page, page_number: int) -> list[NativeWord]:
    return [
        NativeWord(
            x0=float(row[0]),
            y0=float(row[1]),
            x1=float(row[2]),
            y1=float(row[3]),
            text=str(row[4]),
            page_number=page_number,
            order=order,
        )
        for order, row in enumerate(page.get_text("words", sort=False))
        if str(row[4]).strip()
    ]


def _normalized_tokens(value: str) -> list[str]:
    return [
        normalized
        for token in value.split()
        if (normalized := re.sub(r"[^A-Z0-9]+", "", token.upper()))
    ]


def _find_sequence(
    words: list[NativeWord],
    value: str,
    within: tuple[float, float, float, float] | None = None,
) -> list[NativeWord] | None:
    candidates = words
    if within is not None:
        x0, y0, x1, y1 = within
        candidates = [
            word for word in words if x0 <= word.center_x <= x1 and y0 <= word.center_y <= y1
        ]
    sequence = _normalized_tokens(value)
    normalized = [word.normalized for word in candidates]
    for start in range(len(candidates) - len(sequence) + 1):
        if normalized[start : start + len(sequence)] == sequence:
            return candidates[start : start + len(sequence)]
    return None


def _find_marker(pages: list[list[NativeWord]], markers: tuple[str, ...]) -> ExtractedField[str]:
    for marker in markers:
        for words in pages:
            matched = _find_sequence(words, marker)
            if matched:
                return _field(marker, matched)
    return _unknown()


def _clean_metadata_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(".;,: ")


def _copy_as_boolean(field: ExtractedField, value: bool) -> ExtractedField[bool]:
    return ExtractedField(
        value=value,
        page_number=field.page_number,
        confidence=field.confidence,
        extraction_method=field.extraction_method,
        bounding_box=field.bounding_box,
        raw_text=field.raw_text,
        evidence_anchor=field.evidence_anchor,
    )


class DocumentClassifier:
    """Classify a PDF only from explicit native-text drawing evidence."""

    def __init__(self, notes_extractor: NotesExtractor | None = None) -> None:
        self.notes_extractor = notes_extractor or NotesExtractor()

    def extract(self, pdf_path: str | Path) -> DocumentClassification:
        path = Path(pdf_path)
        page_words: list[list[NativeWord]] = []
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                page_words.append(_page_words(page, page_index + 1))

        marker = _find_marker(page_words, SUPPLIER_MARKERS)
        standard_marker = _find_marker(page_words, STANDARD_MARKERS)
        supplier = self._supplier_info(path, page_words, marker)

        supplier_evidence = self._supplier_evidence(supplier)
        if supplier_evidence.value is not None:
            result = DocumentClassification(
                document_type=DocumentType.SUPPLIER_DRAWING,
                evidence=supplier_evidence,
                supplier=supplier,
            )
        elif standard_marker.value is not None:
            result = DocumentClassification(
                document_type=DocumentType.STANDARD_DRAWING,
                evidence=standard_marker,
                supplier=supplier,
            )
        else:
            result = DocumentClassification(supplier=supplier)
        logger.info("Classified %s as %s", path.name, result.document_type)
        return result

    def _supplier_info(
        self,
        path: Path,
        page_words: list[list[NativeWord]],
        marker: ExtractedField[str],
    ) -> SupplierInfo:
        name: ExtractedField[str] = _unknown()
        manufacturer_name: ExtractedField[str] = _unknown()
        part_number: ExtractedField[str] = _unknown()
        part_numbers: ExtractedField[list[str]] = _unknown()
        imported_statement: ExtractedField[str] = _unknown()
        collected_part_numbers: list[tuple[str, list[NativeWord]]] = []
        mappings: list[ManufacturerPartMapping] = []

        for note in self.notes_extractor.extract(path):
            text = note.text.value or ""
            words = page_words[note.page_number - 1] if note.page_number else []
            if name.value is None and (match := SUPPLIER_NAME.search(text)):
                value = _clean_metadata_value(match.group("value"))
                matched_words = _find_sequence(words, value, note.bounding_box)
                if value and matched_words:
                    name = _field(value, matched_words)
                    if match.group("label").upper() == "MANUFACTURER":
                        manufacturer_name = name.model_copy(deep=True)

            label_match = SUPPLIER_PART_LABEL.search(text)
            mapping_matches = list(PART_MAPPING.finditer(text))
            if mapping_matches:
                for mapping_match in mapping_matches:
                    source_value = _clean_metadata_value(mapping_match.group("source"))
                    manufacturer_value = _clean_metadata_value(mapping_match.group("manufacturer"))
                    source_words = _find_sequence(words, source_value, note.bounding_box)
                    manufacturer_words = _find_sequence(
                        words, manufacturer_value, note.bounding_box
                    )
                    if manufacturer_value and manufacturer_words:
                        collected_part_numbers.append((manufacturer_value, manufacturer_words))
                    if source_words and manufacturer_words:
                        mappings.append(
                            ManufacturerPartMapping(
                                source_part_number=_field(source_value, source_words),
                                manufacturer_part_number=_field(
                                    manufacturer_value,
                                    manufacturer_words,
                                ),
                            )
                        )
            elif label_match and (value := _clean_metadata_value(label_match.group(1))):
                matched_words = _find_sequence(words, value, note.bounding_box)
                if matched_words:
                    collected_part_numbers.append((value, matched_words))

            if imported_statement.value is None and IMPORTED_CAD_DATA.search(text):
                imported_statement = note.text.model_copy(deep=True)

        deduplicated: list[tuple[str, list[NativeWord]]] = []
        seen: set[str] = set()
        for value, words in collected_part_numbers:
            if value.upper() not in seen:
                seen.add(value.upper())
                deduplicated.append((value, words))
        if deduplicated:
            evidence_words = [word for _, words in deduplicated for word in words]
            values = [value for value, _ in deduplicated]
            part_numbers = _field(values, evidence_words)
            if len(deduplicated) == 1:
                part_number = _field(values[0], deduplicated[0][1])

        evidence = marker
        if evidence.value is None:
            evidence = name if name.value is not None else part_numbers
        supplier_drawing = (
            _copy_as_boolean(evidence, True) if evidence.value is not None else _unknown()
        )
        return SupplierInfo(
            supplier_drawing=supplier_drawing,
            supplier_name=name,
            supplier_part_number=part_number,
            supplier_part_numbers=part_numbers,
            supplier_drawing_marker=marker,
            imported_cad_data_statement=imported_statement,
            manufacturer_name=manufacturer_name,
            manufacturer_part_number_mappings=mappings or None,
        )

    @staticmethod
    def _supplier_evidence(supplier: SupplierInfo) -> ExtractedField[str]:
        for field in (
            supplier.supplier_drawing_marker,
            supplier.supplier_name,
            supplier.supplier_part_numbers,
        ):
            if field.value is None:
                continue
            return ExtractedField(
                value=(field.value if isinstance(field.value, str) else ", ".join(field.value)),
                page_number=field.page_number,
                confidence=field.confidence,
                extraction_method=field.extraction_method,
                bounding_box=field.bounding_box,
                raw_text=field.raw_text,
                evidence_anchor=field.evidence_anchor,
            )
        statement = supplier.imported_cad_data_statement
        if statement.value and re.search(r"\bSUPPLIER\b", statement.value, re.IGNORECASE):
            return statement.model_copy(deep=True)
        return _unknown()
