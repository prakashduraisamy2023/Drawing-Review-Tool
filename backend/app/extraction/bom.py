"""Coordinate-first extraction of native engineering-drawing BOM tables."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pdfplumber
import pymupdf

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.models.drawing import (
    BOMItem,
    ExtractedField,
    ExtractionMethod,
    TableType,
)

logger = logging.getLogger(__name__)

ValueT = TypeVar("ValueT")
PART_NUMBER = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]{2,}$", re.IGNORECASE)


@dataclass(frozen=True)
class NativeWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block_number: int
    line_number: int
    word_number: int
    order: int

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def normalized(self) -> str:
        return re.sub(r"[^A-Z0-9]+", "", self.text.upper())


@dataclass(frozen=True)
class TextLine:
    words: tuple[NativeWord, ...]

    @property
    def y0(self) -> float:
        return min(word.y0 for word in self.words)

    @property
    def y1(self) -> float:
        return max(word.y1 for word in self.words)

    @property
    def center_y(self) -> float:
        return sum(word.center_y for word in self.words) / len(self.words)


@dataclass(frozen=True)
class Header:
    line: TextLine
    anchors: dict[str, tuple[float, float, float, float]]
    column_bounds: dict[str, tuple[float, float]]
    table_left: float
    table_right: float
    table_type: TableType


def _unknown() -> ExtractedField:
    return ExtractedField()


def _union_bbox(words: list[NativeWord]) -> tuple[float, float, float, float]:
    return (
        min(word.x0 for word in words),
        min(word.y0 for word in words),
        max(word.x1 for word in words),
        max(word.y1 for word in words),
    )


def _known(
    value: ValueT,
    words: list[NativeWord],
    page_number: int,
    confidence: float | None = None,
) -> ExtractedField[ValueT]:
    confidence = (
        confidence
        or calculate_confidence(
            ConfidenceEvidence(
                anchor_found=True,
                expected_region=True,
                format_match=True,
                relative_position=True,
            )
        ).score
    )
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=_union_bbox(words),
        raw_text=_joined(words),
        evidence_anchor="detected table heading",
    )


def _known_table(
    value: ValueT,
    bbox: tuple[float, float, float, float],
    page_number: int,
) -> ExtractedField[ValueT]:
    confidence = calculate_confidence(
        ConfidenceEvidence(
            anchor_found=True,
            expected_region=True,
            relative_position=True,
            reconstructed_across_blocks=True,
        )
    ).score
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.TABLE,
        bounding_box=bbox,
        raw_text=str(value),
        evidence_anchor="pdfplumber table heading",
    )


def _table_field(
    values: dict[str, str],
    name: str,
    bbox: tuple[float, float, float, float],
    page_number: int,
) -> ExtractedField:
    if values.get(name):
        return _known_table(values[name], bbox, page_number)
    return _unknown()


def _native_words(page: pymupdf.Page) -> list[NativeWord]:
    return [
        NativeWord(
            x0=float(row[0]),
            y0=float(row[1]),
            x1=float(row[2]),
            y1=float(row[3]),
            text=str(row[4]),
            block_number=int(row[5]),
            line_number=int(row[6]),
            word_number=int(row[7]),
            order=order,
        )
        for order, row in enumerate(page.get_text("words", sort=False))
        if str(row[4]).strip()
    ]


def _spatial_lines(words: list[NativeWord], page_height: float) -> list[TextLine]:
    tolerance = max(2.0, 0.0025 * page_height)
    groups: list[list[NativeWord]] = []
    centers: list[float] = []
    for word in sorted(words, key=lambda item: (item.center_y, item.x0)):
        for index in range(len(groups) - 1, max(-1, len(groups) - 6), -1):
            if abs(word.center_y - centers[index]) <= tolerance:
                groups[index].append(word)
                centers[index] = sum(item.center_y for item in groups[index]) / len(groups[index])
                break
        else:
            groups.append([word])
            centers.append(word.center_y)
    return [
        TextLine(tuple(sorted(group, key=lambda item: item.x0)))
        for group in sorted(groups, key=lambda group: min(word.y0 for word in group))
    ]


def _compact_with_spans(
    words: tuple[NativeWord, ...],
) -> tuple[str, list[tuple[int, int, NativeWord]]]:
    compact = ""
    spans: list[tuple[int, int, NativeWord]] = []
    for word in words:
        normalized = word.normalized
        if not normalized:
            continue
        start = len(compact)
        compact += normalized
        spans.append((start, len(compact), word))
    return compact, spans


def _match_bbox(
    compact: str,
    spans: list[tuple[int, int, NativeWord]],
    pattern: str,
) -> tuple[float, float, float, float] | None:
    match = re.search(pattern, compact)
    if match is None:
        return None
    words = [word for start, end, word in spans if start < match.end() and end > match.start()]
    return _union_bbox(words) if words else None


def _header_from_line(line: TextLine, page_width: float) -> Header | None:
    compact, spans = _compact_with_spans(line.words)
    description = _match_bbox(compact, spans, r"DESCRIPTION")
    if description is None:
        return None

    service_part = _match_bbox(compact, spans, r"SERVICEPART(?:NO|NUMBER)")
    part_number = service_part or _match_bbox(compact, spans, r"PART(?:NO|NUMBER)")
    quantity = _match_bbox(compact, spans, r"(?:QTY|QUANTITY)")
    item = _match_bbox(compact, spans, r"ITEM(?:NO|NUMBER)?")
    if part_number is None and not (quantity is not None and item is not None):
        return None

    anchors = {"description": description}
    if part_number is not None:
        anchors["part_number"] = part_number
    if quantity is not None:
        anchors["quantity"] = quantity
    if item is not None:
        anchors["item_no"] = item

    centers = sorted(
        ((name, (bbox[0] + bbox[2]) / 2) for name, bbox in anchors.items()),
        key=lambda item: item[1],
    )
    table_left = max(0.0, min(bbox[0] for bbox in anchors.values()) - 0.02 * page_width)
    table_right = min(
        0.995 * page_width,
        max(description[2] + 0.1 * page_width, max(bbox[2] for bbox in anchors.values())),
    )
    column_bounds: dict[str, tuple[float, float]] = {}
    for index, (name, center) in enumerate(centers):
        left = table_left if index == 0 else (centers[index - 1][1] + center) / 2
        right = table_right if index + 1 == len(centers) else (center + centers[index + 1][1]) / 2
        column_bounds[name] = (left, right)
    if service_part is None and part_number is not None:
        part_description_boundary = min(
            column_bounds["part_number"][1],
            part_number[2] + 0.005 * page_width,
        )
        column_bounds["part_number"] = (
            column_bounds["part_number"][0],
            part_description_boundary,
        )
        column_bounds["description"] = (
            part_description_boundary,
            column_bounds["description"][1],
        )
    table_type = (
        TableType.SERVICE_PARTS
        if service_part is not None
        else TableType.BOM
        if quantity is not None or item is not None
        else TableType.PART_LIST
    )
    return Header(
        line,
        anchors,
        column_bounds,
        table_left,
        table_right,
        table_type,
    )


def _joined(words: list[NativeWord]) -> str:
    return re.sub(r"\s+", " ", " ".join(word.text for word in words)).strip()


def _line_columns(line: TextLine, header: Header) -> dict[str, list[NativeWord]]:
    return {
        name: [word for word in line.words if left <= word.center_x < right]
        for name, (left, right) in header.column_bounds.items()
    }


def _valid_part_number(value: str) -> bool:
    return (
        bool(value)
        and bool(PART_NUMBER.fullmatch(value))
        and bool(re.search(r"\d", value))
        and value.upper() not in {"PART NO", "PART NUMBER", "SERVICE PART NO"}
    )


def _is_row(columns: dict[str, list[NativeWord]], header: Header) -> bool:
    description = _joined(columns.get("description", []))
    if "part_number" in header.column_bounds:
        return _valid_part_number(_joined(columns.get("part_number", [])))
    item = _joined(columns.get("item_no", []))
    quantity = _joined(columns.get("quantity", []))
    return bool(description and (item or quantity))


def _row_item(
    columns: dict[str, list[NativeWord]],
    page_number: int,
    table_type: TableType,
    continuation_description: list[NativeWord] | None = None,
) -> BOMItem:
    continuation_description = continuation_description or []
    description_words = [*columns.get("description", []), *continuation_description]
    item_words = columns.get("item_no", [])
    quantity_words = columns.get("quantity", [])
    part_words = columns.get("part_number", [])
    all_words = [*item_words, *quantity_words, *part_words, *description_words]
    return BOMItem(
        table_type=table_type,
        item_no=(
            _known(_joined(item_words), item_words, page_number) if item_words else _unknown()
        ),
        quantity=(
            _known(_joined(quantity_words), quantity_words, page_number)
            if quantity_words
            else _unknown()
        ),
        part_number=(
            _known(_joined(part_words), part_words, page_number) if part_words else _unknown()
        ),
        description=(
            _known(_joined(description_words), description_words, page_number)
            if description_words
            else _unknown()
        ),
        page_number=page_number,
        bounding_box=_union_bbox(all_words),
    )


def _coordinate_rows(
    lines: list[TextLine],
    header: Header,
    next_header_y: float,
    page_number: int,
    page_height: float,
) -> list[BOMItem]:
    candidates: list[tuple[TextLine, dict[str, list[NativeWord]]]] = []
    for line in lines:
        if line.center_y <= header.line.center_y or line.y0 >= next_header_y:
            continue
        columns = _line_columns(line, header)
        if _is_row(columns, header):
            candidates.append((line, columns))
    if not candidates:
        return []

    first_gap_limit = max(60.0, 0.08 * page_height)
    first = next(
        (
            index
            for index, (line, _) in enumerate(candidates)
            if line.y0 - header.line.y1 <= first_gap_limit
        ),
        None,
    )
    if first is None:
        return []

    row_gap_limit = max(48.0, 0.04 * page_height)
    clustered = [candidates[first]]
    for candidate in candidates[first + 1 :]:
        if candidate[0].center_y - clustered[-1][0].center_y > row_gap_limit:
            break
        clustered.append(candidate)

    items: list[BOMItem] = []
    for index, (line, columns) in enumerate(clustered):
        next_y = (
            clustered[index + 1][0].y0
            if index + 1 < len(clustered)
            else min(next_header_y, line.y1 + row_gap_limit)
        )
        continuation: list[NativeWord] = []
        for possible in lines:
            if possible.y0 <= line.y0 or possible.y0 >= next_y:
                continue
            possible_columns = _line_columns(possible, header)
            if _is_row(possible_columns, header):
                continue
            earlier_column_has_text = any(
                possible_columns.get(name) for name in header.column_bounds if name != "description"
            )
            if earlier_column_has_text:
                continue
            continuation.extend(possible_columns.get("description", []))
        items.append(_row_item(columns, page_number, header.table_type, continuation))
    return items


def _canonical_cell(value: object) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()
    if "SERVICE PART NO" in normalized or "PART NO" in normalized:
        return "part_number"
    if normalized in {"QTY", "QUANTITY"}:
        return "quantity"
    if normalized in {"ITEM", "ITEM NO", "ITEM NUMBER"}:
        return "item_no"
    if "DESCRIPTION" in normalized:
        return "description"
    return None


def _plumber_fallback(
    path: Path,
    fallbacks: list[tuple[int, Header, float, float]],
) -> list[BOMItem]:
    items: list[BOMItem] = []
    if not fallbacks:
        return items
    try:
        with pdfplumber.open(path) as document:
            for page_number, header, next_header_y, page_height in fallbacks:
                page = document.pages[page_number - 1]
                crop_bbox = (
                    header.table_left,
                    max(0.0, header.line.y0 - 2.0),
                    header.table_right,
                    min(next_header_y, header.line.y1 + 0.3 * page_height),
                )
                crop = page.crop(crop_bbox)
                for table in crop.find_tables() or []:
                    matrix = table.extract()
                    for header_index, raw_header in enumerate(matrix[:4]):
                        mapped = [_canonical_cell(cell) for cell in raw_header]
                        recognized = {value for value in mapped if value}
                        if "description" not in recognized or not (
                            {"part_number", "quantity", "item_no"} & recognized
                        ):
                            continue
                        columns = {
                            name: index for index, name in enumerate(mapped) if name is not None
                        }
                        for row_index, raw_row in enumerate(
                            matrix[header_index + 1 :], start=header_index + 1
                        ):
                            values = {
                                name: re.sub(r"\s+", " ", str(raw_row[index] or "")).strip()
                                for name, index in columns.items()
                                if index < len(raw_row)
                            }
                            if not values.get("part_number") and not values.get("description"):
                                continue
                            cells = [
                                cell for cell in table.rows[row_index].cells if cell is not None
                            ]
                            if not cells:
                                continue
                            bbox = (
                                min(cell[0] for cell in cells),
                                min(cell[1] for cell in cells),
                                max(cell[2] for cell in cells),
                                max(cell[3] for cell in cells),
                            )
                            items.append(
                                BOMItem(
                                    table_type=header.table_type,
                                    item_no=_table_field(values, "item_no", bbox, page_number),
                                    quantity=_table_field(values, "quantity", bbox, page_number),
                                    part_number=_table_field(
                                        values, "part_number", bbox, page_number
                                    ),
                                    description=_table_field(
                                        values, "description", bbox, page_number
                                    ),
                                    page_number=page_number,
                                    bounding_box=bbox,
                                )
                            )
                        break
    except Exception:
        logger.exception("pdfplumber BOM fallback failed for %s", path.name)
    return items


class BOMExtractor:
    """Extract and label every native-text parts table in a PDF."""

    def extract(self, pdf_path: str | Path) -> list[BOMItem]:
        path = Path(pdf_path)
        items: list[BOMItem] = []
        fallbacks: list[tuple[int, Header, float, float]] = []
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                page_height = float(page.rect.height)
                lines = _spatial_lines(_native_words(page), page_height)
                headers = [
                    header
                    for line in lines
                    if (header := _header_from_line(line, float(page.rect.width))) is not None
                ]
                for header_index, header in enumerate(headers):
                    next_header_y = (
                        headers[header_index + 1].line.y0
                        if header_index + 1 < len(headers)
                        else 0.98 * page_height
                    )
                    extracted = _coordinate_rows(
                        lines,
                        header,
                        next_header_y,
                        page_number,
                        page_height,
                    )
                    if extracted:
                        items.extend(extracted)
                    else:
                        fallbacks.append((page_number, header, next_header_y, page_height))
        items.extend(_plumber_fallback(path, fallbacks))
        logger.info("Extracted %s parts-table row(s) from %s", len(items), path.name)
        return items
