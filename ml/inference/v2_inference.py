"""
V2 Plant Disease inference wrapper.

This is the canonical V2 inference implementation used by the production
adapter in apps/api/app/services/plant_vision_cnn.py. It uses the SAME shared
preprocessing as training/evaluation and the measured OOD thresholds stored
in reports/v2_ood_report.json.

V2 remains an alpha model with documented real-world/OOD limitations. The
fact that it is integrated into the local AgriMind product does not mean it
has been commercially or field-validated.
"""
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, UnidentifiedImageError

MODULE_DIR = Path(__file__).parent
SCRIPTS_DIR = MODULE_DIR.parent / "scripts"
import sys
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from taxonomy import V2_ALPHA_CLASSES  # noqa: E402
from preprocessing import load_and_preprocess, IMAGE_SIZE  # noqa: E402

MODEL_PATH = MODULE_DIR.parent / "artifacts" / "agrimind_plant_disease_v2.keras"
METADATA_PATH = MODULE_DIR.parent / "artifacts" / "agrimind_plant_disease_v2_metadata.json"

MAX_UPLOAD_SIZE_MB = 10
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}

MODEL_VERSION = "agrimind_plant_disease_v3-field-research"


class ValidationError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class InferenceResult:
    predicted_class: Optional[str]
    confidence: Optional[float]
    state: str  # "HIGH_CONFIDENCE" | "LOW_CONFIDENCE" | "REJECTED_UNKNOWN" | "REJECTED_LOW_QUALITY"
    model_version: str = MODEL_VERSION
    is_experimental: bool = True
    top_k: list = field(default_factory=list)


_model = None
_emb_model = None
_thresholds = None
_maha_fit = None  # (class_means, inv_cov) loaded from artifacts/ood_mahalanobis_fit.npz

MAHALANOBIS_FIT_PATH = MODULE_DIR.parent / "artifacts" / "ood_mahalanobis_fit.npz"


def _lazy_load():
    """Load the model (and OOD thresholds/Mahalanobis fit) only on first real
    inference call, AFTER input validation has already happened -- validation
    must never trigger a model load, mirroring V1's fixed ordering bug."""
    global _model, _emb_model, _thresholds, _maha_fit
    if _model is not None:
        return
    import tensorflow as tf
    _model = tf.keras.models.load_model(MODEL_PATH)
    dense128 = next(l for l in _model.layers if isinstance(l, tf.keras.layers.Dense) and l.units == 128)
    _emb_model = tf.keras.Model(inputs=_model.input, outputs=dense128.output)
    ood_report_path = MODULE_DIR.parent / "reports" / "v2_ood_report.json"
    if ood_report_path.exists():
        ood = json.load(open(ood_report_path))
        _thresholds = ood["threshold_calibration"]
    else:
        _thresholds = {"confidence_threshold": 0.5, "mahalanobis_threshold": float("inf")}
    if MAHALANOBIS_FIT_PATH.exists():
        fit = np.load(MAHALANOBIS_FIT_PATH)
        _maha_fit = (fit["class_means"], fit["inv_cov"])
    else:
        _maha_fit = None


def _mahalanobis_distance(embedding: np.ndarray) -> Optional[float]:
    if _maha_fit is None:
        return None
    class_means, inv_cov = _maha_fit
    dists = [float((embedding - mu) @ inv_cov @ (embedding - mu).T) for mu in class_means]
    return min(dists)


def validate_upload(image_bytes: bytes, content_type: str) -> None:
    """Runs BEFORE any model loading. Raises ValidationError on failure."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content type: {content_type}", 415)
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise ValidationError(f"Image exceeds {MAX_UPLOAD_SIZE_MB}MB limit", 413)
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im.verify()
    except (UnidentifiedImageError, Exception) as e:
        raise ValidationError(f"Could not decode image: {e}", 400)


def predict(image_bytes: bytes, content_type: str) -> InferenceResult:
    # 1. Validate BEFORE loading the model.
    validate_upload(image_bytes, content_type)

    # 2. Load model lazily (cached after first call).
    _lazy_load()

    # 3. Shared preprocessing (identical function used in training/eval).
    img = load_and_preprocess(image_bytes, is_bytes=True)
    batch = np.expand_dims(img, axis=0)

    # 4. Inference + embedding for OOD scoring.
    probs = _model.predict(batch, verbose=0)[0]
    emb = _emb_model.predict(batch, verbose=0)[0]

    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])
    predicted_class = V2_ALPHA_CLASSES[pred_idx]

    top_k_idx = np.argsort(probs)[::-1][:3]
    top_k = [{"class": V2_ALPHA_CLASSES[i], "confidence": round(float(probs[i]), 4)} for i in top_k_idx]

    conf_thresh = _thresholds["confidence_threshold"]
    maha_thresh = _thresholds["mahalanobis_threshold"]
    maha_dist = _mahalanobis_distance(emb)

    # Combined OR rule, as measured and recorded in reports/v2_ood_report.json
    # (docs/ml_v2_ood_report.md documents why this rule -- not either signal
    # alone -- was selected, and its real, non-perfect measured performance).
    flagged_by_confidence = confidence < conf_thresh
    flagged_by_embedding = (maha_dist is not None) and (maha_dist > maha_thresh)

    if flagged_by_confidence or flagged_by_embedding:
        state = "REJECTED_UNKNOWN"
    elif confidence < 0.80:
        state = "LOW_CONFIDENCE"
    else:
        state = "HIGH_CONFIDENCE"

    return InferenceResult(
        predicted_class=predicted_class if state != "REJECTED_UNKNOWN" else None,
        confidence=round(confidence, 4),
        state=state,
        top_k=top_k,
    )
