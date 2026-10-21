from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app, get_api_settings, get_drawing_parser

client = TestClient(app)
SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


@pytest.fixture
def drawings_client(tmp_path: Path):
    configured = Settings(
        storage_dir=tmp_path,
        max_upload_bytes=10 * 1024 * 1024,
        ocr_enabled=False,
    )
    app.dependency_overrides[get_api_settings] = lambda: configured
    with TestClient(app) as test_client:
        yield test_client, configured
    app.dependency_overrides.clear()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_endpoint(synthetic_drawing):
    with synthetic_drawing.open("rb") as stream:
        response = client.post(
            "/api/v1/extractions",
            files={"file": (synthetic_drawing.name, stream, "application/pdf")},
        )
    assert response.status_code == 200
    assert response.json()["drawing_number"]["value"] == "ZX-42017"


def test_rejects_non_pdf():
    response = client.post(
        "/api/v1/extractions",
        files={"file": ("drawing.txt", b"not a PDF", "text/plain")},
    )
    assert response.status_code == 415


def test_rejects_invalid_pdf_signature():
    response = client.post(
        "/api/v1/extractions",
        files={"file": ("drawing.pdf", b"not a PDF", "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_safely_persists_and_processes_pdf(drawings_client, synthetic_drawing):
    api_client, configured = drawings_client
    with synthetic_drawing.open("rb") as stream:
        response = api_client.post(
            "/api/drawings/upload",
            files={"file": ("../unsafe-name.pdf", stream, "application/pdf")},
        )

    assert response.status_code == 201
    payload = response.json()
    drawing_id = payload["id"]
    assert str(UUID(drawing_id)) == drawing_id
    assert payload["drawing"]["source_filename"]["value"] == "unsafe-name.pdf"
    assert payload["drawing"]["page_count"]["value"] == 1
    record_directory = configured.storage_dir / drawing_id
    assert (record_directory / "source.pdf").is_file()
    assert (record_directory / "result.json").is_file()
    assert not (record_directory / "source.pdf.part").exists()


def test_level3_api_analyzes_persists_lists_and_exports(drawings_client, synthetic_drawing):
    api_client, configured = drawings_client
    with synthetic_drawing.open("rb") as stream:
        upload = api_client.post(
            "/api/drawings/upload",
            files={"file": (synthetic_drawing.name, stream, "application/pdf")},
        )
    drawing_id = upload.json()["id"]

    before = api_client.get(f"/api/drawings/{drawing_id}/vision")
    analyzed = api_client.post(f"/api/drawings/{drawing_id}/vision/analyze")
    report = api_client.get(f"/api/drawings/{drawing_id}/vision")
    summary = api_client.get(f"/api/drawings/{drawing_id}/vision/summary")
    objects = api_client.get(f"/api/drawings/{drawing_id}/vision/objects")
    missing_object = api_client.get(f"/api/drawings/{drawing_id}/vision/objects/not-a-real-object")
    exported = api_client.get(f"/api/drawings/{drawing_id}/vision/export/json")
    relationships = api_client.post(f"/api/drawings/{drawing_id}/relationships/analyze")
    relationship_report = api_client.get(f"/api/drawings/{drawing_id}/relationships")
    relationship_summary = api_client.get(f"/api/drawings/{drawing_id}/relationships/summary")
    relationship_findings = api_client.get(f"/api/drawings/{drawing_id}/relationships/findings")
    relationship_graph = api_client.get(f"/api/drawings/{drawing_id}/relationships/graph")
    relationship_export = api_client.get(f"/api/drawings/{drawing_id}/relationships/export/json")

    assert before.status_code == 404
    assert analyzed.status_code == 200
    assert analyzed.json()["summary"]["pages_processed"] == 1
    assert report.status_code == 200
    assert summary.json()["objects_detected"] == len(objects.json())
    assert missing_object.status_code == 404
    assert exported.headers["content-type"].startswith("application/json")
    assert relationships.status_code == 200
    assert relationship_report.status_code == 200
    assert relationship_summary.json()["relationships_checked"] == len(relationship_findings.json())
    assert "nodes" in relationship_graph.json()
    assert relationship_export.headers["content-type"].startswith("application/json")
    assert (configured.storage_dir / drawing_id / "vision.json").is_file()
    assert (configured.storage_dir / drawing_id / "relationships.json").is_file()


def test_complete_analysis_and_consolidated_exports(drawings_client, synthetic_drawing):
    api_client, _ = drawings_client
    with synthetic_drawing.open("rb") as stream:
        upload = api_client.post(
            "/api/drawings/upload",
            files={"file": (synthetic_drawing.name, stream, "application/pdf")},
        )
    drawing_id = upload.json()["id"]

    complete = api_client.post(f"/api/drawings/{drawing_id}/analysis/complete")
    report = api_client.get(f"/api/drawings/{drawing_id}/report")
    exported_json = api_client.get(f"/api/drawings/{drawing_id}/report/export/json")
    exported_csv = api_client.get(f"/api/drawings/{drawing_id}/report/export/csv")

    assert complete.status_code == 200
    assert complete.json()["level4_status"] == "COMPLETE"
    assert report.status_code == 200
    assert exported_json.headers["content-type"].startswith("application/json")
    assert exported_csv.headers["content-type"].startswith("text/csv")


def test_all_drawing_resource_endpoints(drawings_client):
    api_client, _ = drawings_client
    source = SAMPLES / "47789660_A_watermarked.pdf"
    with source.open("rb") as stream:
        upload = api_client.post(
            "/api/drawings/upload",
            files={"file": (source.name, stream, "application/pdf")},
        )
    assert upload.status_code == 201
    drawing_id = upload.json()["id"]

    drawing = api_client.get(f"/api/drawings/{drawing_id}")
    pages = api_client.get(f"/api/drawings/{drawing_id}/pages")
    notes = api_client.get(f"/api/drawings/{drawing_id}/notes")
    bom = api_client.get(f"/api/drawings/{drawing_id}/bom")
    revisions = api_client.get(f"/api/drawings/{drawing_id}/revisions")
    standards = api_client.get(f"/api/drawings/{drawing_id}/standards")
    supplier = api_client.get(f"/api/drawings/{drawing_id}/supplier")
    exported = api_client.get(f"/api/drawings/{drawing_id}/export/json")
    exported_csv = api_client.get(f"/api/drawings/{drawing_id}/export/csv")

    assert drawing.status_code == 200
    assert drawing.json()["drawing_number"]["value"] == "47789660"
    assert len(pages.json()) == 1
    assert len(notes.json()) == 6
    assert len(bom.json()) == 9
    assert len(revisions.json()) == 1
    assert revisions.json()[0]["revision_description"]["value"] == "INITIAL RELEASE"
    assert standards.status_code == 200
    assert supplier.json()["supplier_name"]["value"] == "SUPREME"
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert exported.headers["content-disposition"] == (
        f'attachment; filename="drawing-{drawing_id}.json"'
    )
    assert exported.json() == drawing.json()
    assert exported_csv.status_code == 200
    assert exported_csv.headers["content-type"].startswith("text/csv")
    assert "supplier_info.supplier_name" in exported_csv.text


def test_validation_endpoints_and_exports(drawings_client):
    api_client, configured = drawings_client
    source = SAMPLES / "47789660_A_watermarked.pdf"
    with source.open("rb") as stream:
        upload = api_client.post(
            "/api/drawings/upload",
            files={"file": (source.name, stream, "application/pdf")},
        )
    drawing_id = upload.json()["id"]

    before = api_client.get(f"/api/drawings/{drawing_id}/validation")
    validated = api_client.post(f"/api/drawings/{drawing_id}/validate")
    report = api_client.get(f"/api/drawings/{drawing_id}/validation")
    summary = api_client.get(f"/api/drawings/{drawing_id}/validation/summary")
    rules = api_client.get(f"/api/drawings/{drawing_id}/validation/rules")
    detail = api_client.get(f"/api/drawings/{drawing_id}/validation/results/TB-001")
    exported_json = api_client.get(f"/api/drawings/{drawing_id}/validation/export/json")
    exported_csv = api_client.get(f"/api/drawings/{drawing_id}/validation/export/csv")

    assert before.status_code == 404
    assert validated.status_code == 200
    assert validated.json()["summary"]["total_rules"] == 108
    assert report.json() == validated.json()
    assert summary.json() == validated.json()["summary"]
    assert len(rules.json()) == 108
    assert detail.json()["rule_id"] == "TB-001"
    assert detail.json()["evidence"][0]["bounding_box"]
    assert exported_json.json() == validated.json()
    assert "Automated validation assists" in exported_csv.text
    assert (configured.storage_dir / drawing_id / "validation.json").is_file()


@pytest.mark.parametrize(
    "path",
    [
        "/api/drawings/{id}",
        "/api/drawings/{id}/pages",
        "/api/drawings/{id}/notes",
        "/api/drawings/{id}/bom",
        "/api/drawings/{id}/revisions",
        "/api/drawings/{id}/standards",
        "/api/drawings/{id}/supplier",
        "/api/drawings/{id}/export/json",
        "/api/drawings/{id}/export/csv",
    ],
)
def test_unknown_drawing_returns_404(drawings_client, path: str):
    api_client, _ = drawings_client
    response = api_client.get(path.format(id=uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == "Drawing not found."


def test_new_upload_endpoint_rejects_non_pdf_and_bad_pdf(drawings_client):
    api_client, configured = drawings_client

    wrong_extension = api_client.post(
        "/api/drawings/upload",
        files={"file": ("drawing.txt", b"%PDF-invalid", "application/pdf")},
    )
    wrong_signature = api_client.post(
        "/api/drawings/upload",
        files={"file": ("drawing.pdf", b"not a PDF", "application/pdf")},
    )
    unreadable_pdf = api_client.post(
        "/api/drawings/upload",
        files={"file": ("drawing.pdf", b"%PDF-1.7\nbroken", "application/pdf")},
    )
    wrong_mime = api_client.post(
        "/api/drawings/upload",
        files={"file": ("drawing.pdf", b"%PDF-invalid", "application/octet-stream")},
    )
    empty_pdf = api_client.post(
        "/api/drawings/upload",
        files={"file": ("drawing.pdf", b"", "application/pdf")},
    )

    assert wrong_extension.status_code == 415
    assert wrong_signature.status_code == 422
    assert unreadable_pdf.status_code == 422
    assert wrong_mime.status_code == 415
    assert empty_pdf.status_code == 422
    assert list(configured.storage_dir.iterdir()) == []


def test_upload_size_limit_uses_configuration(tmp_path: Path):
    configured = Settings(
        storage_dir=tmp_path,
        max_upload_bytes=10,
        ocr_enabled=False,
    )
    app.dependency_overrides[get_api_settings] = lambda: configured
    try:
        with TestClient(app) as api_client:
            response = api_client.post(
                "/api/drawings/upload",
                files={"file": ("drawing.pdf", b"%PDF-" + b"x" * 20, "application/pdf")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "10-byte upload limit" in response.json()["detail"]
    assert list(tmp_path.iterdir()) == []


def test_processing_failure_does_not_leave_partial_record(drawings_client, synthetic_drawing):
    api_client, configured = drawings_client

    class FailingParser:
        def parse(self, *_args, **_kwargs):
            raise RuntimeError("processing unavailable")

    app.dependency_overrides[get_drawing_parser] = FailingParser
    with synthetic_drawing.open("rb") as stream:
        response = api_client.post(
            "/api/drawings/upload",
            files={"file": (synthetic_drawing.name, stream, "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unable to process this PDF."
    assert not any(path.is_dir() for path in configured.storage_dir.iterdir())
