"""Private GCS persistence using ADC; local files are request-scoped working copies."""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from google.api_core.exceptions import GoogleAPICallError, NotFound, PreconditionFailed
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

from backend.app.drawing_store import (
    JSON_ARTIFACTS,
    DrawingNotFoundError,
    DrawingStorageError,
    DrawingStore,
)
from backend.app.vision.models import VisionReport, VisualReview

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _storage_operation() -> Iterator[None]:
    try:
        yield
    except (GoogleAPICallError, GoogleAuthError) as exc:
        raise DrawingStorageError("Drawing storage is unavailable.") from exc


class GCSDrawingStore(DrawingStore):
    """Keep only PDFs/analysis/evidence in GCS, never processing scratch files.

    The caller owns and removes processing_root after the request. Reads always
    consult GCS, so a new instance needs no files from an earlier instance.
    """

    def __init__(
        self,
        bucket_name: str,
        processing_root: str | Path,
        *,
        client: storage.Client | None = None,
    ) -> None:
        super().__init__(processing_root)
        # No credentials argument or key-file loading: Cloud Run supplies ADC.
        try:
            self.client = client if client is not None else storage.Client()
        except GoogleAuthError as exc:
            raise DrawingStorageError("Drawing storage authentication is unavailable.") from exc
        self.bucket = self.client.bucket(bucket_name)
        self._conflicting_records: set[str] = set()

    def close(self) -> None:
        self.client.close()

    def _prefix(self, drawing_id: str) -> str:
        # Reuse canonical UUID validation before any remote operation.
        return f"drawings/{self._record_directory(drawing_id).name}/"

    def _blob(self, drawing_id: str, name: str) -> storage.Blob:
        if name not in JSON_ARTIFACTS | {"source.pdf"} and not re.fullmatch(
            r"vision_debug/page_[1-9][0-9]*_level3_overlay\.png|"
            r"vision_reviews/[0-9a-f]{32}\.json",
            name,
        ):
            raise ValueError("Unsupported drawing artifact")
        return self.bucket.blob(self._prefix(drawing_id) + name)

    def finalize_source(self, drawing_id: str) -> Path:
        source = super().finalize_source(drawing_id)
        with _storage_operation():
            try:
                self._blob(drawing_id, "source.pdf").upload_from_filename(
                    str(source), content_type="application/pdf", if_generation_match=0
                )
            except PreconditionFailed:
                # A UUID collision must never make failed-upload cleanup delete
                # a different instance's existing record.
                self._conflicting_records.add(drawing_id)
                raise
        return source

    def source_path(self, drawing_id: str) -> Path:
        return self._download_file(drawing_id, "source.pdf")

    def evidence_path(self, drawing_id: str, filename: str) -> Path:
        if not re.fullmatch(r"page_[1-9][0-9]*_level3_overlay\.png", filename):
            raise DrawingNotFoundError(drawing_id)
        return self._download_file(drawing_id, f"vision_debug/{filename}")

    def _download_file(self, drawing_id: str, name: str) -> Path:
        blob = self._blob(drawing_id, name)
        target = self._record_directory(drawing_id) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with _storage_operation():
            try:
                blob.download_to_filename(str(target))
            except NotFound as exc:
                raise DrawingNotFoundError(drawing_id) from exc
        return target

    def _write_json(self, drawing_id: str, name: str, content: str) -> None:
        with _storage_operation():
            self._blob(drawing_id, name).upload_from_string(
                content, content_type="application/json"
            )

    def _read_json(self, drawing_id: str, name: str) -> str:
        with _storage_operation():
            try:
                return self._blob(drawing_id, name).download_as_bytes().decode("utf-8")
            except NotFound as exc:
                raise DrawingNotFoundError(drawing_id) from exc

    def save_vision(self, drawing_id: str, report: VisionReport) -> None:
        directory = self._record_directory(drawing_id) / "vision_debug"
        with _storage_operation():
            for path in sorted(directory.glob("page_*_level3_overlay.png")):
                if path.is_symlink():
                    raise ValueError("Visual evidence must not be a symlink")
                self._blob(drawing_id, f"vision_debug/{path.name}").upload_from_filename(
                    str(path), content_type="image/png"
                )
        super().save_vision(drawing_id, report)

    def append_visual_review(self, drawing_id: str, review: VisualReview) -> list[VisualReview]:
        # One immutable object per review avoids lost updates between instances.
        with _storage_operation():
            self._blob(drawing_id, f"vision_reviews/{uuid4().hex}.json").upload_from_string(
                review.model_dump_json(indent=2),
                content_type="application/json",
                if_generation_match=0,
            )
        return self.load_visual_reviews(drawing_id)

    def load_visual_reviews(self, drawing_id: str) -> list[VisualReview]:
        prefix = self._prefix(drawing_id) + "vision_reviews/"
        with _storage_operation():
            reviews = [
                VisualReview.model_validate_json(blob.download_as_bytes())
                for blob in self.client.list_blobs(self.bucket, prefix=prefix)
                if re.fullmatch(r"[0-9a-f]{32}\.json", blob.name.removeprefix(prefix))
            ]
        return sorted(reviews, key=lambda review: review.reviewed_at)

    def discard(self, drawing_id: str) -> None:
        prefix = self._prefix(drawing_id)
        try:
            if drawing_id in self._conflicting_records:
                return
            with _storage_operation():
                for blob in self.client.list_blobs(self.bucket, prefix=prefix):
                    try:
                        blob.delete(if_generation_match=blob.generation)
                    except NotFound:
                        pass
        finally:
            super().discard(drawing_id)
