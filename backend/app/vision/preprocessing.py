"""Reusable detector-specific OpenCV preprocessing primitives."""

from __future__ import annotations

import cv2
import numpy as np


def grayscale(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def normalize_contrast(image: np.ndarray) -> np.ndarray:
    gray = grayscale(image)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def adaptive_threshold(image: np.ndarray, *, block_size: int = 31, c: int = 11) -> np.ndarray:
    size = block_size if block_size % 2 else block_size + 1
    return cv2.adaptiveThreshold(
        grayscale(image), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, size, c
    )


def binary_threshold(image: np.ndarray, threshold: int = 180) -> np.ndarray:
    _, result = cv2.threshold(grayscale(image), threshold, 255, cv2.THRESH_BINARY_INV)
    return result


def edge_detection(image: np.ndarray, low: int = 60, high: int = 180) -> np.ndarray:
    return cv2.Canny(grayscale(image), low, high)


def morphological_cleanup(
    image: np.ndarray, *, kernel_size: int = 3, iterations: int = 1
) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    opened = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel, iterations=iterations)
    return cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=iterations)


def connected_components(image: np.ndarray) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    return cv2.connectedComponentsWithStats(image, connectivity=8)


def contours(image: np.ndarray) -> list[np.ndarray]:
    found, _ = cv2.findContours(image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return list(found)


def upscale_crop(image: np.ndarray, factor: float = 2.0) -> np.ndarray:
    return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def deskew_crop(image: np.ndarray) -> np.ndarray:
    binary = adaptive_threshold(image)
    points = np.column_stack(np.where(binary > 0))
    if len(points) < 10:
        return image
    angle = cv2.minAreaRect(points[:, ::-1].astype(np.float32))[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.15:
        return image
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
