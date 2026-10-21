"""Coordinate extraction of native-text drawing revision tables."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pymupdf

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.models.drawing import ExtractedField, ExtractionMethod, RevisionRecord

logger = logging.getLogger(__name__)

ValueT = TypeVar("ValueT")
ECN_VALUE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{3,}$", re.IGNORECASE)
SUPPORTED_DESCRIPTIONS = re.compile(
    r"\b(?:INITIAL\s+RELEASE|PRODUCTION\s+RELEASE|NOT\s+RELEASED|"
    r"SEE\s+SHEET\s+1\s+FOR\s+REVISIONS)\b",
    re.IGNORECASE,
)


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
class RevisionHeader:
    line: TextLine
    column_bounds: dict[str, tuple[float, float]]
    table_left: float
    table_right: float


@dataclass(frozen=True)
class RowAnchor:
    center_y: float
    ecn_word: NativeWord | None = None


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
) -> ExtractedField[ValueT]:
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
        page_number=page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=_union_bbox(words),
        raw_text=value if isinstance(value, str) else " ".join(word.text for word in words),
        evidence_anchor="revision-table column heading and row alignment",
    )


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
    matched = [word for start, end, word in spans if start < match.end() and end > match.start()]
    return _union_bbox(matched) if matched else None


def _header_from_line(line: TextLine, page_width: float) -> RevisionHeader | None:
    compact, spans = _compact_with_spans(line.words)
    patterns = {
        "ecn": r"ECN",
        "revision_description": r"DESCRIPTIONOFCHANGE",
        "revision_date": r"DATE",
        "changed_by": r"CHANGEDBY",
        "approved_by": r"APPROVEDBY",
    }
    anchors = {
        name: bbox
        for name, pattern in patterns.items()
        if (bbox := _match_bbox(compact, spans, pattern)) is not None
    }
    if set(anchors) != set(patterns):
        return None

    ordered = sorted(
        ((name, bbox) for name, bbox in anchors.items()),
        key=lambda item: item[1][0],
    )
    table_left = max(0.0, anchors["ecn"][0] - 0.025 * page_width)
    table_right = min(page_width, anchors["approved_by"][2] + 0.025 * page_width)
    bounds: dict[str, tuple[float, float]] = {}
    for index, (name, bbox) in enumerate(ordered):
        left = table_left if index == 0 else (ordered[index - 1][1][2] + bbox[0]) / 2
        right = (
            table_right if index + 1 == len(ordered) else (bbox[2] + ordered[index + 1][1][0]) / 2
        )
        bounds[name] = (left, right)
    return RevisionHeader(line, bounds, table_left, table_right)


def _column_words(
    words: list[NativeWord],
    header: RevisionHeader,
    field_name: str,
    top: float,
    bottom: float,
) -> list[NativeWord]:
    left, right = header.column_bounds[field_name]
    return [
        word for word in words if left <= word.center_x < right and top <= word.center_y < bottom
    ]


def _raw_multiline(words: list[NativeWord]) -> str:
    if not words:
        return ""
    ordered = sorted(words, key=lambda word: (word.center_y, word.x0))
    tolerance = max(1.0, min(word.y1 - word.y0 for word in words) * 0.2)
    lines: list[list[NativeWord]] = []
    centers: list[float] = []
    for word in ordered:
        if lines and abs(word.center_y - centers[-1]) <= tolerance:
            lines[-1].append(word)
            centers[-1] = sum(item.center_y for item in lines[-1]) / len(lines[-1])
        else:
            lines.append([word])
            centers.append(word.center_y)
    return "\n".join(
        " ".join(word.text for word in sorted(line, key=lambda item: item.x0)) for line in lines
    )


def _single_line(words: list[NativeWord]) -> str:
    return re.sub(
        r"\s+", " ", " ".join(word.text for word in sorted(words, key=lambda item: item.x0))
    ).strip()


def _row_anchors(
    words: list[NativeWord],
    lines: list[TextLine],
    header: RevisionHeader,
    page_height: float,
) -> list[RowAnchor]:
    table_top = header.line.y0 - max(120.0, 0.20 * page_height)
    ecn_words = _column_words(
        words,
        header,
        "ecn",
        table_top,
        header.line.y0,
    )
    anchors = [
        RowAnchor(round(word.center_y, 3), word)
        for word in ecn_words
        if ECN_VALUE.fullmatch(word.text.strip()) and re.search(r"\d", word.text)
    ]
    anchors.sort(key=lambda anchor: anchor.center_y)
    if anchors:
        return anchors

    description_left, description_right = header.column_bounds["revision_description"]
    for line in lines:
        if line.center_y < table_top or line.center_y >= header.line.y0:
            continue
        description = " ".join(
            word.text
            for word in line.words
            if description_left <= word.center_x < description_right
        )
        if SUPPORTED_DESCRIPTIONS.search(description):
            anchors.append(RowAnchor(round(line.center_y, 3)))
    return sorted(
        {anchor.center_y: anchor for anchor in anchors}.values(),
        key=lambda anchor: anchor.center_y,
    )


def _field(
    value: str,
    words: list[NativeWord],
    page_number: int,
) -> ExtractedField[str]:
    return _known(value, words, page_number) if value and words else _unknown()


def _extract_rows(
    words: list[NativeWord],
    lines: list[TextLine],
    header: RevisionHeader,
    page_number: int,
    page_height: float,
) -> list[RevisionRecord]:
    anchors = _row_anchors(words, lines, header, page_height)
    if not anchors:
        return []
    radius = max(18.0, 0.018 * page_height)
    records: list[RevisionRecord] = []
    for index, anchor in enumerate(anchors):
        center_y = anchor.center_y
        top = (
            max(
                center_y - radius,
                (anchors[index - 1].center_y + center_y) / 2,
            )
            if index > 0
            else center_y - radius
        )
        bottom = (
            min(
                center_y + radius,
                (center_y + anchors[index + 1].center_y) / 2,
            )
            if index + 1 < len(anchors)
            else min(center_y + radius, header.line.y0)
        )
        fields = {
            name: _column_words(words, header, name, top, bottom) for name in header.column_bounds
        }
        if anchor.ecn_word is not None:
            fields["ecn"] = [anchor.ecn_word]
            _, description_right = header.column_bounds["revision_description"]
            fields["revision_description"] = [
                word
                for word in words
                if word.x0 >= anchor.ecn_word.x1
                and word.center_x < description_right
                and top <= word.center_y < bottom
            ]

        description = _raw_multiline(fields["revision_description"])
        values = {
            "ecn": _single_line(fields["ecn"]),
            "revision_date": _single_line(fields["revision_date"]),
            "changed_by": _single_line(fields["changed_by"]),
            "approved_by": _single_line(fields["approved_by"]),
        }
        all_words = [word for field_words in fields.values() for word in field_words]
        if not all_words or not any([description, *values.values()]):
            continue

        records.append(
            RevisionRecord(
                ecn=_field(values["ecn"], fields["ecn"], page_number),
                revision_description=_field(
                    description,
                    fields["revision_description"],
                    page_number,
                ),
                revision_date=_field(
                    values["revision_date"],
                    fields["revision_date"],
                    page_number,
                ),
                changed_by=_field(
                    values["changed_by"],
                    fields["changed_by"],
                    page_number,
                ),
                approved_by=_field(
                    values["approved_by"],
                    fields["approved_by"],
                    page_number,
                ),
                page_number=page_number,
                bounding_box=_union_bbox(all_words),
            )
        )
    return records


class RevisionTableExtractor:
    """Extract every native revision-table row without validating its meaning."""

    def extract(self, pdf_path: str | Path) -> list[RevisionRecord]:
        path = Path(pdf_path)
        records: list[RevisionRecord] = []
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                words = _native_words(page)
                lines = _spatial_lines(words, float(page.rect.height))
                for line in lines:
                    header = _header_from_line(line, float(page.rect.width))
                    if header is not None:
                        records.extend(
                            _extract_rows(
                                words,
                                lines,
                                header,
                                page_index + 1,
                                float(page.rect.height),
                            )
                        )
        logger.info("Extracted %s revision row(s) from %s", len(records), path.name)
        return records
