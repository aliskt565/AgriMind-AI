"""
REAL evaluation of the existing agrimind_plant_disease_model.keras against
genuine, correctly-labeled images -- for the SUBSET of classes where a
legitimate, verifiable, appropriately-licensed source actually exists.

DATA SOURCE (verified, not assumed):
  spMohanty/PlantVillage-Dataset (github.com/spMohanty/PlantVillage-Dataset)
  License: CC-BY-SA-3.0 (per the dataset's Hugging Face mirror metadata --
  no LICENSE file exists in the GitHub repo itself, so this is the only
  place a formal license is actually declared). Attribution: Mohanty,
  Hughes, Salathe 2016, Frontiers in Plant Science.

SCOPE -- read this before trusting the numbers below:
  PlantVillage does NOT contain Rice, Wheat, sugarcane ("Red Rot"), or any
  generic/background/non-plant images. Of the model's 18 classes, only 7
  have a legitimate, verifiable real-image source available in this
  environment:
    Corn___Common_Rust, Corn___Gray_Leaf_Spot, Corn___Healthy,
    Corn___Northern_Leaf_Blight, Potato___Early_Blight, Potato___Healthy,
    Potato___Late_Blight
  The other 11 classes (all Rice/Wheat classes, "Red Rot", bare
  "Bacterial Blight", bare "Healthy", "Background___Non_Plant") remain
  COMPLETELY UNEVALUATED -- there is no legitimate labeled data for them
  anywhere in this environment. Metrics below cover ONLY the 7 classes
  listed above; nothing here should be read as an overall-model accuracy
  figure.

  Also note: the model's CLASS_NAMES strings ("Corn___Common_Rust") are NOT
  byte-identical to PlantVillage's real folder names
  ("Corn_(maize)___Common_rust_") -- they were evidently manually
  retyped/simplified. The mapping below is a manual, human-verified
  semantic mapping, not a string match.
"""
import io
import os
import sys
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "apps/api"))
os.chdir(os.path.join(os.path.dirname(__file__), "apps/api"))

import numpy as np
from PIL import Image

from app.main import _get_model, CLASS_NAMES

SAMPLES_PER_CLASS = 40
SEED = 42

# Manual, human-verified semantic mapping: real PlantVillage folder -> model's CLASS_NAMES label
MAPPING = {
    "Corn_(maize)___Common_rust_": "Corn___Common_Rust",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "Corn___Gray_Leaf_Spot",
    "Corn_(maize)___healthy": "Corn___Healthy",
    "Corn_(maize)___Northern_Leaf_Blight": "Corn___Northern_Leaf_Blight",
    "Potato___Early_blight": "Potato___Early_Blight",
    "Potato___healthy": "Potato___Healthy",
    "Potato___Late_blight": "Potato___Late_Blight",
}

DATA_ROOT = "/home/claude/pv_repo/raw/color"


def preprocess(img: Image.Image) -> np.ndarray:
    img = img.convert("RGB").resize((224, 224))
    x = np.expand_dims(np.array(img), axis=0)
    return x


def main():
    random.seed(SEED)
    model = _get_model()
    assert model is not None, "Model failed to load"

    y_true = []
    y_pred = []
    confidences = []
    per_image_records = []

    for folder_name, true_label in MAPPING.items():
        folder_path = os.path.join(DATA_ROOT, folder_name)
        files = sorted(os.listdir(folder_path))
        rng = random.Random(SEED)
        rng.shuffle(files)
        sample = files[:SAMPLES_PER_CLASS]
        print(f"Evaluating {len(sample)} images for '{true_label}' (real folder: {folder_name})")

        for fname in sample:
            path = os.path.join(folder_path, fname)
            try:
                img = Image.open(path)
                x = preprocess(img)
            except Exception as e:
                print(f"  SKIP (unreadable): {fname} -> {e}")
                continue

            preds = model.predict(x, verbose=0)
            idx = int(np.argmax(preds[0]))
            conf = float(np.max(preds[0])) * 100
            predicted_label = CLASS_NAMES[idx]

            y_true.append(true_label)
            y_pred.append(predicted_label)
            confidences.append(conf)
            per_image_records.append({
                "file": fname, "true": true_label, "predicted": predicted_label, "confidence": round(conf, 2)
            })

    # ---- Metrics (only across the 7 evaluated classes + whatever the model predicted) ----
    from sklearn.metrics import classification_report, confusion_matrix

    labels_in_play = sorted(set(y_true) | set(y_pred))
    report = classification_report(y_true, y_pred, labels=labels_in_play, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels_in_play)

    result = {
        "scope_note": "Covers ONLY 7 of 18 model classes -- see script docstring. NOT an overall model accuracy.",
        "data_source": "spMohanty/PlantVillage-Dataset (CC-BY-SA-3.0), github.com/spMohanty/PlantVillage-Dataset",
        "samples_per_class_requested": SAMPLES_PER_CLASS,
        "total_images_evaluated": len(y_true),
        "labels": labels_in_play,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "confidence_stats": {
            "mean": float(np.mean(confidences)),
            "min": float(np.min(confidences)),
            "max": float(np.max(confidences)),
            "median": float(np.median(confidences)),
        },
        "per_image_records": per_image_records,
    }

    with open("/home/claude/pv_eval_results.json", "w") as f:
        json.dump(result, f, indent=2)

    print("\n=== SUMMARY ===")
    print(f"Total images evaluated: {len(y_true)}")
    print(f"Overall accuracy (these 7 classes only): {report['accuracy']:.4f}")
    print(f"Macro F1: {report['macro avg']['f1-score']:.4f}")
    print(f"Weighted F1: {report['weighted avg']['f1-score']:.4f}")
    print("\nPer-class:")
    for label in labels_in_play:
        if label in report:
            r = report[label]
            print(f"  {label:30s} P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1-score']:.3f} support={int(r['support'])}")
    print(f"\nConfidence: mean={result['confidence_stats']['mean']:.1f} min={result['confidence_stats']['min']:.1f} max={result['confidence_stats']['max']:.1f}")
    print("\nConfusion matrix (rows=true, cols=predicted), labels order:")
    print(labels_in_play)
    print(np.array(cm))
    print("\nFull results written to /home/claude/pv_eval_results.json")


if __name__ == "__main__":
    main()
