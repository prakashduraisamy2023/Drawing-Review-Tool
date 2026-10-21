from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app, get_api_settings

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def test_all_samples_complete_upload_retrieval_and_export_pathway(tmp_path: Path):
    settings = Settings(storage_dir=tmp_path, max_upload_bytes=20 * 1024 * 1024)
    app.dependency_overrides[get_api_settings] = lambda: settings
    expected = {
        "47789413_C_watermarked.pdf": (5, "47789413", 0),
        "47789460_B_watermarked.pdf": (1, "47789460", 1),
        "47789660_A_watermarked.pdf": (1, "47789660", 1),
    }
    try:
        with TestClient(app) as client:
            for filename, (pages, drawing_number, raster_regions) in expected.items():
                with (SAMPLES / filename).open("rb") as stream:
                    response = client.post(
                        "/api/drawings/upload",
                        files={"file": (filename, stream, "application/pdf")},
                    )
                assert response.status_code == 201
                payload = response.json()
                drawing_id = payload["id"]
                drawing = payload["drawing"]
                assert drawing["page_count"]["value"] == pages
                assert drawing["drawing_number"]["value"] == drawing_number
                assert len(drawing["supplier_raster_regions"]) == raster_regions
                assert drawing["level1_summary"]["processing_state"] == "SUCCESS"
                assert client.get(f"/api/drawings/{drawing_id}").status_code == 200
                assert client.get(f"/api/drawings/{drawing_id}/export/json").status_code == 200
                assert client.get(f"/api/drawings/{drawing_id}/export/csv").status_code == 200
    finally:
        app.dependency_overrides.clear()
