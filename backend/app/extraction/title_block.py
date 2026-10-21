"""Spatial extraction of native-text Club Car title blocks."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pymupdf

from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence
from backend.app.models.drawing import ExtractedField, ExtractionMethod, TitleBlock

logger = logging.getLogger(__name__)

ValueT = TypeVar("ValueT")

# Club Car B- and D-size sheets place the title block in the lower-right corner.
# This intentionally broad normalized window only selects candidates; labels
# inside the window establish the actual field boundaries.
TITLE_REGION = (0.65, 0.82, 0.995, 0.995)


@dataclass(frozen=True)
class NativeWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def normalized(self) -> str:
        return re.sub(r"[^A-Z0-9]+", "", self.text.upper())

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


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
        raw_text=" ".join(word.text for word in words),
        evidence_anchor="title-block label and relative position",
    )


def _native_words(page: pymupdf.Page, clip: pymupdf.Rect | None = None) -> list[NativeWord]:
    return [
        NativeWord(
            x0=float(row[0]),
            y0=float(row[1]),
            x1=float(row[2]),
            y1=float(row[3]),
            text=str(row[4]).strip(),
        )
        for row in page.get_text("words", clip=clip, sort=True)
        if str(row[4]).strip()
    ]


def _bottom_anchor(words: list[NativeWord], label: str) -> NativeWord | None:
    matches = [word for word in words if word.normalized == label]
    return max(matches, key=lambda word: word.y0, default=None)


def _words_in_rect(
    words: list[NativeWord],
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    excluded: set[str] | None = None,
) -> list[NativeWord]:
    excluded = excluded or set()
    selected = [
        word
        for word in words
        if x0 <= word.center_x < x1 and y0 <= word.center_y < y1 and word.normalized not in excluded
    ]
    return sorted(selected, key=lambda word: (word.center_y, word.x0))


def _joined(words: list[NativeWord]) -> str:
    return re.sub(r"\s+", " ", " ".join(word.text for word in words)).strip()


def _text_field(
    words: list[NativeWord],
    page_number: int,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    excluded: set[str],
    accept: Callable[[str], bool] | None = None,
) -> ExtractedField[str]:
    candidates = _words_in_rect(
        words,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        excluded=excluded,
    )
    value = _joined(candidates)
    if not candidates or not value or (accept is not None and not accept(value)):
        return _unknown()
    return _known(value, candidates, page_number)


def _sequence_bbox(words: list[NativeWord], sequence: tuple[str, ...]) -> list[NativeWord] | None:
    normalized = [word.normalized for word in words]
    for start in range(len(words) - len(sequence) + 1):
        if tuple(normalized[start : start + len(sequence)]) == sequence:
            return words[start : start + len(sequence)]
    return None


class TitleBlockExtractor:
    """Extract one native-text Club Car title block record per PDF page."""

    def extract(self, pdf_path: str | Path) -> list[TitleBlock]:
        path = Path(pdf_path)
        title_blocks: list[TitleBlock] = []
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                title_blocks.append(self.extract_page(page, page_index + 1))
        logger.info("Extracted %s title block page(s) from %s", len(title_blocks), path.name)
        return title_blocks

    def extract_page(self, page: pymupdf.Page, page_number: int) -> TitleBlock:
        width = float(page.rect.width)
        height = float(page.rect.height)
        region = pymupdf.Rect(
            TITLE_REGION[0] * width,
            TITLE_REGION[1] * height,
            TITLE_REGION[2] * width,
            TITLE_REGION[3] * height,
        )
        words = _native_words(page, region)
        anchors = {
            label: _bottom_anchor(words, label)
            for label in (
                "DRAWN",
                "MODELED",
                "DATE",
                "PART",
                "SIZE",
                "DWG",
                "REV",
                "WEIGHT",
                "SCALE",
                "UNITS",
                "SHEET",
                "OF",
            )
        }

        title = TitleBlock()
        required = ("DRAWN", "MODELED", "DATE", "PART", "SIZE", "DWG", "REV")
        if any(anchors[label] is None for label in required):
            logger.warning("Title block anchors incomplete on page %s", page_number)
            return title

        drawn = anchors["DRAWN"]
        modeled = anchors["MODELED"]
        date = anchors["DATE"]
        part = anchors["PART"]
        size = anchors["SIZE"]
        dwg = anchors["DWG"]
        revision = anchors["REV"]
        assert all(
            anchor is not None for anchor in (drawn, modeled, date, part, size, dwg, revision)
        )

        row_padding = 0.004 * height
        title_right = min(region.x1, max(revision.x1 + 0.04 * width, 0.975 * width))
        left_value_right = part.x0 - 0.002 * width

        title.drawn_by = _text_field(
            words,
            page_number,
            x0=drawn.x1,
            y0=drawn.y0 - row_padding,
            x1=left_value_right,
            y1=modeled.y0,
            excluded={"DRAWN"},
        )
        title.modeled_by = _text_field(
            words,
            page_number,
            x0=modeled.x1,
            y0=modeled.y0 - row_padding,
            x1=left_value_right,
            y1=date.y0,
            excluded={"MODELED"},
        )
        title.drawing_date = _text_field(
            words,
            page_number,
            x0=date.x1,
            y0=date.y0 - row_padding,
            x1=left_value_right,
            y1=part.y0,
            excluded={"DATE"},
            accept=lambda value: bool(re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", value)),
        )
        title.part_name = _text_field(
            words,
            page_number,
            x0=part.x1,
            y0=part.y0,
            x1=title_right,
            y1=size.y0,
            excluded={"PART", "NAME"},
        )

        identifier_y1 = anchors["WEIGHT"].y0 if anchors["WEIGHT"] else size.y1 + 0.04 * height
        title.drawing_size = _text_field(
            words,
            page_number,
            x0=size.x0,
            y0=size.y0,
            x1=dwg.x0,
            y1=identifier_y1,
            excluded={"SIZE"},
            accept=lambda value: bool(re.fullmatch(r"[A-E](?:[0-4])?", value.upper())),
        )
        title.drawing_number = _text_field(
            words,
            page_number,
            x0=dwg.x0,
            y0=dwg.y0 - row_padding,
            x1=revision.x0,
            y1=identifier_y1,
            excluded={"DWG", "NO"},
            accept=lambda value: len(value) >= 4 and bool(re.search(r"\d", value)),
        )
        title.revision = _text_field(
            words,
            page_number,
            x0=revision.x0,
            y0=revision.y0 - row_padding,
            x1=title_right,
            y1=identifier_y1,
            excluded={"REV"},
            accept=lambda value: bool(re.fullmatch(r"[A-Z0-9]{1,4}", value.upper())),
        )

        self._extract_metrics(title, words, anchors, page_number, height, title_right)
        title.critical_component = self._critical_component(page, page_number)
        return title

    def _extract_metrics(
        self,
        title: TitleBlock,
        words: list[NativeWord],
        anchors: dict[str, NativeWord | None],
        page_number: int,
        height: float,
        title_right: float,
    ) -> None:
        weight = anchors["WEIGHT"]
        scale = anchors["SCALE"]
        units = anchors["UNITS"]
        sheet = anchors["SHEET"]
        of_word = anchors["OF"]
        if any(anchor is None for anchor in (weight, scale, units, sheet, of_word)):
            return
        assert weight is not None
        assert scale is not None
        assert units is not None
        assert sheet is not None
        assert of_word is not None

        metric_y0 = min(weight.y0, scale.y0, units.y0, sheet.y0) - 0.003 * height
        metric_y1 = min(0.99 * height, metric_y0 + 0.035 * height)
        number = r"[-+]?\d+(?:\.\d+)?"
        title.weight = _text_field(
            words,
            page_number,
            x0=weight.x0,
            y0=metric_y0,
            x1=scale.x0,
            y1=metric_y1,
            excluded={"WEIGHT", "KILOGRAMS", "KG", "LBS", "COMPONENT"},
            accept=lambda value: bool(re.fullmatch(number, value)),
        )
        title.scale = _text_field(
            words,
            page_number,
            x0=scale.x0,
            y0=metric_y0,
            x1=units.x0,
            y1=metric_y1,
            excluded={"SCALE"},
            accept=lambda value: bool(
                re.fullmatch(r"(?:[-+]?\d+(?:\.\d+)?(?:\s*:\s*\d+(?:\.\d+)?)?|NTS)", value, re.I)
            ),
        )
        title.units = _text_field(
            words,
            page_number,
            x0=units.x0,
            y0=metric_y0,
            x1=sheet.x0,
            y1=metric_y1,
            excluded={"UNITS"},
            accept=lambda value: bool(re.fullmatch(r"[A-Za-zµμ\"]{1,12}", value)),
        )

        sheet_words = _words_in_rect(
            words,
            x0=sheet.x0,
            y0=metric_y0,
            x1=title_right,
            y1=metric_y1,
            excluded={"SHEET", "OF"},
        )
        current = [
            word
            for word in sheet_words
            if sheet.x1 <= word.center_x < of_word.x0 and word.text.isdigit()
        ]
        total = [
            word for word in sheet_words if word.center_x >= of_word.x1 and word.text.isdigit()
        ]
        if current:
            title.sheet_number = _known(int(current[0].text), [current[0]], page_number)
        if total:
            title.sheet_count = _known(int(total[0].text), [total[0]], page_number)

    def _critical_component(self, page: pymupdf.Page, page_number: int) -> ExtractedField[bool]:
        words = _native_words(page)
        positive_sequences = (
            ("THIS", "ITEM", "HAS", "BEEN", "IDENTIFIED", "AS", "A", "CRITICAL", "ITEM"),
            ("IDENTIFIED", "AS", "A", "CRITICAL", "COMPONENT"),
        )
        negative_sequences = (
            ("NOT", "A", "CRITICAL", "ITEM"),
            ("NOT", "A", "CRITICAL", "COMPONENT"),
            ("NONCRITICAL", "COMPONENT"),
        )
        for sequence in negative_sequences:
            matched = _sequence_bbox(words, sequence)
            if matched:
                return _known(False, matched, page_number)
        for sequence in positive_sequences:
            matched = _sequence_bbox(words, sequence)
            if matched:
                return _known(True, matched, page_number)
        return _unknown()
