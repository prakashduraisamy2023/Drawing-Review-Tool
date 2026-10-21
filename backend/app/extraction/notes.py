"""Native-text extraction of numbered drawing-note sections."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pymupdf

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.models.drawing import (
    DrawingNote,
    ExtractedField,
    ExtractionMethod,
    StandardReference,
)

logger = logging.getLogger(__name__)

ValueT = TypeVar("ValueT")
NOTE_NUMBER = re.compile(r"^(\d{1,3})(?:[.)])?$")
ATTACHED_NOTE_NUMBER = re.compile(r"^(\d{1,3})[.)](\S.+)$")
STANDARD_PATTERNS = (
    re.compile(r"\bPES\s*\d{3,}\b", re.IGNORECASE),
    re.compile(
        r"\bASME\s+Y\s*\d+(?:\.\d+)+(?:\s*-\s*\d{2,4})?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bFMVSS(?:\s*-\s*\d+(?:\.\d+)*)?\b", re.IGNORECASE),
    re.compile(r"\bSAE(?:\s+[A-Z]?\d+(?:\.\d+)*)?\b", re.IGNORECASE),
    re.compile(r"\bASTM(?:\s+[A-Z]?\d+(?:\.\d+)*)?\b", re.IGNORECASE),
    re.compile(r"\bCAL\s+\d+(?:\.\d+)*\b", re.IGNORECASE),
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
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def normalized(self) -> str:
        return re.sub(r"[^A-Z0-9]+", "", self.text.upper())

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


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


def _block_rectangles(page: pymupdf.Page) -> dict[int, pymupdf.Rect]:
    return {
        int(row[5]): pymupdf.Rect(float(row[0]), float(row[1]), float(row[2]), float(row[3]))
        for row in page.get_text("blocks", sort=True)
        if len(row) >= 7 and int(row[6]) == 0
    }


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
    reconstructed: bool = False,
) -> ExtractedField[ValueT]:
    confidence = calculate_confidence(
        ConfidenceEvidence(
            anchor_found=True,
            expected_region=True,
            format_match=True,
            relative_position=True,
            reconstructed_across_blocks=reconstructed,
        )
    ).score
    return ExtractedField(
        value=value,
        page_number=page_number,
        confidence=confidence,
        extraction_method=ExtractionMethod.COORDINATE_TEXT,
        bounding_box=_union_bbox(words),
        raw_text=value if isinstance(value, str) else " ".join(word.text for word in words),
        evidence_anchor="NOTE/NOTES heading and numbered marker",
    )


def _heading_words(words: list[NativeWord]) -> list[NativeWord]:
    by_line: dict[tuple[int, int], list[NativeWord]] = defaultdict(list)
    for word in words:
        by_line[(word.block_number, word.line_number)].append(word)
    return [
        line[0]
        for line in by_line.values()
        if len(line) == 1 and line[0].normalized in {"NOTE", "NOTES"}
    ]


def _number(word: NativeWord) -> int | None:
    match = NOTE_NUMBER.fullmatch(word.text.strip())
    if match is None:
        match = ATTACHED_NOTE_NUMBER.fullmatch(word.text.strip())
    return int(match.group(1)) if match else None


def _split_marker(word: NativeWord) -> tuple[NativeWord, NativeWord | None]:
    match = ATTACHED_NOTE_NUMBER.fullmatch(word.text.strip())
    if match is None:
        return word, None
    prefix_length = match.start(2)
    split_x = word.x0 + (word.x1 - word.x0) * prefix_length / len(word.text)
    number_word = NativeWord(
        x0=word.x0,
        y0=word.y0,
        x1=split_x,
        y1=word.y1,
        text=match.group(1),
        block_number=word.block_number,
        line_number=word.line_number,
        word_number=word.word_number,
        order=word.order,
    )
    suffix_word = NativeWord(
        x0=split_x,
        y0=word.y0,
        x1=word.x1,
        y1=word.y1,
        text=match.group(2),
        block_number=word.block_number,
        line_number=word.line_number,
        word_number=word.word_number,
        order=word.order,
    )
    return number_word, suffix_word


def _sequential_markers(
    words: list[NativeWord], heading: NativeWord, page: pymupdf.Page
) -> list[NativeWord]:
    x_tolerance = max(8.0, 0.012 * float(page.rect.width))
    candidates = [
        word
        for word in words
        if _number(word) is not None
        and word.center_y > heading.center_y
        and word.y0 < 0.84 * float(page.rect.height)
        and abs(word.x0 - heading.x0) <= x_tolerance
    ]
    candidates.sort(key=lambda word: (word.y0, word.x0))
    first = next((word for word in candidates if _number(word) == 1), None)
    if first is None:
        return []

    markers = [first]
    expected = 2
    for candidate in candidates:
        if candidate.order == first.order or candidate.y0 <= markers[-1].y0:
            continue
        if abs(candidate.x0 - first.x0) > x_tolerance:
            continue
        if _number(candidate) == expected:
            markers.append(candidate)
            expected += 1
    return markers


def _note_text(words: list[NativeWord]) -> str:
    lines: list[str] = []
    current_key: tuple[int, int] | None = None
    current_words: list[str] = []
    for word in sorted(words, key=lambda item: item.order):
        key = (word.block_number, word.line_number)
        if current_key is not None and key != current_key:
            lines.append(" ".join(current_words))
            current_words = []
        current_key = key
        current_words.append(word.text)
    if current_words:
        lines.append(" ".join(current_words))
    return "\n".join(line.rstrip() for line in lines).strip()


def _flat_text_with_spans(
    words: list[NativeWord],
) -> tuple[str, list[tuple[int, int, NativeWord]]]:
    parts: list[str] = []
    spans: list[tuple[int, int, NativeWord]] = []
    cursor = 0
    for word in sorted(words, key=lambda item: item.order):
        if parts:
            parts.append(" ")
            cursor += 1
        start = cursor
        parts.append(word.text)
        cursor += len(word.text)
        spans.append((start, cursor, word))
    return "".join(parts), spans


def _standard_references(
    words: list[NativeWord], page_number: int
) -> list[StandardReference] | None:
    text, spans = _flat_text_with_spans(words)
    references: list[tuple[int, StandardReference]] = []
    seen: set[str] = set()
    for pattern in STANDARD_PATTERNS:
        for match in pattern.finditer(text):
            matched_words = [
                word for start, end, word in spans if start < match.end() and end > match.start()
            ]
            value = re.sub(r"\s+", " ", match.group(0)).strip()
            deduplication_key = value.upper()
            if not matched_words or deduplication_key in seen:
                continue
            seen.add(deduplication_key)
            references.append(
                (
                    match.start(),
                    StandardReference(designation=_known(value, matched_words, page_number)),
                )
            )
    if not references:
        return None
    return [reference for _, reference in sorted(references, key=lambda item: item[0])]


class NotesExtractor:
    """Extract numbered NOTE/NOTES sections from every PDF page."""

    def extract(self, pdf_path: str | Path) -> list[DrawingNote]:
        path = Path(pdf_path)
        notes: list[DrawingNote] = []
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                notes.extend(self.extract_page(page, page_index + 1))
        logger.info("Extracted %s numbered note(s) from %s", len(notes), path.name)
        return notes

    def extract_page(self, page: pymupdf.Page, page_number: int) -> list[DrawingNote]:
        words = _native_words(page)
        blocks = _block_rectangles(page)
        notes: list[DrawingNote] = []
        used_markers: set[int] = set()
        for heading in _heading_words(words):
            markers = [
                marker
                for marker in _sequential_markers(words, heading, page)
                if marker.order not in used_markers
            ]
            if not markers:
                continue
            used_markers.update(marker.order for marker in markers)
            notes.extend(self._notes_from_section(words, blocks, markers, page_number, page))
        return notes

    def _notes_from_section(
        self,
        words: list[NativeWord],
        blocks: dict[int, pymupdf.Rect],
        markers: list[NativeWord],
        page_number: int,
        page: pymupdf.Page,
    ) -> list[DrawingNote]:
        section_block_numbers = {marker.block_number for marker in markers}
        section_left = min(marker.x0 for marker in markers)
        block_x_tolerance = 0.08 * float(page.rect.width)
        block_gap_tolerance = 0.025 * float(page.rect.height)
        section_bottom = max(blocks[number].y1 for number in section_block_numbers)
        aligned_blocks = sorted(
            (
                (number, rectangle)
                for number, rectangle in blocks.items()
                if number not in section_block_numbers
                and rectangle.y1 >= markers[0].y0
                and rectangle.y0 < 0.84 * float(page.rect.height)
                and section_left - block_x_tolerance
                <= rectangle.x0
                <= section_left + block_x_tolerance
            ),
            key=lambda item: item[1].y0,
        )
        for number, rectangle in aligned_blocks:
            if rectangle.y0 <= section_bottom + block_gap_tolerance:
                section_block_numbers.add(number)
                section_bottom = max(section_bottom, rectangle.y1)

        section_right = max(blocks[number].x1 for number in section_block_numbers)
        line_tolerance = max(1.0, min(marker.y1 - marker.y0 for marker in markers) * 0.15)
        extracted: list[DrawingNote] = []

        for index, marker in enumerate(markers):
            if index + 1 < len(markers):
                bottom = markers[index + 1].y0 - line_tolerance
            else:
                bottom = section_bottom + line_tolerance
            note_words = [
                word
                for word in words
                if word.block_number in section_block_numbers
                and word.order != marker.order
                and word.x1 >= section_left
                and word.x0 <= section_right
                and word.y0 >= marker.y0 - line_tolerance
                and word.y0 < bottom
            ]
            number_word, attached_text = _split_marker(marker)
            if attached_text is not None:
                note_words.insert(0, attached_text)
            text = _note_text(note_words)
            if not note_words or not text:
                continue
            combined_words = [number_word, *note_words]
            extracted.append(
                DrawingNote(
                    number=_known(str(_number(marker)), [number_word], page_number),
                    text=_known(
                        text,
                        note_words,
                        page_number,
                        reconstructed="\n" in text,
                    ),
                    page_number=page_number,
                    bounding_box=_union_bbox(combined_words),
                    standards=_standard_references(note_words, page_number),
                )
            )
        return extracted
