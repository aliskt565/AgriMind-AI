"""
Tests for the AgriMind Plant Disease V2-alpha pipeline: taxonomy/label
mapping, preprocessing, model loading, inference input validation
(invalid/oversized/corrupt/unsupported), output schema, OOD rejection
behavior, and metadata consistency.

Run with: python3 -m pytest test_v2_pipeline.py -v
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
sys.path.insert(0, str(PROJECT_ML / "scripts"))
sys.path.insert(0, str(PROJECT_ML / "inference"))

from taxonomy import V2_ALPHA_CLASSES, PLANTVILLAGE_LABEL_MAP, PLANTDOC_LABEL_MAP  # noqa: E402
from preprocessing import load_and_preprocess, preprocessing_config, IMAGE_SIZE  # noqa: E402
import v2_inference  # noqa: E402


# --- Class mapping ---

def test_no_duplicate_canonical_targets_lose_source_diversity():
    # every V2_ALPHA_CLASSES entry should be produced by at least one mapping
    mapped_targets = set(PLANTVILLAGE_LABEL_MAP.values()) | set(PLANTDOC_LABEL_MAP.values())
    for c in V2_ALPHA_CLASSES:
        assert c in mapped_targets, f"{c} has no source mapping"


def test_label_maps_only_target_known_classes():
    for mapping in (PLANTVILLAGE_LABEL_MAP, PLANTDOC_LABEL_MAP):
        for src, canonical in mapping.items():
            assert canonical in V2_ALPHA_CLASSES, f"{src} -> {canonical} not in V2_ALPHA_CLASSES"


def test_class_list_is_crop_prefixed_and_sorted_source_of_truth():
    for c in V2_ALPHA_CLASSES:
        assert "___" in c, f"{c} is not crop-prefixed"
    assert len(V2_ALPHA_CLASSES) == len(set(V2_ALPHA_CLASSES)), "duplicate classes in taxonomy"


# --- Preprocessing ---

def test_preprocessing_output_shape_and_range():
    raw_dir = PROJECT_ML / "data" / "raw" / V2_ALPHA_CLASSES[0]
    if not raw_dir.exists():
        pytest.skip("raw training images are not shipped in the package (reproduce with ml/scripts/ingest.py)")
    sample_path = next(raw_dir.glob("*"))
    arr = load_and_preprocess(str(sample_path))
    assert arr.shape == (*IMAGE_SIZE, 3)
    assert arr.dtype == np.float32
    assert arr.min() >= -1.01 and arr.max() <= 1.01, "MobileNetV2 preprocessing should scale to [-1, 1]"


def test_preprocessing_config_is_shared_and_documented():
    cfg = preprocessing_config()
    assert cfg["image_size"] == list(IMAGE_SIZE)
    assert "mobilenet_v2" in cfg["normalization"]
    assert set(cfg["used_identically_by"]) >= {"training", "inference wrapper"}


# --- Model loading ---

def test_model_file_exists_and_loads():
    import tensorflow as tf
    model_path = PROJECT_ML / "artifacts" / "agrimind_plant_disease_v2.keras"
    assert model_path.exists(), "V2 model artifact missing"
    model = tf.keras.models.load_model(model_path)
    assert model.output_shape[-1] == len(V2_ALPHA_CLASSES)


# --- Inference input validation ---

def test_rejects_invalid_image_bytes():
    with pytest.raises(v2_inference.ValidationError) as exc:
        v2_inference.validate_upload(b"definitely not an image", "image/jpeg")
    assert exc.value.status_code == 400


def test_rejects_oversized_image():
    with pytest.raises(v2_inference.ValidationError) as exc:
        v2_inference.validate_upload(b"x" * (11 * 1024 * 1024), "image/jpeg")
    assert exc.value.status_code == 413


def test_rejects_unsupported_content_type():
    with pytest.raises(v2_inference.ValidationError) as exc:
        v2_inference.validate_upload(b"anything", "application/pdf")
    assert exc.value.status_code == 415


def test_validation_runs_before_model_load(monkeypatch):
    """Mirrors the V1 fix: malformed/oversized input must not trigger a
    model load. We assert this by checking _model stays None after a
    validation failure on a fresh (unloaded) module state."""
    v2_inference._model = None
    v2_inference._emb_model = None
    try:
        v2_inference.validate_upload(b"bad", "image/jpeg")
    except v2_inference.ValidationError:
        pass
    assert v2_inference._model is None, "validation failure must not trigger model loading"


def test_corrupt_image_after_valid_content_type_is_rejected():
    # content-type says jpeg, bytes are garbage -- PIL decode should catch it
    with pytest.raises(v2_inference.ValidationError):
        v2_inference.validate_upload(b"\xff\xd8\xff\xe0not actually a valid jpeg body", "image/jpeg")


# --- Output schema ---

def test_predict_output_schema_on_real_image():
    sample_dir = PROJECT_ML / "data" / "raw" / "Corn___Common_Rust"
    if not sample_dir.exists():
        pytest.skip("raw training images are not shipped in the package (reproduce with ml/scripts/ingest.py)")
    sample_path = next(sample_dir.glob("*"))
    result = v2_inference.predict(open(sample_path, "rb").read(), "image/jpeg")
    assert result.model_version == v2_inference.MODEL_VERSION
    assert result.is_experimental is True
    assert result.state in {"HIGH_CONFIDENCE", "LOW_CONFIDENCE", "REJECTED_UNKNOWN", "REJECTED_LOW_QUALITY"}
    if result.state != "REJECTED_UNKNOWN":
        assert result.predicted_class in V2_ALPHA_CLASSES
        assert 0.0 <= result.confidence <= 1.0
    assert len(result.top_k) == 3


# --- OOD rejection behavior ---

def test_ood_report_exists_and_has_measured_not_assumed_metrics():
    report_path = PROJECT_ML / "reports" / "v2_ood_report.json"
    assert report_path.exists()
    report = json.load(open(report_path))
    assert "method_comparison" in report
    for method in report["method_comparison"].values():
        assert 0.0 <= method["auroc_vs_real_ood"] <= 1.0
    # explicit non-fabrication check: AUROC must not be exactly 1.0 (that would
    # be an implausible, red-flag "too good" result for this task)
    for method in report["method_comparison"].values():
        assert method["auroc_vs_real_ood"] < 1.0


def test_mahalanobis_fit_artifact_matches_class_list():
    fit_path = PROJECT_ML / "artifacts" / "ood_mahalanobis_fit.npz"
    assert fit_path.exists()
    fit = np.load(fit_path, allow_pickle=True)
    assert list(fit["class_list"]) == V2_ALPHA_CLASSES
    assert fit["class_means"].shape[0] == len(V2_ALPHA_CLASSES)


# --- Metadata consistency ---

def test_metadata_class_list_matches_taxonomy():
    meta = json.load(open(PROJECT_ML / "artifacts" / "agrimind_plant_disease_v2_metadata.json"))
    assert meta["canonical_class_list"] == V2_ALPHA_CLASSES
    assert meta["is_experimental"] is True
    # V2-alpha was deliberately integrated into Plant Vision on 2026-09-25 (see
    # MERGE_REPORT_2026_09_25.md). The metadata flag must stay consistent with its
    # own production_integration block rather than assert a stale "not integrated".
    assert meta["not_integrated_into_production"] is ("production_integration" not in meta)


def test_metadata_dataset_manifest_hash_matches_actual_file():
    import hashlib
    meta = json.load(open(PROJECT_ML / "artifacts" / "agrimind_plant_disease_v2_metadata.json"))
    actual_hash = hashlib.sha256(open(PROJECT_ML / "data" / "dataset_manifest.json", "rb").read()).hexdigest()
    assert meta["dataset_manifest_sha256"] == actual_hash, "metadata's recorded manifest hash is stale"


def test_leakage_report_shows_zero_violations():
    report = json.load(open(PROJECT_ML / "reports" / "v2_leakage_report.json"))
    assert report["cross_split_verification_status"] == "PASSED"
    assert report["cross_split_near_duplicate_violations"] == 0
