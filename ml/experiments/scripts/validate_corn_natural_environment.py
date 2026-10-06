#!/usr/bin/env python3
"""
Large-scale real-world Corn validation (MEASUREMENT ONLY -- these images are
NOT used for training, per the explicit decision to avoid training a
commercial production model on an unlicensed source).

Source: gitergo/Datasets (GitHub), Natural_environment/ folder, 3,380 real
field-condition Corn images (Qingdao, China), matching this project's 4 Corn
classes exactly. No LICENSE file exists in that repo (confirmed 404 on both
branches) -- used here strictly to MEASURE real-world accuracy with a much
larger, statistically meaningful sample than the 63-image PlantDoc subset
allowed, not to train or fine-tune any model.

To re-run: clone the dataset first --
  git clone --filter=blob:none --sparse --depth 1 https://github.com/gitergo/Datasets.git /tmp/gitergo
  cd /tmp/gitergo && git sparse-checkout init --cone && git sparse-checkout set Natural_environment
then set BASE below to /tmp/gitergo/Natural_environment (or wherever you put it).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from taxonomy import V2_ALPHA_CLASSES
from preprocessing import load_and_preprocess

LABEL_MAP = {
    "Cercospora_leaf_spot Gray_leaf_spot": "Corn___Gray_Leaf_Spot",
    "Common_rust": "Corn___Common_Rust",
    "Northern_Leaf_Blight": "Corn___Northern_Leaf_Blight",
    "healthy": "Corn___Healthy",
}
BASE = os.environ.get("GITERGO_NATURAL_ENV_PATH", "/tmp/gitergo/Natural_environment")
PROJECT_ML = Path(__file__).resolve().parents[2]


def wilson_ci(k, n, z=1.96):
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return center - margin, center + margin


def evaluate_model(model_path, label):
    model = tf.keras.models.load_model(model_path)
    class_to_idx = {c: i for i, c in enumerate(V2_ALPHA_CLASSES)}

    paths, true_labels = [], []
    for split in ["train", "val", "test"]:
        for folder, canonical in LABEL_MAP.items():
            d = f"{BASE}/{split}/{folder}"
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                paths.append(f"{d}/{f}")
                true_labels.append(canonical)

    if not paths:
        raise FileNotFoundError(
            f"No images found under {BASE} -- clone the gitergo/Datasets "
            f"Natural_environment folder first (see module docstring)."
        )

    y_true = np.array([class_to_idx[l] for l in true_labels])
    y_pred, confs = [], []
    BATCH = 64
    imgs_batch = []

    def flush():
        nonlocal imgs_batch, y_pred, confs
        if not imgs_batch:
            return
        arr = np.stack(imgs_batch, axis=0)
        preds = model.predict(arr, verbose=0)
        for p in preds:
            y_pred.append(int(np.argmax(p)))
            confs.append(float(np.max(p)))
        imgs_batch = []

    for i, p in enumerate(paths):
        try:
            img = load_and_preprocess(p)
        except Exception as e:
            print(f"skip {p}: {e}")
            continue
        imgs_batch.append(img)
        if len(imgs_batch) >= BATCH:
            flush()
        if (i + 1) % 500 == 0:
            print(f"  {label}: {i + 1}/{len(paths)}")
    flush()

    y_pred = np.array(y_pred)
    confs = np.array(confs)
    n = len(y_pred)
    y_true = y_true[:n]

    acc = accuracy_score(y_true, y_pred)
    k = int(round(acc * n))
    lo, hi = wilson_ci(k, n)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(V2_ALPHA_CLASSES))), zero_division=0
    )
    per_class = {}
    for i, c in enumerate(V2_ALPHA_CLASSES):
        if support[i] > 0:
            per_class[c] = {
                "precision": round(float(precision[i]), 4), "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4), "support": int(support[i]),
            }
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(V2_ALPHA_CLASSES))))

    print(f"\n=== {label} on gitergo Natural_environment (n={n}) ===")
    print(f"Accuracy: {acc:.4f}  (95% CI [{lo:.4f}, {hi:.4f}])")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"Mean confidence: {confs.mean():.4f}")
    for c, m in per_class.items():
        print(f"  {c:30s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} n={m['support']}")

    return {
        "model": label, "n": n, "accuracy": round(float(acc), 4),
        "accuracy_95pct_wilson_ci": [round(float(lo), 4), round(float(hi), 4)],
        "macro_f1": round(float(macro_f1), 4), "mean_confidence": round(float(confs.mean()), 4),
        "per_class": per_class, "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": V2_ALPHA_CLASSES,
    }


if __name__ == "__main__":
    results = {}
    results["v2_alpha"] = evaluate_model(str(PROJECT_ML / "artifacts/agrimind_plant_disease_v2.keras"), "v2-alpha")
    results["v2_r2"] = evaluate_model(str(PROJECT_ML / "experiments/artifacts_v2_r2/agrimind_plant_disease_v2_r2.keras"), "v2-r2")

    out_path = PROJECT_ML / "experiments/reports/corn_natural_environment_external_validation.json"
    out_path.write_text(json.dumps({
        "purpose": "Large-scale (n=3,380) real-world Corn external validation, MEASUREMENT ONLY -- not used for training any model.",
        "results": results,
    }, indent=2))
    print(f"\nWrote {out_path}")
