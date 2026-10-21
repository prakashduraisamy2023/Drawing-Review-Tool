"""Single-pass native PDF context shared by Level-1 orchestration stages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pymupdf

BoundingBox = tuple[float, float, float, float]


class PageTemplate(StrEnum):
    CLUB_CAR_17X11 = "CLUB_CAR_17X11"
    CLUB_CAR_34X22 = "CLUB_CAR_34X22"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ImageRegion:
    bounding_box: BoundingBox
    normalized_bounding_box: BoundingBox


@dataclass(frozen=True)
class PageContext:
    page_number: int
    width: float
    height: float
    template: PageTemplate
    text: str
    words: tuple[tuple[object, ...], ...]
    blocks: tuple[tuple[object, ...], ...]
    image_regions: tuple[ImageRegion, ...]

    @property
    def native_text_available(self) -> bool:
        return bool(self.text.strip())


@dataclass(frozen=True)
class DocumentContext:
    path: Path
    page_count: int
    pages: tuple[PageContext, ...]


def detect_page_template(width: float, height: float) -> PageTemplate:
    dimensions = (round(width / 72), round(height / 72))
    if dimensions == (17, 11):
        return PageTemplate.CLUB_CAR_17X11
    if dimensions == (34, 22):
        return PageTemplate.CLUB_CAR_34X22
    return PageTemplate.UNKNOWN


def _normalized_bbox(bbox: BoundingBox, width: float, height: float) -> BoundingBox:
    x0, y0, x1, y1 = bbox
    return (x0 / width, y0 / height, x1 / width, y1 / height)


def build_document_context(pdf_path: str | Path) -> DocumentContext:
    path = Path(pdf_path)
    pages: list[PageContext] = []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            width = float(page.rect.width)
            height = float(page.rect.height)
            image_regions = []
            for image in page.get_image_info(xrefs=True):
                raw_bbox = image.get("bbox")
                if not raw_bbox or len(raw_bbox) != 4:
                    continue
                bbox = tuple(float(value) for value in raw_bbox)
                image_regions.append(
                    ImageRegion(
                        bounding_box=bbox,
                        normalized_bounding_box=_normalized_bbox(bbox, width, height),
                    )
                )
            pages.append(
                PageContext(
                    page_number=index + 1,
                    width=width,
                    height=height,
                    template=detect_page_template(width, height),
                    text=page.get_text("text", sort=False),
                    words=tuple(tuple(row) for row in page.get_text("words", sort=False)),
                    blocks=tuple(tuple(row) for row in page.get_text("blocks", sort=False)),
                    image_regions=tuple(image_regions),
                )
            )
    return DocumentContext(path=path, page_count=len(pages), pages=tuple(pages))
