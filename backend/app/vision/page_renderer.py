"""Shared PyMuPDF page rendering with exact PDF-coordinate mapping."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from backend.app.models.drawing import BoundingBox


@dataclass(frozen=True)
class NativeWord:
    text: str
    bounding_box: BoundingBox


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    image: np.ndarray
    pdf_width: float
    pdf_height: float
    dpi: int
    native_words: tuple[NativeWord, ...]

    @property
    def x_scale(self) -> float:
        return self.image.shape[1] / self.pdf_width

    @property
    def y_scale(self) -> float:
        return self.image.shape[0] / self.pdf_height

    def pixel_to_pdf_bbox(self, box: tuple[int, int, int, int]) -> BoundingBox:
        x0, y0, x1, y1 = box
        return (
            x0 / self.x_scale,
            y0 / self.y_scale,
            x1 / self.x_scale,
            y1 / self.y_scale,
        )

    def pdf_to_pixel_bbox(self, box: BoundingBox) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = box
        return (
            round(x0 * self.x_scale),
            round(y0 * self.y_scale),
            round(x1 * self.x_scale),
            round(y1 * self.y_scale),
        )


@dataclass(frozen=True)
class RenderedCrop:
    page_number: int
    image: np.ndarray
    pdf_bounding_box: BoundingBox
    dpi: int

    @property
    def x_scale(self) -> float:
        width = self.pdf_bounding_box[2] - self.pdf_bounding_box[0]
        return self.image.shape[1] / width

    @property
    def y_scale(self) -> float:
        height = self.pdf_bounding_box[3] - self.pdf_bounding_box[1]
        return self.image.shape[0] / height

    def pixel_to_pdf_bbox(self, box: tuple[int, int, int, int]) -> BoundingBox:
        x0, y0, x1, y1 = box
        origin_x, origin_y = self.pdf_bounding_box[:2]
        return (
            origin_x + x0 / self.x_scale,
            origin_y + y0 / self.y_scale,
            origin_x + x1 / self.x_scale,
            origin_y + y1 / self.y_scale,
        )


class PageRenderer:
    """Open a PDF once and cache each requested general-purpose page render."""

    def __init__(self, pdf_path: str | Path, *, dpi: int = 200) -> None:
        self.path = Path(pdf_path)
        self.dpi = dpi
        self._document = pymupdf.open(self.path)
        self._cache: dict[tuple[int, int], RenderedPage] = {}
        self.render_time_ms = 0.0

    def __enter__(self) -> PageRenderer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        return self._document.page_count

    def close(self) -> None:
        if not self._document.is_closed:
            self._document.close()

    def render_page(self, page_number: int, *, dpi: int | None = None) -> RenderedPage:
        render_dpi = dpi or self.dpi
        key = (page_number, render_dpi)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if page_number < 1 or page_number > self.page_count:
            raise IndexError(f"Page {page_number} is outside the PDF")
        started = time.perf_counter()
        page = self._document[page_number - 1]
        scale = render_dpi / 72.0
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
        rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        image = cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR)
        words = tuple(
            NativeWord(
                text=str(word[4]).strip(),
                bounding_box=tuple(float(value) for value in word[:4]),
            )
            for word in page.get_text("words", sort=False)
            if str(word[4]).strip()
        )
        rendered = RenderedPage(
            page_number=page_number,
            image=image,
            pdf_width=float(page.rect.width),
            pdf_height=float(page.rect.height),
            dpi=render_dpi,
            native_words=words,
        )
        self._cache[key] = rendered
        self.render_time_ms += (time.perf_counter() - started) * 1000
        return rendered

    def render_crop(
        self,
        page_number: int,
        bounding_box: BoundingBox,
        *,
        dpi: int = 400,
    ) -> RenderedCrop:
        started = time.perf_counter()
        page = self._document[page_number - 1]
        clip = pymupdf.Rect(*bounding_box) & page.rect
        scale = dpi / 72.0
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            colorspace=pymupdf.csRGB,
            alpha=False,
            clip=clip,
        )
        rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        self.render_time_ms += (time.perf_counter() - started) * 1000
        return RenderedCrop(
            page_number=page_number,
            image=cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR),
            pdf_bounding_box=(float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1)),
            dpi=dpi,
        )
