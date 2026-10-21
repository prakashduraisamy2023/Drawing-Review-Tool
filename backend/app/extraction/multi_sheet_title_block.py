"""Independent page extraction and conservative document-level normalization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypeVar

from backend.app.extraction.title_block import TitleBlockExtractor
from backend.app.models.drawing import (
    ExtractedField,
    MultiSheetTitleBlockExtraction,
    PageTitleBlockData,
    TitleBlock,
    TitleBlockPage,
)

logger = logging.getLogger(__name__)

ValueT = TypeVar("ValueT")
HIGH_CONFIDENCE_THRESHOLD = 0.9

PAGE_FIELD_MAP = {
    "drawing_number": "drawing_number",
    "revision": "revision",
    "part_name": "part_name",
    "weight": "weight",
    "sheet_number": "sheet_number",
    "total_sheets": "sheet_count",
    "units": "units",
}


def _unknown() -> ExtractedField:
    return ExtractedField()


def _project_title_block(title_block: TitleBlock) -> PageTitleBlockData:
    return PageTitleBlockData(
        **{
            output_name: getattr(title_block, source_name).model_copy(deep=True)
            for output_name, source_name in PAGE_FIELD_MAP.items()
        }
    )


def _resolve_document_field(
    fields: list[ExtractedField[ValueT]],
) -> ExtractedField[ValueT]:
    """Resolve unanimous evidence without interpreting conflicting values."""
    known = [field for field in fields if field.value is not None]
    if not known:
        return _unknown()

    first_value = known[0].value
    if any(field.value != first_value for field in known[1:]):
        return _unknown()

    complete_consensus = len(known) == len(fields)
    confident_partial_consensus = all(
        field.confidence >= HIGH_CONFIDENCE_THRESHOLD for field in known
    )
    if not complete_consensus and not confident_partial_consensus:
        return _unknown()

    strongest = max(known, key=lambda field: field.confidence)
    return strongest.model_copy(deep=True)


class MultiSheetTitleBlockExtractor:
    """Return page-specific title blocks plus non-conflicting document metadata."""

    def __init__(self, page_extractor: TitleBlockExtractor | None = None) -> None:
        self.page_extractor = page_extractor or TitleBlockExtractor()

    def extract(self, pdf_path: str | Path) -> MultiSheetTitleBlockExtraction:
        extracted = self.page_extractor.extract(pdf_path)
        pages = [
            TitleBlockPage(page=page_number, title_block=_project_title_block(title_block))
            for page_number, title_block in enumerate(extracted, start=1)
        ]
        document_metadata = self.normalize([page.title_block for page in pages])
        logger.info(
            "Built multi-sheet title-block result with %s page(s) for %s",
            len(pages),
            Path(pdf_path).name,
        )
        return MultiSheetTitleBlockExtraction(
            pages=pages,
            document_metadata=document_metadata,
        )

    def normalize(self, title_blocks: list[PageTitleBlockData]) -> PageTitleBlockData:
        """Normalize only exact, non-conflicting values across available pages."""
        if not title_blocks:
            return PageTitleBlockData()
        return PageTitleBlockData(
            **{
                field_name: _resolve_document_field(
                    [getattr(title_block, field_name) for title_block in title_blocks]
                )
                for field_name in PAGE_FIELD_MAP
            }
        )
