"""Offline OCR provider abstraction used only on targeted image crops."""

from __future__ import annotations

import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float
    pixel_bounding_box: tuple[int, int, int, int]


@dataclass(frozen=True)
class OCRResult:
    words: tuple[OCRWord, ...]
    raw_text: str
    execution_time_ms: float
    warnings: tuple[str, ...] = ()


class OCRProvider(ABC):
    name: str

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def recognize(self, image: np.ndarray) -> OCRResult:
        raise NotImplementedError


class DisabledOCRProvider(OCRProvider):
    name = "disabled"

    @property
    def available(self) -> bool:
        return False

    def recognize(self, image: np.ndarray) -> OCRResult:
        return OCRResult((), "", 0.0, ("OCR is disabled by configuration.",))


class TesseractOCRProvider(OCRProvider):
    name = "tesseract"

    @property
    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def recognize(self, image: np.ndarray) -> OCRResult:
        if not self.available:
            return OCRResult((), "", 0.0, ("Tesseract executable is not available.",))
        import pytesseract
        from pytesseract import Output

        started = time.perf_counter()
        data = pytesseract.image_to_data(image, output_type=Output.DICT, config="--psm 6")
        words: list[OCRWord] = []
        for index, raw_text in enumerate(data.get("text", [])):
            text = str(raw_text).strip()
            try:
                confidence = max(0.0, min(1.0, float(data["conf"][index]) / 100.0))
            except (KeyError, TypeError, ValueError):
                confidence = 0.0
            if not text or confidence <= 0:
                continue
            left = int(data["left"][index])
            top = int(data["top"][index])
            width = int(data["width"][index])
            height = int(data["height"][index])
            words.append(OCRWord(text, confidence, (left, top, left + width, top + height)))
        elapsed = (time.perf_counter() - started) * 1000
        return OCRResult(tuple(words), " ".join(word.text for word in words), elapsed)


def build_ocr_provider(*, enabled: bool, name: str) -> OCRProvider:
    if not enabled:
        return DisabledOCRProvider()
    if name.lower() == "tesseract":
        return TesseractOCRProvider()
    return DisabledOCRProvider()
