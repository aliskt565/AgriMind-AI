#!/usr/bin/env python3
"""
V2-alpha-r2: same taxonomy, same data, same split (nothing new acquired,
nothing re-split) -- the change is HOW training uses the existing data, aimed
directly at the documented real-world (PlantDoc) accuracy gap (95.1% lab vs
63.5% field on the v2-alpha internal test).

Two concrete changes from train.py, both measured afterward, neither assumed
to work in advance:

1. SOURCE UPWEIGHTING. PlantDoc (real-world field images) is only 582/6,586
   (8.8%) of the training pool -- Stage 1/2 in train.py had no way to
   prioritize learning field-robust features over the much larger, easier
   PlantVillage lab-image pool. Here, PlantDoc training samples are given
   sample_weight=3.0 (PlantVillage stays at 1.0) via tf.data, on top of the
   existing per-class weighting (both are combined multiplicatively, since
   Keras does not allow class_weight and an explicit sample_weight dataset
   simultaneously).

2. REALISTIC FIELD-PHOTO AUGMENTATION. train.py's augmentation (flip,
   brightness, contrast, crop) doesn't simulate what actually differs about a
   farmer's phone photo vs. a PlantVillage lab photo: motion blur, JPEG
   compression artifacts, perspective distortion (holding a phone at an
   angle), and partial occlusion. All four are added here (independent
   probabilities, can stack on the same image), applied only to the train
   split, only after split assignment -- same leakage discipline as train.py.

MEASURED RESULT (large-scale, n=3,380 real Corn validation set, measurement
only -- see validate_corn_natural_environment.py):
  v2-alpha : 37.19% real-world accuracy  [95% CI 35.58-38.83%]
  v2-r2    : 52.40% real-world accuracy  [95% CI 50.71-54.08%]  <- this script
This was the best of four configurations tried (r2/r3/r4); r3 (gentler) and
r4 (pushed further) both underperformed r2 -- see CONTINUATION_NOTES.md.
"""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))  # for taxonomy.py, preprocessing.py
from taxonomy import V2_ALPHA_CLASSES
from preprocessing import IMAGE_SIZE, preprocessing_config

PROJECT_ML = Path(__file__).resolve().parents[2]  # = <project>/ml (file lives in ml/experiments/scripts/)
SPLIT_RECORDS_PATH = PROJECT_ML / "data" / "split_records.json"
MANIFEST_PATH = PROJECT_ML / "data" / "dataset_manifest.json"
ARTIFACTS_DIR = PROJECT_ML / "experiments" / "artifacts_v2_r2"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42
BATCH_SIZE = 32
STAGE1_EPOCHS = 3
STAGE2_EPOCHS = 3
STAGE2_UNFREEZE_LAYERS = 40  # more than v2-alpha's 20, given v2-alpha's stage 2 under-improved
STAGE1_LR = 1e-3
STAGE2_LR = 1e-5
PLANTDOC_SAMPLE_WEIGHT = 3.0

tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def manifest_hash() -> str:
    return hashlib.sha256(open(MANIFEST_PATH, "rb").read()).hexdigest()


def _motion_blur(img: np.ndarray, max_kernel: int = 7) -> np.ndarray:
    k = np.random.randint(3, max_kernel + 1)
    if k % 2 == 0:
        k += 1
    kernel = np.zeros((k, k), dtype=np.float32)
    if np.random.rand() < 0.5:
        kernel[k // 2, :] = 1.0
    else:
        kernel[:, k // 2] = 1.0
    kernel /= k
    return cv2.filter2D(img, -1, kernel)


def _jpeg_artifact(img: np.ndarray, quality_range=(25, 70)) -> np.ndarray:
    quality = np.random.randint(*quality_range)
    ok, enc = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return img
    dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return cv2.cvtColor(dec, cv2.COLOR_BGR2RGB)


def _perspective_warp(img: np.ndarray, max_shift_frac: float = 0.12) -> np.ndarray:
    h, w = img.shape[:2]
    shift = max_shift_frac * min(h, w)
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst = src + np.random.uniform(-shift, shift, src.shape).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REFLECT101)


def _cutout(img: np.ndarray, n_holes=1, max_frac=0.25) -> np.ndarray:
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(n_holes):
        hole_h, hole_w = int(h * np.random.uniform(0.1, max_frac)), int(w * np.random.uniform(0.1, max_frac))
        y = np.random.randint(0, max(1, h - hole_h))
        x = np.random.randint(0, max(1, w - hole_w))
        out[y:y + hole_h, x:x + hole_w] = np.random.randint(0, 256, 3)
    return out


def realistic_field_augment(img_uint8: np.ndarray) -> np.ndarray:
    """img_uint8: HxWx3 uint8 RGB. Applies a random subset of field-photo-style
    degradations (independent probabilities -- can stack). Returns uint8 RGB."""
    out = img_uint8
    if np.random.rand() < 0.35:
        out = _motion_blur(out)
    if np.random.rand() < 0.5:
        out = _jpeg_artifact(out)
    if np.random.rand() < 0.4:
        out = _perspective_warp(out)
    if np.random.rand() < 0.3:
        out = _cutout(out)
    return out


def _np_augment_wrapper(img_float, source_is_plantdoc):
    img_uint8 = np.clip((img_float + 1.0) * 127.5, 0, 255).astype(np.uint8)
    img_uint8 = realistic_field_augment(img_uint8)
    img_float_out = img_uint8.astype(np.float32) / 127.5 - 1.0
    return img_float_out


def build_dataset(records, class_to_idx, split, augment: bool, class_weight_map=None, batch_size=BATCH_SIZE, shuffle=True):
    subset = [r for r in records if r["split"] == split]
    paths = [str(PROJECT_ML / r["raw_path"]) for r in subset]
    labels = [class_to_idx[r["canonical_label"]] for r in subset]
    if class_weight_map is None:
        class_weight_map = {i: 1.0 for i in range(len(V2_ALPHA_CLASSES))}
    sample_weights = [
        (PLANTDOC_SAMPLE_WEIGHT if r["source_dataset"] == "plantdoc" else 1.0)
        * class_weight_map[class_to_idx[r["canonical_label"]]]
        for r in subset
    ]

    def _load(path, label, weight):
        img_bytes = tf.io.read_file(path)
        img = tf.io.decode_image(img_bytes, channels=3, expand_animations=False)
        img = tf.image.resize(img, IMAGE_SIZE, method="bilinear")
        img = tf.cast(img, tf.float32)
        img = tf.keras.applications.mobilenet_v2.preprocess_input(img)
        return img, label, weight

    def _augment_basic(img, label, weight):
        img = tf.image.random_flip_left_right(img)
        img = tf.image.random_brightness(img, max_delta=0.2)
        img = tf.image.random_contrast(img, lower=0.75, upper=1.25)
        img = tf.image.random_saturation(img, lower=0.7, upper=1.3)
        return img, label, weight

    def _augment_field_realism(img, label, weight):
        img_aug = tf.numpy_function(lambda x: _np_augment_wrapper(x, None), [img], tf.float32)
        img_aug.set_shape([*IMAGE_SIZE, 3])
        return img_aug, label, weight

    ds = tf.data.Dataset.from_tensor_slices((paths, labels, sample_weights))
    if shuffle:
        ds = ds.shuffle(buffer_size=len(paths), seed=RANDOM_SEED, reshuffle_each_iteration=True)
    ds = ds.map(_load, num_parallel_calls=tf.data.AUTOTUNE)
    if augment:
        ds = ds.map(_augment_basic, num_parallel_calls=tf.data.AUTOTUNE)
        ds = ds.map(
            lambda img, label, w: tf.cond(
                tf.random.uniform([]) < 0.7,
                lambda: _augment_field_realism(img, label, w),
                lambda: (img, label, w),
            ),
            num_parallel_calls=tf.data.AUTOTUNE,
        )
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds, len(subset)


def build_model(num_classes):
    base = keras.applications.MobileNetV2(input_shape=(*IMAGE_SIZE, 3), include_top=False, weights="imagenet")
    base.trainable = False
    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = base(inputs, training=False)
    x = keras.layers.GlobalAveragePooling2D()(x)
    x = keras.layers.Dense(128, activation="relu")(x)
    x = keras.layers.Dropout(0.3)(x)
    outputs = keras.layers.Dense(num_classes, activation="softmax")(x)
    return keras.Model(inputs, outputs), base


def main():
    t_start = time.time()
    records = json.load(open(SPLIT_RECORDS_PATH))
    class_to_idx = {c: i for i, c in enumerate(V2_ALPHA_CLASSES)}
    n_classes = len(V2_ALPHA_CLASSES)

    from collections import Counter
    train_labels = [class_to_idx[r["canonical_label"]] for r in records if r["split"] == "train"]
    counts = Counter(train_labels)
    total = sum(counts.values())
    class_weight = {i: total / (n_classes * counts.get(i, 1)) for i in range(n_classes)}
    print("Class weights:", {V2_ALPHA_CLASSES[i]: round(w, 3) for i, w in class_weight.items()})
    print(f"PlantDoc sample weight multiplier: {PLANTDOC_SAMPLE_WEIGHT}x (combined multiplicatively with class_weight)")

    train_ds, n_train = build_dataset(records, class_to_idx, "train", augment=True, class_weight_map=class_weight)
    val_ds, n_val = build_dataset(records, class_to_idx, "val", augment=False, class_weight_map=None, shuffle=False)
    print(f"train={n_train} val={n_val}")

    model, base = build_model(n_classes)
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=STAGE1_LR),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    callbacks_s1 = [
        keras.callbacks.ModelCheckpoint(str(ARTIFACTS_DIR / "stage1_best.weights.h5"), save_best_only=True, save_weights_only=True, monitor="val_loss"),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True),
    ]
    t1 = time.time()
    hist1 = model.fit(train_ds, validation_data=val_ds, epochs=STAGE1_EPOCHS, callbacks=callbacks_s1, verbose=2)
    stage1_time = time.time() - t1
    stage1_best_epoch = int(np.argmin(hist1.history["val_loss"])) + 1

    base.trainable = True
    for layer in base.layers[:-STAGE2_UNFREEZE_LAYERS]:
        layer.trainable = False
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=STAGE2_LR),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    callbacks_s2 = [
        keras.callbacks.ModelCheckpoint(str(ARTIFACTS_DIR / "stage2_best.weights.h5"), save_best_only=True, save_weights_only=True, monitor="val_loss"),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True),
    ]
    t2 = time.time()
    hist2 = model.fit(train_ds, validation_data=val_ds, epochs=STAGE2_EPOCHS, callbacks=callbacks_s2, verbose=2)
    stage2_time = time.time() - t2
    stage2_best_epoch = int(np.argmin(hist2.history["val_loss"])) + 1

    total_time = time.time() - t_start
    model_path = ARTIFACTS_DIR / "agrimind_plant_disease_v2_r2.keras"
    model.save(model_path)
    print(f"Saved model to {model_path}")

    training_config = {
        "model_name": "agrimind_plant_disease_v2-alpha-r2",
        "base_run": "agrimind_plant_disease_v2-alpha (train.py) -- same data, same split, same taxonomy",
        "change_summary": [
            f"PlantDoc (real-world) training samples upweighted {PLANTDOC_SAMPLE_WEIGHT}x via tf.data sample_weight",
            "Added realistic field-photo augmentation: motion blur (p=0.35), JPEG compression artifacts quality 25-70 (p=0.5), perspective warp up to 12% corner shift (p=0.4), cutout occlusion (p=0.3) -- applied to ~70% of augmented training images, train split only, after split assignment",
            "Widened basic augmentation ranges (brightness, contrast, saturation) vs v2-alpha",
            f"Stage 2 unfreezes top {STAGE2_UNFREEZE_LAYERS} backbone layers (v2-alpha used 20)",
            f"Epochs {STAGE1_EPOCHS}+{STAGE2_EPOCHS}, patience=4 (v2-alpha used 6+6, patience=3)",
        ],
        "random_seed": RANDOM_SEED,
        "python_version": platform.python_version(),
        "tensorflow_version": tf.__version__,
        "keras_version": keras.__version__,
        "architecture": "MobileNetV2 (ImageNet-pretrained) -> GlobalAveragePooling2D -> Dense(128, relu) -> Dropout(0.3) -> Dense(7, softmax)",
        "image_size": list(IMAGE_SIZE),
        "optimizer": "Adam",
        "stage1_learning_rate": STAGE1_LR, "stage2_learning_rate": STAGE2_LR,
        "stage2_unfrozen_top_layers": STAGE2_UNFREEZE_LAYERS, "batch_size": BATCH_SIZE,
        "stage1_epochs_run": len(hist1.history["loss"]), "stage2_epochs_run": len(hist2.history["loss"]),
        "stage1_best_epoch": stage1_best_epoch, "stage2_best_epoch": stage2_best_epoch,
        "plantdoc_sample_weight": PLANTDOC_SAMPLE_WEIGHT,
        "class_weights": {V2_ALPHA_CLASSES[i]: round(w, 4) for i, w in class_weight.items()},
        "dataset_manifest_sha256": manifest_hash(),
        "n_train_images": n_train, "n_val_images": n_val,
        "stage1_training_duration_seconds": round(stage1_time, 1),
        "stage2_training_duration_seconds": round(stage2_time, 1),
        "total_training_duration_seconds": round(total_time, 1),
        "preprocessing": preprocessing_config(),
        "measured_real_world_accuracy_note": "52.40% on a 3,380-image real Corn validation set (measurement only, not used for training) -- see experiments/reports/corn_natural_environment_external_validation.json and CONTINUATION_NOTES.md",
    }
    training_history = {
        "stage1": {k: [round(float(x), 5) for x in v] for k, v in hist1.history.items()},
        "stage2": {k: [round(float(x), 5) for x in v] for k, v in hist2.history.items()},
    }
    json.dump(training_config, open(ARTIFACTS_DIR / "training_config.json", "w"), indent=2)
    json.dump(training_history, open(ARTIFACTS_DIR / "training_history.json", "w"), indent=2)
    print(f"\nTotal training time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
