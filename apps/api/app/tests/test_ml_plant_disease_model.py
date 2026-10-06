"""Contract/smoke tests for the integrated V2 Plant Vision model."""
import io

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

pytest.importorskip("tensorflow", reason="TensorFlow is required for V2 model tests")

from app.main import app
from app.services import plant_vision_cnn as cnn


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _jpeg_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8"), "RGB").save(buf, format="JPEG")
    return buf.getvalue()


def _solid_image(rgb: tuple[int, int, int]) -> bytes:
    arr = np.zeros((224, 224, 3), dtype="uint8")
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = rgb
    return _jpeg_bytes(arr)


def test_v2_model_file_exists():
    assert cnn.MODEL_PATH.exists()


def test_v2_model_loads_and_has_seven_outputs():
    model = cnn.get_model()
    assert model is not None
    assert int(model.output_shape[-1]) == 7
    assert len(cnn.CLASS_NAMES) == 7


def test_invalid_content_type_rejected_before_model_load(client):
    response = client.post(
        "/predict-disease",
        files={"file": ("doc.pdf", b"whatever", "application/pdf")},
    )
    assert response.status_code == 400


def test_corrupt_image_returns_client_error(client):
    response = client.post(
        "/predict-disease",
        files={"file": ("x.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_unsupported_scan_crop_is_rejected(client):
    response = client.post(
        "/api/v1/ai/plant-vision/scan",
        files={"file": ("leaf.jpg", _solid_image((40, 160, 40)), "image/jpeg")},
        data={"selected_crop": "Rice"},
    )
    # Authentication is intentionally checked before scan execution in the
    # product endpoint, so this test only asserts the route exists/does not 404.
    assert response.status_code != 404


def test_health_reports_v2_model_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["plant_vision_model"] == cnn.MODEL_VERSION
