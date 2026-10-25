"""Storage contract, private object operations, and restart regression coverage."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import Forbidden, NotFound, PreconditionFailed, ServiceUnavailable
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage
from pydantic import ValidationError

from backend.app import main
from backend.app.config import Settings
from backend.app.drawing_store import DrawingNotFoundError, DrawingStorageError, DrawingStore
from backend.app.gcs_drawing_store import GCSDrawingStore
from backend.app.models.drawing import DrawingDocument
from backend.app.vision.models import VisualReview


@pytest.fixture
def mocked_gcs(monkeypatch):
    """Mock SDK methods over durable bytes; no GCP credentials/network required."""
    objects = {}
    blobs = {}
    client = Mock(spec=storage.Client)
    bucket = Mock(spec=storage.Bucket)
    client.bucket.return_value = bucket

    def blob_for(name):
        if name in blobs:
            return blobs[name]
        blob = Mock(spec=storage.Blob)
        blob.name = name
        blob.generation = 0

        def upload(content, *, content_type, if_generation_match=None):
            if if_generation_match == 0 and name in objects:
                raise PreconditionFailed("object exists")
            objects[name] = content.encode("utf-8") if isinstance(content, str) else content
            blob.generation += 1

        def upload_file(filename, **kwargs):
            upload(Path(filename).read_bytes(), **kwargs)

        def download():
            if name not in objects:
                raise NotFound("object missing")
            return objects[name]

        def download_file(filename):
            Path(filename).write_bytes(download())

        def delete(**kwargs):
            assert kwargs["if_generation_match"] == blob.generation
            del objects[name]

        blob.upload_from_string.side_effect = upload
        blob.upload_from_filename.side_effect = upload_file
        blob.download_as_bytes.side_effect = download
        blob.download_to_filename.side_effect = download_file
        blob.delete.side_effect = delete
        blobs[name] = blob
        return blob

    bucket.blob.side_effect = blob_for
    client.list_blobs.side_effect = lambda _bucket, prefix: [
        blob_for(name) for name in sorted(objects) if name.startswith(prefix)
    ]
    constructor = Mock(return_value=client)
    monkeypatch.setattr("backend.app.gcs_drawing_store.storage.Client", constructor)
    return client, bucket, objects, blobs, constructor


@pytest.mark.parametrize("backend", ["local", "gcs"])
def test_all_resources_and_exports_survive_restart(
    backend, tmp_path, synthetic_drawing, mocked_gcs, monkeypatch
):
    configured = Settings(
        storage_backend=backend,
        storage_dir=tmp_path / "persistent-local",
        gcs_bucket="private-drawings",
        vision_debug_overlays=True,
        vision_dpi=72,
        ocr_enabled=False,
    )
    temporary_paths = []

    @contextmanager
    def processing_directory(**kwargs):
        with TemporaryDirectory(dir=tmp_path, **kwargs) as directory:
            temporary_paths.append(Path(directory))
            yield directory

    monkeypatch.setattr(main, "TemporaryDirectory", processing_directory)
    main.app.dependency_overrides[main.get_api_settings] = lambda: configured
    try:
        with TestClient(main.app) as client:
            uploaded = client.post(
                "/api/drawings/upload",
                files={
                    "file": (
                        "../../untrusted.pdf",
                        synthetic_drawing.read_bytes(),
                        "application/pdf",
                    )
                },
            )
            assert uploaded.status_code == 201, uploaded.text
            drawing_id = uploaded.json()["id"]
            assert str(UUID(drawing_id)) == drawing_id
            base = f"/api/drawings/{drawing_id}"
            assert uploaded.json()["drawing"]["source_filename"]["value"] == "untrusted.pdf"
            complete = client.post(base + "/analysis/complete")
            assert complete.status_code == 200, complete.text
            vision = client.get(base + "/vision").json()
            # Ensure an object review is covered even on drawings with no visual candidates.
            if not vision["objects"]:
                from backend.app.vision.models import VisionReport, VisualObject

                report = VisionReport.model_validate(vision)
                report.objects.append(
                    VisualObject(
                        object_type="UNKNOWN",
                        page_number=1,
                        bounding_box=(1, 1, 2, 2),
                        confidence=0.5,
                        detector="test_fixture",
                    )
                )
                dependency = main.get_drawing_store(configured)
                store = next(dependency)
                try:
                    store.save_vision(drawing_id, report)
                finally:
                    dependency.close()
                vision = report.model_dump(mode="json")
            object_id = vision["objects"][0]["object_id"]
            review = client.post(
                base + f"/vision/objects/{object_id}/review",
                json={"object_id": object_id, "action": "CONFIRM"},
            )
            assert review.status_code == 200
            paths = [
                "",
                "/pages",
                "/notes",
                "/bom",
                "/revisions",
                "/standards",
                "/supplier",
                "/export/json",
                "/export/csv",
                "/source",
                "/validation",
                "/validation/summary",
                "/validation/rules",
                "/validation/results/TB-001",
                "/validation/export/json",
                "/validation/export/csv",
                "/vision",
                "/vision/summary",
                "/vision/objects",
                f"/vision/objects/{object_id}",
                "/vision/reviews",
                "/vision/export/json",
                "/relationships",
                "/relationships/summary",
                "/relationships/findings",
                "/relationships/graph",
                "/relationships/export/json",
                "/report",
                "/report/export/json",
                "/report/export/csv",
                "/vision/evidence/page_1_level3_overlay.png",
            ]
            before = {path: client.get(base + path) for path in paths}
            assert all(response.status_code == 200 for response in before.values())
            assert before["/source"].content == synthetic_drawing.read_bytes()
            assert before["/vision/evidence/page_1_level3_overlay.png"].content.startswith(
                b"\x89PNG"
            )

        # Every GCS request has already removed its working copies. A fresh API
        # client and freshly constructed stores can only use bucket objects.
        assert all(not path.exists() for path in temporary_paths)
        with TestClient(main.app) as restarted:
            for path, previous in before.items():
                response = restarted.get(base + path)
                assert response.status_code == 200, (path, response.text)
                assert response.content == previous.content, path
                assert response.headers["content-type"] == previous.headers["content-type"]
            # Re-analysis must download the persisted PDF on the new instance.
            assert restarted.post(base + "/vision/analyze").status_code == 200
            assert restarted.post(base + "/validate").status_code == 200
            assert restarted.post(base + "/relationships/analyze").status_code == 200
        assert all(not path.exists() for path in temporary_paths)
    finally:
        main.app.dependency_overrides.clear()

    _, bucket, objects, blobs, constructor = mocked_gcs
    if backend == "local":
        constructor.assert_not_called()
        directory = configured.storage_dir / drawing_id
        assert {
            "source.pdf",
            "result.json",
            "validation.json",
            "vision.json",
            "relationships.json",
            "vision_reviews.json",
            "vision_debug",
        } <= {path.name for path in directory.iterdir()}
        assert not list(directory.rglob("*.part"))
    else:
        assert not configured.storage_dir.exists()
        assert temporary_paths
        constructor.assert_called_with()  # ADC, no explicit credentials/key file.
        assert all(name.startswith(f"drawings/{drawing_id}/") for name in objects)
        assert not any("untrusted" in name or ".part" in name for name in objects)
        for name in (
            "source.pdf",
            "result.json",
            "validation.json",
            "vision.json",
            "relationships.json",
            "vision_debug/page_1_level3_overlay.png",
        ):
            assert f"drawings/{drawing_id}/{name}" in objects
        for blob in blobs.values():
            blob.make_public.assert_not_called()
            blob.generate_signed_url.assert_not_called()
        bucket.acl.save.assert_not_called()


@pytest.mark.parametrize("backend", ["local", "gcs"])
def test_store_rejects_unsafe_ids_and_artifact_paths(backend, tmp_path, mocked_gcs):
    store = (
        DrawingStore(tmp_path)
        if backend == "local"
        else GCSDrawingStore("private-drawings", tmp_path)
    )
    for drawing_id in ("../escape", "/absolute", "bad-id", str(uuid4()).upper(), "..\\escape"):
        for operation in (
            store.source_path,
            store.load_result,
            store.load_validation,
            store.load_vision,
            store.load_relationships,
            store.discard,
            store.load_visual_reviews,
            store.debug_directory,
        ):
            with pytest.raises(DrawingNotFoundError):
                operation(drawing_id)
    for name in ("../source.pdf", "..\\source.pdf", "/source.pdf", "page_0_level3_overlay.png"):
        with pytest.raises(DrawingNotFoundError):
            store.evidence_path(str(uuid4()), name)
    mocked_gcs[1].blob.assert_not_called()


@pytest.mark.parametrize("backend", ["local", "gcs"])
def test_missing_records_and_reviews(backend, tmp_path, mocked_gcs):
    store = (
        DrawingStore(tmp_path)
        if backend == "local"
        else GCSDrawingStore("private-drawings", tmp_path)
    )
    drawing_id = str(uuid4())
    for operation in (
        store.load_result,
        store.load_validation,
        store.load_vision,
        store.load_relationships,
        store.source_path,
    ):
        with pytest.raises(DrawingNotFoundError):
            operation(drawing_id)
    assert store.load_visual_reviews(drawing_id) == []


def test_gcs_reviews_from_independent_instances_are_preserved(tmp_path, mocked_gcs):
    first = GCSDrawingStore("private-drawings", tmp_path / "one")
    second = GCSDrawingStore("private-drawings", tmp_path / "two")
    drawing_id = str(uuid4())
    review1 = VisualReview(object_id="one", action="CONFIRM")
    # Equal timestamps must not make preservation depend on UUID/list ordering.
    review2 = VisualReview(object_id="two", action="REJECT", reviewed_at=review1.reviewed_at)
    first.append_visual_review(drawing_id, review1)
    second.append_visual_review(drawing_id, review2)
    assert sorted(first.load_visual_reviews(drawing_id), key=lambda item: item.object_id) == [
        review1,
        review2,
    ]
    assert len(mocked_gcs[2]) == 2


def test_gcs_discard_only_removes_target_record(tmp_path, mocked_gcs):
    store = GCSDrawingStore("private-drawings", tmp_path)
    first, partial = store.create_record()
    partial.write_bytes(b"%PDF-test")
    store.finalize_source(first)
    store.save_result(first, DrawingDocument())
    second, other_partial = store.create_record()
    other_partial.write_bytes(b"%PDF-other")
    store.finalize_source(second)
    store.discard(first)
    assert not (tmp_path / first).exists()
    assert list(mocked_gcs[2]) == [f"drawings/{second}/source.pdf"]
    assert (tmp_path / second).exists()


@pytest.mark.parametrize("failure", [Forbidden("denied"), ServiceUnavailable("unavailable")])
def test_gcs_failure_returns_503_without_leaking_details(tmp_path, mocked_gcs, failure):
    configured = Settings(storage_backend="gcs", gcs_bucket="private-drawings")
    main.app.dependency_overrides[main.get_api_settings] = lambda: configured
    drawing_id = str(uuid4())
    mocked_gcs[1].blob(f"drawings/{drawing_id}/result.json").download_as_bytes.side_effect = failure
    try:
        with TestClient(main.app) as client:
            response = client.get(f"/api/drawings/{drawing_id}")
        assert response.status_code == 503
        assert response.json() == {"detail": "Drawing storage is unavailable."}
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "failure_stage", ["invalid_pdf", "parse", "source_upload", "result_upload", "cleanup"]
)
def test_gcs_upload_failures_clean_up(tmp_path, synthetic_drawing, mocked_gcs, failure_stage):
    configured = Settings(storage_backend="gcs", gcs_bucket="private-drawings")
    main.app.dependency_overrides[main.get_api_settings] = lambda: configured
    client_mock, bucket, objects, _, _ = mocked_gcs
    original_blob = bucket.blob.side_effect

    def failing_blob(name):
        blob = original_blob(name)
        if failure_stage == "source_upload" and name.endswith("/source.pdf"):
            blob.upload_from_filename.side_effect = ServiceUnavailable("bucket unavailable")
        if failure_stage == "result_upload" and name.endswith("/result.json"):
            blob.upload_from_string.side_effect = Forbidden("denied")
        return blob

    bucket.blob.side_effect = failing_blob
    if failure_stage in {"parse", "cleanup"}:
        parser = Mock()
        parser.parse.side_effect = RuntimeError("parse failed")
        main.app.dependency_overrides[main.get_drawing_parser] = lambda: parser
    if failure_stage == "cleanup":
        client_mock.list_blobs.side_effect = Forbidden("cleanup denied")
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/drawings/upload",
                files={
                    "file": (
                        "drawing.pdf",
                        b"invalid"
                        if failure_stage == "invalid_pdf"
                        else synthetic_drawing.read_bytes(),
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == (503 if failure_stage.endswith("upload") else 422)
        if failure_stage == "cleanup":
            assert len(objects) == 1
            assert next(iter(objects)).endswith("/source.pdf")
        else:
            assert not objects
        assert client_mock.list_blobs.called
    finally:
        main.app.dependency_overrides.clear()


def test_gcs_source_creation_prevents_overwrite(tmp_path, mocked_gcs):
    store = GCSDrawingStore("private-drawings", tmp_path)
    drawing_id, partial = store.create_record()
    partial.write_bytes(b"original")
    store.finalize_source(drawing_id)
    partial.write_bytes(b"replacement")
    with pytest.raises(DrawingStorageError):
        store.finalize_source(drawing_id)
    store.discard(drawing_id)
    assert mocked_gcs[2][f"drawings/{drawing_id}/source.pdf"] == b"original"
    assert not (tmp_path / drawing_id).exists()


def test_missing_adc_is_storage_error(tmp_path, mocked_gcs):
    mocked_gcs[4].side_effect = DefaultCredentialsError("credentials missing")
    with pytest.raises(DrawingStorageError):
        GCSDrawingStore("private-drawings", tmp_path)


@pytest.mark.parametrize(
    "values",
    [
        {"storage_backend": "invalid"},
        {"storage_backend": "gcs"},
        {"storage_backend": "gcs", "gcs_bucket": " "},
        {"storage_backend": "gcs", "gcs_bucket": "gs://bucket"},
        {"storage_backend": "gcs", "gcs_bucket": "bucket/prefix"},
    ],
)
def test_invalid_storage_configuration_fails_fast(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_storage_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("DRAWING_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("DRAWING_GCS_BUCKET", "private-drawings")
    configured = Settings()
    assert configured.storage_backend == "gcs"
    assert configured.gcs_bucket == "private-drawings"
    monkeypatch.delenv("DRAWING_STORAGE_BACKEND")
    monkeypatch.delenv("DRAWING_GCS_BUCKET")
    assert Settings().storage_backend == "local"
