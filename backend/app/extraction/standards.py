"""Engineering-standard reference extraction."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.app.extraction.notes import NotesExtractor
from backend.app.models.drawing import StandardReference

logger = logging.getLogger(__name__)


class StandardsExtractor:
    """Collect unique explicit standards already evidenced in drawing notes."""

    def __init__(self, notes_extractor: NotesExtractor | None = None) -> None:
        self.notes_extractor = notes_extractor or NotesExtractor()

    def extract(self, pdf_path: str | Path) -> list[StandardReference]:
        path = Path(pdf_path)
        references: list[StandardReference] = []
        seen: set[str] = set()
        for note in self.notes_extractor.extract(path):
            for reference in note.standards or []:
                value = reference.designation.value
                if value is None:
                    continue
                key = re.sub(r"\s+", " ", value).strip().upper()
                if key in seen:
                    continue
                seen.add(key)
                references.append(reference.model_copy(deep=True))
        logger.info("Extracted %s standard reference(s) from %s", len(references), path.name)
        return references
