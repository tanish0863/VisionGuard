"""API contract tests. Model inference is stubbed so tests need no YOLO weights."""
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

import main


client = TestClient(main.app)


def png_bytes():
    buffer = BytesIO()
    Image.new("RGB", (32, 24), color=(120, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_endpoint_returns_expected_fields():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "weights" in body
    assert body["corruptions"] == [
        "blur", "brightness", "noise", "rotation", "jpeg", "occlusion"
    ]


def test_unknown_corruption_is_rejected():
    response = client.post(
        "/api/analyze",
        files={"file": ("sample.png", png_bytes(), "image/png")},
        data={"corruption": "not-a-corruption"},
    )

    assert response.status_code == 400
    assert "corruption must be one of" in response.json()["detail"]


def test_invalid_image_is_rejected():
    response = client.post(
        "/api/analyze",
        files={"file": ("broken.png", b"this is not an image", "image/png")},
        data={"corruption": "blur"},
    )

    assert response.status_code == 400
    assert "valid image" in response.json()["detail"]


def test_non_numeric_severity_is_rejected():
    response = client.post(
        "/api/analyze",
        files={"file": ("sample.png", png_bytes(), "image/png")},
        data={"corruption": "blur", "levels": "0,not-a-number,1"},
    )

    assert response.status_code == 400
    assert "numeric severity levels" in response.json()["detail"]


def test_missing_run_returns_404():
    response = client.get("/api/runs/run-that-does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_analysis_is_saved_and_report_is_exportable(monkeypatch):
    # Keep the test deterministic and avoid downloading/loading model weights.
    monkeypatch.setattr(main, "detect", lambda image: ([], 1.0))

    response = client.post(
        "/api/analyze",
        files={"file": ("sample.png", png_bytes(), "image/png")},
        data={"corruption": "blur", "levels": "0,0.5", "iou": "0.5", "seed": "42"},
    )

    assert response.status_code == 200
    run = response.json()
    assert run["id"]
    assert run["config"]["corruption"] == "blur"
    assert [level["severity"] for level in run["levels"]] == [0.0, 0.5]

    saved = client.get(f"/api/runs/{run['id']}")
    assert saved.status_code == 200
    assert saved.json()["id"] == run["id"]

    report = client.get(f"/api/runs/{run['id']}/report")
    assert report.status_code == 200
    assert report.text.startswith(f"# VisionGuard report {run['id']}")
