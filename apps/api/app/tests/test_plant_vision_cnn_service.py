"""Unit tests for the production V2 Plant Vision service."""
import io

import numpy as np
from PIL import Image

from app.services import plant_vision_cnn as cnn


def _image() -> bytes:
    image = Image.new("RGB", (32, 32), (45, 170, 70))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class _FakeModel:
    def __init__(self, probabilities):
        self.probabilities = np.asarray([probabilities], dtype=np.float32)

    def predict(self, x, verbose=0):
        return self.probabilities


def _setup(monkeypatch, probabilities):
    model = _FakeModel(probabilities)
    embedding_model = _FakeModel(np.zeros(128, dtype=np.float32))
    monkeypatch.setattr(cnn, "_model", model)
    monkeypatch.setattr(cnn, "_embedding_model", embedding_model)
    monkeypatch.setattr(cnn, "_model_load_failed", False)
    monkeypatch.setattr(
        cnn,
        "_thresholds",
        {"confidence_threshold": 0.6335, "mahalanobis_threshold": 164.42},
    )
    monkeypatch.setattr(cnn, "_maha_fit", None)
    monkeypatch.setattr(cnn, "_preprocess", lambda image: np.zeros((224, 224, 3), dtype=np.float32))


def _probs(class_name: str, confidence: float) -> np.ndarray:
    values = np.full(len(cnn.CLASS_NAMES), (1.0 - confidence) / (len(cnn.CLASS_NAMES) - 1), dtype=np.float32)
    values[cnn.CLASS_NAMES.index(class_name)] = confidence
    return values


def test_v2_healthy_prediction_is_healthy(monkeypatch):
    _setup(monkeypatch, _probs("Corn___Healthy", 0.94))
    result = cnn.scan_image_bytes(_image(), crop_context="Corn")

    assert result.status == cnn.CNNScanStatus.SUCCESS
    assert result.predicted_class == "Corn___Healthy"
    assert result.is_disease is False
    assert result.crop_mismatch is False
    assert result.confidence_percent == 94.0


def test_v2_disease_prediction_for_matching_crop(monkeypatch):
    _setup(monkeypatch, _probs("Potato___Late_Blight", 0.91))
    result = cnn.scan_image_bytes(_image(), crop_context="Potato")

    assert result.status == cnn.CNNScanStatus.SUCCESS
    assert result.predicted_class == "Potato___Late_Blight"
    assert result.is_disease is True
    assert result.crop_mismatch is False


def test_v2_crop_mismatch_is_flagged(monkeypatch):
    _setup(monkeypatch, _probs("Corn___Common_Rust", 0.90))
    result = cnn.scan_image_bytes(_image(), crop_context="Potato")

    assert result.status == cnn.CNNScanStatus.SUCCESS
    assert result.crop_mismatch is True
    assert "selected 'Potato'" in (result.mismatch_detail or "")


def test_v2_low_confidence_is_rejected(monkeypatch):
    _setup(monkeypatch, _probs("Corn___Common_Rust", 0.60))
    result = cnn.scan_image_bytes(_image(), crop_context="Corn")

    assert result.status == cnn.CNNScanStatus.REJECTED
    assert result.predicted_class is None
    assert result.ood_state == "REJECTED_UNKNOWN"


def test_v2_unsupported_crop_is_rejected_before_model_inference(monkeypatch):
    _setup(monkeypatch, _probs("Corn___Common_Rust", 0.99))
    result = cnn.scan_image_bytes(_image(), crop_context="Rice")

    assert result.status == cnn.CNNScanStatus.UNSUPPORTED_CROP
    assert result.predicted_class is None
    assert "Corn" in result.message and "Potato" in result.message


def test_invalid_image_does_not_load_model(monkeypatch):
    cnn.reset_model_cache()
    called = {"value": False}

    def fail_if_called():
        called["value"] = True
        raise AssertionError("model should not load for invalid input")

    monkeypatch.setattr(cnn, "get_model", fail_if_called)
    result = cnn.scan_image_bytes(b"not-an-image", crop_context="Corn")

    assert result.status == cnn.CNNScanStatus.REJECTED
    assert called["value"] is False
