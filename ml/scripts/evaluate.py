#!/usr/bin/env python3
"""
Internal held-out test evaluation for AgriMind Plant Disease V2-alpha.

Uses the SAME shared preprocessing implementation as training (preprocessing.py)
and the test split produced by split.py (never seen during training or
validation-based checkpoint selection).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    classification_report, confusion_matrix, precision_recall_fscore_support, accuracy_score
)

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import V2_ALPHA_CLASSES
from preprocessing import load_and_preprocess

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
SPLIT_RECORDS_PATH = PROJECT_ML / "data" / "split_records.json"
MODEL_PATH = PROJECT_ML / "artifacts" / "agrimind_plant_disease_v2.keras"
OUT_PATH = PROJECT_ML / "reports" / "v2_internal_test_evaluation.json"


def main():
    model = tf.keras.models.load_model(MODEL_PATH)
    records = json.load(open(SPLIT_RECORDS_PATH))
    test_records = [r for r in records if r["split"] == "test"]
    print(f"Evaluating on {len(test_records)} held-out test images")

    class_to_idx = {c: i for i, c in enumerate(V2_ALPHA_CLASSES)}
    y_true, y_pred, confidences, sources = [], [], [], []

    batch_imgs, batch_meta = [], []
    BATCH = 64

    def flush():
        nonlocal batch_imgs, batch_meta
        if not batch_imgs:
            return
        arr = np.stack(batch_imgs, axis=0)
        preds = model.predict(arr, verbose=0)
        for p, meta in zip(preds, batch_meta):
            pred_idx = int(np.argmax(p))
            y_true.append(meta["true_idx"])
            y_pred.append(pred_idx)
            confidences.append(float(np.max(p)))
            sources.append(meta["source"])
        batch_imgs, batch_meta = [], []

    for i, r in enumerate(test_records):
        full_path = PROJECT_ML / r["raw_path"]
        img = load_and_preprocess(str(full_path))
        batch_imgs.append(img)
        batch_meta.append({"true_idx": class_to_idx[r["canonical_label"]], "source": r["source_dataset"]})
        if len(batch_imgs) >= BATCH:
            flush()
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{len(test_records)}")
    flush()

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    confidences = np.array(confidences)
    sources = np.array(sources)

    overall_acc = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(V2_ALPHA_CLASSES))), zero_division=0
    )
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(V2_ALPHA_CLASSES))))

    per_class = {}
    for i, c in enumerate(V2_ALPHA_CLASSES):
        per_class[c] = {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }

    # Source breakdown (PlantVillage vs PlantDoc within the test split)
    source_breakdown = {}
    for src in np.unique(sources):
        mask = sources == src
        source_breakdown[src] = {
            "n": int(mask.sum()),
            "accuracy": round(float(accuracy_score(y_true[mask], y_pred[mask])), 4),
            "mean_confidence": round(float(confidences[mask].mean()), 4),
        }

    result = {
        "evaluated_at": "2026-09-21",
        "model_path": str(MODEL_PATH),
        "n_test_images": len(test_records),
        "overall_accuracy": round(overall_acc, 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "mean_confidence_overall": round(float(confidences.mean()), 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": V2_ALPHA_CLASSES,
        "source_breakdown": source_breakdown,
        "note": "This is V2-alpha's internal held-out test (leakage-gated, near-dup-safe split). It is NOT held-out in the sense of being independent of V1's unknown training data lineage -- it IS independent of V2's own training/validation split, which V1 could never claim (V1's training provenance is unknown).",
    }

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nOverall accuracy: {overall_acc:.4f}")
    print(f"Macro F1: {macro_f1:.4f}  Weighted F1: {weighted_f1:.4f}")
    print("Source breakdown:", json.dumps(source_breakdown, indent=2))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
