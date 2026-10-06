"""
Production Plant Vision service backed by the V3 field-robust MobileNetV2 model (ml/experiments/field_robust_v3, model B).

V2 replaces the legacy V1 model at the existing production model path while
keeping the existing API/DB contract and Quick Scan feature.

The V2 model currently covers Corn + Potato (7 classes). Rice, Wheat and
Sugarcane remain intentionally unsupported by Plant Vision until V2 is
expanded and re-evaluated for those crops.

OOD rejection uses the thresholds calibrated on the V2 validation split and
persisted in ml/reports/v2_ood_report.json. This is a safety/rejection
mechanism, not a guarantee of real-world disease diagnosis.
"""
from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("agrimind.cnn")

# Project root: <project>/apps/api/app/services/plant_vision_cnn.py
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ML_DIR = PROJECT_ROOT / "ml"
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "agrimind_plant_disease_model.keras"
V2_ARTIFACT_MODEL_PATH = ML_DIR / "artifacts" / "agrimind_plant_disease_v2.keras"
V2_METADATA_PATH = ML_DIR / "artifacts" / "agrimind_plant_disease_v2_metadata.json"
OOD_REPORT_PATH = ML_DIR / "reports" / "v2_ood_report.json"
MAHALANOBIS_FIT_PATH = ML_DIR / "artifacts" / "ood_mahalanobis_fit.npz"

MODEL_VERSION = "agrimind_plant_disease_v3-field-research"
MODEL_NAME = "AgriMind MobileNetV2 CNN V2"

CLASS_NAMES: list[str] = [
    "Corn___Common_Rust",
    "Corn___Gray_Leaf_Spot",
    "Corn___Healthy",
    "Corn___Northern_Leaf_Blight",
    "Potato___Early_Blight",
    "Potato___Healthy",
    "Potato___Late_Blight",
]

HEALTHY_CLASSES: frozenset[str] = frozenset(
    c for c in CLASS_NAMES if "healthy" in c.lower()
)

SUPPORTED_CROP_TYPES: list[str] = ["Corn", "Potato"]

CROP_FAMILY_CLASSES: dict[str, frozenset[str]] = {
    "Corn": frozenset(
        {
            "Corn___Common_Rust",
            "Corn___Gray_Leaf_Spot",
            "Corn___Healthy",
            "Corn___Northern_Leaf_Blight",
        }
    ),
    "Potato": frozenset(
        {
            "Potato___Early_Blight",
            "Potato___Healthy",
            "Potato___Late_Blight",
        }
    ),
}

# These values are calibrated from the V2 validation split and recorded in
# ml/reports/v2_ood_report.json. They are not invented at runtime.
DEFAULT_CONFIDENCE_THRESHOLD = 0.4271
DEFAULT_MAHALANOBIS_THRESHOLD = 183.81
LOW_CONFIDENCE_THRESHOLD = 0.80


class CNNScanStatus(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
    UNSUPPORTED_CROP = "unsupported_crop"
    ERROR = "error"


@dataclass
class CNNScanResult:
    status: CNNScanStatus
    message: str
    predicted_class: str | None = None
    confidence_percent: float = 0.0
    is_disease: bool = False
    crop_mismatch: bool = False
    mismatch_detail: str | None = None
    rejection_reason: str | None = None
    ood_state: str | None = None
    mahalanobis_distance: float | None = None
    top_k: list[dict] | None = None


_model = None
_embedding_model = None
_maha_fit: tuple[np.ndarray, np.ndarray] | None = None
_thresholds: dict | None = None
_model_load_failed = False


def is_model_loaded() -> bool:
    return _model is not None


def _load_thresholds() -> dict:
    if OOD_REPORT_PATH.exists():
        try:
            payload = json.loads(OOD_REPORT_PATH.read_text(encoding="utf-8"))
            return payload["threshold_calibration"]
        except Exception:
            logger.exception("Failed to read V2 OOD calibration; using persisted defaults.")
    return {
        "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
        "mahalanobis_threshold": DEFAULT_MAHALANOBIS_THRESHOLD,
    }


def _load_mahalanobis_fit():
    if not MAHALANOBIS_FIT_PATH.exists():
        return None
    try:
        fit = np.load(MAHALANOBIS_FIT_PATH)
        return fit["class_means"], fit["inv_cov"]
    except Exception:
        logger.exception("Failed to load V2 Mahalanobis fit.")
        return None


def get_model():
    """Lazy-load V2 model + embedding/OOD artifacts exactly once."""
    global _model, _embedding_model, _maha_fit, _thresholds, _model_load_failed

    if _model is not None:
        return _model
    if _model_load_failed:
        return None

    try:
        import tensorflow as tf

        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"V2 production model missing: {MODEL_PATH}")

        _model = tf.keras.models.load_model(MODEL_PATH)

        output_units = int(_model.output_shape[-1])
        if output_units != len(CLASS_NAMES):
            raise RuntimeError(
                f"V2 model output has {output_units} classes but production taxonomy has "
                f"{len(CLASS_NAMES)} classes."
            )

        dense128 = next(
            layer
            for layer in _model.layers
            if isinstance(layer, tf.keras.layers.Dense) and layer.units == 128
        )
        _embedding_model = tf.keras.Model(inputs=_model.input, outputs=dense128.output)
        _thresholds = _load_thresholds()
        _maha_fit = _load_mahalanobis_fit()

        logger.info(
            "Loaded %s (%s), classes=%d, OOD=%s",
            MODEL_NAME,
            MODEL_VERSION,
            len(CLASS_NAMES),
            "enabled" if _maha_fit is not None else "confidence-only",
        )
    except Exception as exc:
        logger.error("Failed to load V2 CNN model: %s", exc, exc_info=True)
        _model = None
        _embedding_model = None
        _model_load_failed = True

    return _model


def reset_model_cache() -> None:
    """Test helper: clear the lazy-loaded model/artifact cache."""
    global _model, _embedding_model, _maha_fit, _thresholds, _model_load_failed
    _model = None
    _embedding_model = None
    _maha_fit = None
    _thresholds = None
    _model_load_failed = False


def is_crop_mismatch(predicted_class: str, selected_crop: str) -> bool:
    valid = CROP_FAMILY_CLASSES.get(selected_crop)
    if valid is None:
        return True
    return predicted_class not in valid


def _mahalanobis_distance(embedding: np.ndarray) -> float | None:
    if _maha_fit is None:
        return None
    class_means, inv_cov = _maha_fit
    distances = [
        float((embedding - mean) @ inv_cov @ (embedding - mean).T)
        for mean in class_means
    ]
    return min(distances)


def _validate_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return image
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("File appears to be corrupt or is not a valid image.") from exc


def _preprocess(image: Image.Image) -> np.ndarray:
    import tensorflow as tf

    resized = image.resize((224, 224), Image.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32)
    return tf.keras.applications.mobilenet_v2.preprocess_input(arr)


def scan_image_bytes(
    image_bytes: bytes,
    crop_context: str | None = None,
) -> CNNScanResult:
    """
    Run V2 inference.

    Validation happens before model loading. V2 preprocessing matches the
    training/evaluation pipeline exactly. The combined OOD rule is
    confidence OR Mahalanobis distance.
    """
    if crop_context is not None and crop_context not in SUPPORTED_CROP_TYPES:
        return CNNScanResult(
            status=CNNScanStatus.UNSUPPORTED_CROP,
            message=(
                f"Plant Vision V2 currently supports only {', '.join(SUPPORTED_CROP_TYPES)}. "
                f"{crop_context} is not yet covered by the trained V2 taxonomy."
            ),
            rejection_reason="Crop is outside the currently trained V2 taxonomy.",
        )

    try:
        image = _validate_image(image_bytes)
    except ValueError as exc:
        return CNNScanResult(
            status=CNNScanStatus.REJECTED,
            message=str(exc),
            rejection_reason=str(exc),
        )

    model = get_model()
    if model is None or _embedding_model is None:
        return CNNScanResult(
            status=CNNScanStatus.ERROR,
            message="V2 CNN model is not available on this server.",
        )

    try:
        batch = np.expand_dims(_preprocess(image), axis=0)
        probabilities = _model.predict(batch, verbose=0)[0]
        embedding = _embedding_model.predict(batch, verbose=0)[0]

        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx])
        predicted_class = CLASS_NAMES[predicted_idx]

        top_indices = np.argsort(probabilities)[::-1][:3]
        top_k = [
            {
                "class": CLASS_NAMES[int(i)],
                "confidence": round(float(probabilities[int(i)]), 4),
            }
            for i in top_indices
        ]

        thresholds = _thresholds or {}
        confidence_threshold = float(
            thresholds.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        )
        mahalanobis_threshold = float(
            thresholds.get("mahalanobis_threshold", DEFAULT_MAHALANOBIS_THRESHOLD)
        )

        maha_distance = _mahalanobis_distance(embedding)
        rejected_by_confidence = confidence < confidence_threshold
        rejected_by_embedding = (
            maha_distance is not None and maha_distance > mahalanobis_threshold
        )

        if rejected_by_confidence or rejected_by_embedding:
            reasons = []
            if rejected_by_confidence:
                reasons.append("confidence below the calibrated threshold")
            if rejected_by_embedding:
                reasons.append("image is outside the calibrated embedding distribution")
            reason = " and ".join(reasons)

            return CNNScanResult(
                status=CNNScanStatus.REJECTED,
                message=(
                    "The V2 model could not confidently recognize this image as one "
                    "of its supported crop-disease classes."
                ),
                predicted_class=None,
                confidence_percent=round(confidence * 100, 2),
                is_disease=False,
                rejection_reason=reason,
                ood_state="REJECTED_UNKNOWN",
                mahalanobis_distance=maha_distance,
                top_k=top_k,
            )

        state = "LOW_CONFIDENCE" if confidence < LOW_CONFIDENCE_THRESHOLD else "HIGH_CONFIDENCE"
        crop_mismatch = False
        mismatch_detail = None

        if crop_context is not None and is_crop_mismatch(predicted_class, crop_context):
            crop_mismatch = True
            detected_family = predicted_class.split("___")[0]
            mismatch_detail = (
                f"You selected '{crop_context}', but V2 detected a '{detected_family}' "
                "pattern. Upload a clear photo of the selected crop."
            )

        is_disease = predicted_class not in HEALTHY_CLASSES

        return CNNScanResult(
            status=CNNScanStatus.SUCCESS,
            message=(
                "Analysis complete."
                if not crop_mismatch
                else "Crop family mismatch detected."
            ),
            predicted_class=predicted_class,
            confidence_percent=round(confidence * 100, 2),
            is_disease=is_disease,
            crop_mismatch=crop_mismatch,
            mismatch_detail=mismatch_detail,
            ood_state=state,
            mahalanobis_distance=maha_distance,
            top_k=top_k,
        )

    except Exception as exc:
        logger.error("V2 CNN inference failed: %s", exc, exc_info=True)
        return CNNScanResult(
            status=CNNScanStatus.ERROR,
            message="Inference failed unexpectedly. Please try again.",
        )
