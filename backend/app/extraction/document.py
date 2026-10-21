from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz

from backend.app.schemas import ExtractionMethod

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(frozen=True)
class TextLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class PageContent:
    number: int
    width: float
    height: float
    text: str
    words: list[Word] = field(default_factory=list)
    lines: list[TextLine] = field(default_factory=list)
    method: ExtractionMethod = ExtractionMethod.NATIVE_TEXT


@dataclass
class DocumentContent:
    path: Path
    pages: list[PageContent]
    metadata: dict[str, str]

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _usable_character_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]", text))


def _group_words_into_lines(words: list[Word], y_tolerance: float = 3.0) -> list[TextLine]:
    grouped: list[list[Word]] = []
    for word in sorted(words, key=lambda item: ((item.y0 + item.y1) / 2, item.x0)):
        center = (word.y0 + word.y1) / 2
        for group in reversed(grouped[-8:]):
            group_center = sum((item.y0 + item.y1) / 2 for item in group) / len(group)
            if abs(center - group_center) <= y_tolerance:
                group.append(word)
                break
        else:
            grouped.append([word])

    lines: list[TextLine] = []
    for group in grouped:
        ordered = sorted(group, key=lambda item: item.x0)
        lines.append(
            TextLine(
                text=" ".join(item.text for item in ordered),
                x0=min(item.x0 for item in ordered),
                y0=min(item.y0 for item in ordered),
                x1=max(item.x1 for item in ordered),
                y1=max(item.y1 for item in ordered),
            )
        )
    return sorted(lines, key=lambda item: (item.y0, item.x0))


def ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def _ocr_page(page: fitz.Page) -> tuple[str, list[Word]]:
    import pytesseract
    from PIL import Image
    from pytesseract import Output

    pixmap = page.get_pixmap(dpi=200, alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    x_scale = page.rect.width / pixmap.width
    y_scale = page.rect.height / pixmap.height
    words: list[Word] = []
    for index, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue
        x = float(data["left"][index]) * x_scale
        y = float(data["top"][index]) * y_scale
        width = float(data["width"][index]) * x_scale
        height = float(data["height"][index]) * y_scale
        words.append(Word(x, y, x + width, y + height, text))
    lines = _group_words_into_lines(words, y_tolerance=4.0)
    return "\n".join(line.text for line in lines), words


def read_document(
    path: Path,
    *,
    ocr_enabled: bool,
    native_text_min_characters: int,
) -> DocumentContent:
    pages: list[PageContent] = []
    with fitz.open(path) as document:
        metadata = {key: value for key, value in document.metadata.items() if value}
        can_ocr = ocr_enabled and ocr_available()
        if ocr_enabled and not can_ocr:
            logger.warning("OCR requested but Tesseract is unavailable")

        for page_index, page in enumerate(document):
            text = page.get_text("text", sort=True).strip()
            raw_words = page.get_text("words", sort=True)
            words = [
                Word(float(row[0]), float(row[1]), float(row[2]), float(row[3]), str(row[4]))
                for row in raw_words
                if str(row[4]).strip()
            ]
            method = ExtractionMethod.NATIVE_TEXT

            if _usable_character_count(text) < native_text_min_characters and can_ocr:
                logger.info("Using OCR fallback for page %s", page_index + 1)
                text, words = _ocr_page(page)
                method = ExtractionMethod.OCR

            pages.append(
                PageContent(
                    number=page_index + 1,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    text=text,
                    words=words,
                    lines=_group_words_into_lines(words),
                    method=method,
                )
            )
    return DocumentContent(path=path, pages=pages, metadata=metadata)
