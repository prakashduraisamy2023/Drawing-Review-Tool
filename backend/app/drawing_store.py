"""Filesystem persistence for uploaded drawings and extraction JSON."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from backend.app.models.drawing import DrawingDocument
from backend.app.relationships.models import RelationshipReport
from backend.app.validation.models import ValidationReport
from backend.app.vision.models import VisionReport, VisualReview


class DrawingNotFoundError(LookupError):
    pass


class DrawingStore:
    """Store each drawing beneath an opaque UUID directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def create_record(self) -> tuple[str, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            drawing_id = str(uuid4())
            directory = self.root / drawing_id
            try:
                directory.mkdir()
            except FileExistsError:
                continue
            return drawing_id, directory / "source.pdf.part"

    def finalize_source(self, drawing_id: str) -> Path:
        directory = self._record_directory(drawing_id)
        partial = directory / "source.pdf.part"
        source = directory / "source.pdf"
        partial.replace(source)
        return source

    def save_result(self, drawing_id: str, document: DrawingDocument) -> None:
        directory = self._record_directory(drawing_id)
        target = directory / "result.json"
        temporary = directory / "result.json.part"
        temporary.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def load_result(self, drawing_id: str) -> DrawingDocument:
        target = self._record_directory(drawing_id) / "result.json"
        if not target.is_file():
            raise DrawingNotFoundError(drawing_id)
        return DrawingDocument.model_validate_json(target.read_text(encoding="utf-8"))

    def save_validation(self, drawing_id: str, report: ValidationReport) -> None:
        directory = self._record_directory(drawing_id)
        target = directory / "validation.json"
        temporary = directory / "validation.json.part"
        temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def load_validation(self, drawing_id: str) -> ValidationReport:
        target = self._record_directory(drawing_id) / "validation.json"
        if not target.is_file():
            raise DrawingNotFoundError(drawing_id)
        return ValidationReport.model_validate_json(target.read_text(encoding="utf-8"))

    def save_vision(self, drawing_id: str, report: VisionReport) -> None:
        directory = self._record_directory(drawing_id)
        target = directory / "vision.json"
        temporary = directory / "vision.json.part"
        temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def load_vision(self, drawing_id: str) -> VisionReport:
        target = self._record_directory(drawing_id) / "vision.json"
        if not target.is_file():
            raise DrawingNotFoundError(drawing_id)
        return VisionReport.model_validate_json(target.read_text(encoding="utf-8"))

    def save_relationships(self, drawing_id: str, report: RelationshipReport) -> None:
        directory = self._record_directory(drawing_id)
        target = directory / "relationships.json"
        temporary = directory / "relationships.json.part"
        temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def load_relationships(self, drawing_id: str) -> RelationshipReport:
        target = self._record_directory(drawing_id) / "relationships.json"
        if not target.is_file():
            raise DrawingNotFoundError(drawing_id)
        return RelationshipReport.model_validate_json(target.read_text(encoding="utf-8"))

    def source_path(self, drawing_id: str) -> Path:
        source = self._record_directory(drawing_id) / "source.pdf"
        if not source.is_file():
            raise DrawingNotFoundError(drawing_id)
        return source

    def debug_directory(self, drawing_id: str) -> Path:
        directory = self._record_directory(drawing_id) / "vision_debug"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def append_visual_review(self, drawing_id: str, review: VisualReview) -> list[VisualReview]:
        directory = self._record_directory(drawing_id)
        target = directory / "vision_reviews.json"
        reviews = (
            [
                VisualReview.model_validate(item)
                for item in json.loads(target.read_text(encoding="utf-8"))
            ]
            if target.is_file()
            else []
        )
        reviews.append(review)
        temporary = directory / "vision_reviews.json.part"
        temporary.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in reviews],
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        temporary.replace(target)
        return reviews

    def load_visual_reviews(self, drawing_id: str) -> list[VisualReview]:
        target = self._record_directory(drawing_id) / "vision_reviews.json"
        if not target.is_file():
            return []
        return [
            VisualReview.model_validate(item)
            for item in json.loads(target.read_text(encoding="utf-8"))
        ]

    def discard(self, drawing_id: str) -> None:
        directory = self._record_directory(drawing_id)
        if directory.is_dir():
            shutil.rmtree(directory)

    def _record_directory(self, drawing_id: str) -> Path:
        try:
            canonical_id = str(UUID(drawing_id))
        except (ValueError, AttributeError) as exc:
            raise DrawingNotFoundError(drawing_id) from exc
        if canonical_id != drawing_id:
            raise DrawingNotFoundError(drawing_id)
        return self.root / canonical_id
