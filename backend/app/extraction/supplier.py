"""Supplier-information extraction interface."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.extraction.classification import DocumentClassifier
from backend.app.models.drawing import SupplierInfo

logger = logging.getLogger(__name__)


class SupplierInfoExtractor:
    """Extract explicit supplier metadata without using the source filename."""

    def __init__(self, classifier: DocumentClassifier | None = None) -> None:
        self.classifier = classifier or DocumentClassifier()

    def extract(self, pdf_path: str | Path) -> SupplierInfo:
        path = Path(pdf_path)
        supplier = self.classifier.extract(path).supplier.model_copy(deep=True)
        logger.info("Extracted supplier information from %s", path.name)
        return supplier
