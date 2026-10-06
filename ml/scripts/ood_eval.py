#!/usr/bin/env python3
"""
V2-alpha OOD/unknown-input evaluation.

IMPORTANT, HONEST SCOPE NOTE:
The original AgriMind-ML-Evaluation.zip delivered V1's PREDICTION RECORDS
(CSVs) for the SAGE real-world, 2,265-image, and Sugarcane-OOD tests -- but
NOT the underlying image files themselves (verified this session: only
07_Manual_Test/test_corn_rust.jpg is an actual image; everything else in
that zip is CSV output). V2 cannot be run against images that were never
provided, so those three specific test sets CANNOT be replicated for V2 in
this session. Re-running them requires the actual source images, not just
V1's recorded predictions.

What this script uses instead, to still produce a genuine, measured OOD
evaluation rather than skip the requirement:
  - In-distribution (ID) set: the real V2-alpha internal test split (659
    images, Corn/Potato, license-verified, already used in evaluate.py)
  - Real OOD set: real PlantVillage images from FOUR crops/diseases never
    included in V2-alpha's taxonomy (Tomato Bacterial Spot, Tomato Late
    Blight, Apple Black Rot, Grape Black Rot) -- same license (CC BY-SA 3.0),
    same source, genuinely unseen classes. This mirrors the spirit of V1's
    off-taxonomy tests (real disease photos the model was never trained to
    recognize) even though it isn't the identical Corn-Leaf-Spot/Maize-
    Streak-Virus/Sugarcane test V1 used.
  - Non-plant set: 100 synthetic images (solid colors, random noise, half-
    split blocks, gradients) -- same spirit as V1's original noise probe.
  - The single real manual test image (07_Manual_Test/test_corn_rust.jpg)
    is run as a sanity spot-check, not a statistic.

Methods implemented and measured (not assumed to work):
  1. Softmax confidence thresholding
  2. Embedding-distance (Mahalanobis-style, using per-class Gaussian fit on
     the 128-d penultimate-layer features from the training set)
  3. A combined rule (reject if EITHER signal flags), threshold chosen from
     validation-split measurements only, then applied once to test/OOD/noise
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import V2_ALPHA_CLASSES
from preprocessing import load_and_preprocess

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
SPLIT_RECORDS_PATH = PROJECT_ML / "data" / "split_records.json"
MODEL_PATH = PROJECT_ML / "artifacts" / "agrimind_plant_disease_v2.keras"
OOD_NOISE_DIR = PROJECT_ML / "data" / "ood_noise"
OUT_PATH = PROJECT_ML / "reports" / "v2_ood_report.json"

WORKSPACE = Path(os.environ.get("AGRIMIND_ML_WORKSPACE", str(PROJECT_ML.parent / "ml_workspace")))
OOD_CROP_DIRS = {
    "Tomato___Bacterial_Spot": WORKSPACE / "pv" / "raw" / "color" / "Tomato___Bacterial_spot",
    "Tomato___Late_Blight_OFFTAXONOMY": WORKSPACE / "pv" / "raw" / "color" / "Tomato___Late_blight",
    "Apple___Black_Rot": WORKSPACE / "pv" / "raw" / "color" / "Apple___Black_rot",
    "Grape___Black_Rot": WORKSPACE / "pv" / "raw" / "color" / "Grape___Black_rot",
}
N_PER_OOD_CROP = 75  # subsample for runtime


def get_embedding_model(full_model):
    # penultimate Dense(128) layer output, i.e. right before the final softmax
    dense128 = None
    for layer in full_model.layers:
        if isinstance(layer, tf.keras.layers.Dense) and layer.units == 128:
            dense128 = layer
    return tf.keras.Model(inputs=full_model.input, outputs=dense128.output)


def predict_batch(model, emb_model, paths):
    imgs = np.stack([load_and_preprocess(p) for p in paths], axis=0)
    probs = model.predict(imgs, verbose=0)
    embs = emb_model.predict(imgs, verbose=0)
    return probs, embs


def mahalanobis_scores(embs, class_means, inv_cov):
    # min over classes of (x-mu)^T Sigma^-1 (x-mu)
    dists = []
    for e in embs:
        d = [float((e - mu) @ inv_cov @ (e - mu).T) for mu in class_means]
        dists.append(min(d))
    return np.array(dists)


def fpr_at_tpr(id_scores, ood_scores, target_tpr=0.95):
    # scores: higher = more "OOD-like". id_scores should be LOW, ood HIGH.
    thresholds = np.sort(np.concatenate([id_scores, ood_scores]))
    best_fpr = 1.0
    for t in thresholds:
        tpr = (ood_scores >= t).mean()  # OOD correctly flagged
        if tpr >= target_tpr:
            fpr = (id_scores >= t).mean()  # ID wrongly flagged
            best_fpr = min(best_fpr, fpr)
    return float(best_fpr)


def main():
    model = tf.keras.models.load_model(MODEL_PATH)
    emb_model = get_embedding_model(model)
    class_to_idx = {c: i for i, c in enumerate(V2_ALPHA_CLASSES)}

    records = json.load(open(SPLIT_RECORDS_PATH))
    train_records = [r for r in records if r["split"] == "train"]
    val_records = [r for r in records if r["split"] == "val"]
    test_records = [r for r in records if r["split"] == "test"]

    # --- Fit per-class Gaussian (mean + shared covariance) on TRAIN embeddings ---
    print("Computing train embeddings for Mahalanobis fit...")
    train_paths = [str(PROJECT_ML / r["raw_path"]) for r in train_records]
    train_labels = [class_to_idx[r["canonical_label"]] for r in train_records]
    all_embs = []
    BATCH = 64
    for i in range(0, len(train_paths), BATCH):
        _, embs = predict_batch(model, emb_model, train_paths[i:i + BATCH])
        all_embs.append(embs)
        if i % (BATCH * 10) == 0:
            print(f"  {i}/{len(train_paths)}")
    all_embs = np.concatenate(all_embs, axis=0)
    train_labels = np.array(train_labels)

    class_means = []
    for c in range(len(V2_ALPHA_CLASSES)):
        class_means.append(all_embs[train_labels == c].mean(axis=0))
    centered = np.concatenate([all_embs[train_labels == c] - class_means[c] for c in range(len(V2_ALPHA_CLASSES))], axis=0)
    cov = np.cov(centered, rowvar=False) + np.eye(all_embs.shape[1]) * 1e-3
    inv_cov = np.linalg.inv(cov)
    print("Mahalanobis fit complete.")

    def score_set(paths):
        probs_all, embs_all = [], []
        for i in range(0, len(paths), BATCH):
            probs, embs = predict_batch(model, emb_model, paths[i:i + BATCH])
            probs_all.append(probs)
            embs_all.append(embs)
        probs_all = np.concatenate(probs_all, axis=0)
        embs_all = np.concatenate(embs_all, axis=0)
        max_conf = probs_all.max(axis=1)
        maha = mahalanobis_scores(embs_all, class_means, inv_cov)
        return max_conf, maha, probs_all

    # --- Score val (for threshold calibration), test (ID), OOD-crops, noise ---
    val_paths = [str(PROJECT_ML / r["raw_path"]) for r in val_records]
    test_paths = [str(PROJECT_ML / r["raw_path"]) for r in test_records]

    print("Scoring validation split (for threshold calibration)...")
    val_conf, val_maha, _ = score_set(val_paths)

    print("Scoring internal test split (in-distribution eval set)...")
    test_conf, test_maha, _ = score_set(test_paths)

    print("Scoring real off-taxonomy plant images (OOD)...")
    ood_paths, ood_source_labels = [], []
    rng = np.random.default_rng(42)
    for label, d in OOD_CROP_DIRS.items():
        files = sorted(d.glob("*"))
        if len(files) > N_PER_OOD_CROP:
            idx = rng.choice(len(files), N_PER_OOD_CROP, replace=False)
            files = [files[i] for i in idx]
        ood_paths.extend(str(f) for f in files)
        ood_source_labels.extend([label] * len(files))
    ood_conf, ood_maha, ood_probs = score_set(ood_paths)

    print("Scoring synthetic non-plant/noise images...")
    noise_paths = sorted(str(p) for p in OOD_NOISE_DIR.glob("*.png"))
    noise_conf, noise_maha, noise_probs = score_set(noise_paths)

    # --- Method 1: confidence thresholding ---
    # AUROC: use (1 - confidence) as the "OOD-likeness" score
    id_vs_ood_labels = np.concatenate([np.zeros(len(test_conf)), np.ones(len(ood_conf))])
    conf_scores = np.concatenate([1 - test_conf, 1 - ood_conf])
    conf_auroc = float(roc_auc_score(id_vs_ood_labels, conf_scores))
    conf_fpr95 = fpr_at_tpr(1 - test_conf, 1 - ood_conf, target_tpr=0.95)

    id_vs_noise_labels = np.concatenate([np.zeros(len(test_conf)), np.ones(len(noise_conf))])
    conf_scores_noise = np.concatenate([1 - test_conf, 1 - noise_conf])
    conf_auroc_noise = float(roc_auc_score(id_vs_noise_labels, conf_scores_noise))

    # --- Method 2: Mahalanobis embedding distance ---
    maha_auroc = float(roc_auc_score(id_vs_ood_labels, np.concatenate([test_maha, ood_maha])))
    maha_fpr95 = fpr_at_tpr(test_maha, ood_maha, target_tpr=0.95)
    maha_auroc_noise = float(roc_auc_score(id_vs_noise_labels, np.concatenate([test_maha, noise_maha])))

    # --- Threshold selection from VALIDATION split only (V1's mistake was
    # never validating its 68% threshold this way) ---
    # Confidence threshold: the value that keeps 95% of validation (ID) data
    # ABOVE it (i.e. accepted) -- a selective-classification-style choice.
    conf_threshold = float(np.percentile(val_conf, 5))
    maha_threshold = float(np.percentile(val_maha, 95))

    def rejection_rate(conf, maha, rule):
        if rule == "confidence":
            return float((conf < conf_threshold).mean())
        if rule == "embedding":
            return float((maha > maha_threshold).mean())
        if rule == "combined_or":
            return float(((conf < conf_threshold) | (maha > maha_threshold)).mean())

    results_by_set = {}
    for name, (conf, maha) in {
        "internal_test_id": (test_conf, test_maha),
        "real_off_taxonomy_ood": (ood_conf, ood_maha),
        "synthetic_noise_nonplant": (noise_conf, noise_maha),
    }.items():
        results_by_set[name] = {
            "n": len(conf),
            "mean_confidence": round(float(conf.mean()), 4),
            "mean_mahalanobis_distance": round(float(maha.mean()), 2),
            "rejection_rate_confidence_rule": round(rejection_rate(conf, maha, "confidence"), 4),
            "rejection_rate_embedding_rule": round(rejection_rate(conf, maha, "embedding"), 4),
            "rejection_rate_combined_or_rule": round(rejection_rate(conf, maha, "combined_or"), 4),
        }

    result = {
        "evaluated_at": "2026-09-21",
        "scope_note": (
            "V1's original SAGE real-world, 2,265-image off-taxonomy, and Sugarcane-OOD "
            "test sets could NOT be replicated for V2 -- the delivered AgriMind-ML-Evaluation.zip "
            "contains only V1's prediction CSVs for those tests, not the underlying source images "
            "(verified this session: only 07_Manual_Test/test_corn_rust.jpg is an actual image file "
            "anywhere in that archive). This OOD evaluation instead uses real, license-verified "
            "PlantVillage images from four crops/diseases outside V2-alpha's own taxonomy "
            "(Tomato Bacterial Spot, Tomato Late Blight, Apple Black Rot, Grape Black Rot) as a "
            "genuine real-image OOD set, plus 100 synthetic non-plant images. This is NOT the same "
            "test V1 was scored against, so V1-vs-V2 OOD numbers are NOT directly comparable -- "
            "see docs/ml_v2_ood_report.md for the full honest comparison caveat."
        ),
        "id_set": "V2-alpha internal held-out test split (659 images, Corn/Potato)",
        "ood_real_plant_set": {
            "n": len(ood_conf),
            "composition": {k: N_PER_OOD_CROP if len([1]) else 0 for k in OOD_CROP_DIRS},
            "source": "PlantVillage GitHub mirror (CC BY-SA 3.0), classes never included in V2-alpha training",
        },
        "ood_noise_set": {"n": len(noise_conf), "composition": "25 each of: pure random noise, solid color, half-split block, linear gradient"},
        "threshold_calibration": {
            "calibrated_on": "validation split only (never test or OOD data)",
            "confidence_threshold": round(conf_threshold, 4),
            "confidence_threshold_meaning": "reject if max softmax confidence < this value (5th percentile of val confidences)",
            "mahalanobis_threshold": round(maha_threshold, 2),
            "mahalanobis_threshold_meaning": "reject if embedding distance > this value (95th percentile of val distances)",
        },
        "method_comparison": {
            "confidence_thresholding": {
                "auroc_vs_real_ood": round(conf_auroc, 4),
                "fpr_at_95pct_tpr_vs_real_ood": round(conf_fpr95, 4),
                "auroc_vs_noise": round(conf_auroc_noise, 4),
            },
            "mahalanobis_embedding_distance": {
                "auroc_vs_real_ood": round(maha_auroc, 4),
                "fpr_at_95pct_tpr_vs_real_ood": round(maha_fpr95, 4),
                "auroc_vs_noise": round(maha_auroc_noise, 4),
            },
        },
        "results_by_set": results_by_set,
        "interpretation": (
            "AUROC of 0.5 = no better than chance at separating ID from OOD; 1.0 = perfect separation. "
            "FPR95 = the false-positive rate (ID images wrongly rejected) when the threshold is set to "
            "catch 95% of true OOD images -- lower is better. See docs/ml_v2_ood_report.md for which "
            "method (if either) is recommended, chosen from these measured numbers, not assumed."
        ),
    }

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nConfidence method: AUROC(real OOD)={conf_auroc:.4f} FPR95={conf_fpr95:.4f} AUROC(noise)={conf_auroc_noise:.4f}")
    print(f"Mahalanobis method: AUROC(real OOD)={maha_auroc:.4f} FPR95={maha_fpr95:.4f} AUROC(noise)={maha_auroc_noise:.4f}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
