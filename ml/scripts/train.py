#!/usr/bin/env python3
"""
V2-alpha two-stage transfer learning training script.

Stage 1: frozen MobileNetV2 backbone, train classification head only.
Stage 2: unfreeze the top N backbone layers, fine-tune at a low learning rate,
         with early stopping on validation macro-F1-adjacent metric (val loss
         here, since Keras' built-in EarlyStopping needs a monitorable scalar;
         full per-class metrics are computed separately in evaluate.py).

Records exact configuration (seed, versions, architecture, hyperparameters,
dataset manifest hash) into artifacts/agrimind_plant_disease_v2_metadata.json
together with evaluate.py's later additions.
"""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import V2_ALPHA_CLASSES
from preprocessing import IMAGE_SIZE, preprocessing_config

PROJECT_ML = Path(__file__).resolve().parents[1]  # = <project>/ml (portable)
SPLIT_RECORDS_PATH = PROJECT_ML / "data" / "split_records.json"
MANIFEST_PATH = PROJECT_ML / "data" / "dataset_manifest.json"
ARTIFACTS_DIR = PROJECT_ML / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

RANDOM_SEED = 42
BATCH_SIZE = 32
STAGE1_EPOCHS = 6
STAGE2_EPOCHS = 6
STAGE2_UNFREEZE_LAYERS = 20  # top N layers of the MobileNetV2 backbone
STAGE1_LR = 1e-3
STAGE2_LR = 1e-5

tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def manifest_hash() -> str:
    return hashlib.sha256(open(MANIFEST_PATH, "rb").read()).hexdigest()


def build_dataset(records, class_to_idx, split, augment: bool, batch_size=BATCH_SIZE, shuffle=True):
    subset = [r for r in records if r["split"] == split]
    paths = [str(PROJECT_ML / r["raw_path"]) for r in subset]
    labels = [class_to_idx[r["canonical_label"]] for r in subset]

    def _load(path, label):
        img_bytes = tf.io.read_file(path)
        img = tf.io.decode_image(img_bytes, channels=3, expand_animations=False)
        img = tf.image.resize(img, IMAGE_SIZE, method="bilinear")
        img = tf.cast(img, tf.float32)
        img = tf.keras.applications.mobilenet_v2.preprocess_input(img)
        return img, label

    def _augment(img, label):
        # Augmentation happens ONLY here, applied ONLY to the train split,
        # and only ever after split assignment (split.py already ran).
        img = tf.image.random_flip_left_right(img)
        img = tf.image.random_brightness(img, max_delta=0.15)
        img = tf.image.random_contrast(img, lower=0.85, upper=1.15)
        img = tf.image.random_crop(tf.image.resize_with_crop_or_pad(img, IMAGE_SIZE[0] + 20, IMAGE_SIZE[1] + 20),
                                    size=[IMAGE_SIZE[0], IMAGE_SIZE[1], 3])
        return img, label

    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    if shuffle:
        ds = ds.shuffle(buffer_size=len(paths), seed=RANDOM_SEED, reshuffle_each_iteration=True)
    ds = ds.map(_load, num_parallel_calls=tf.data.AUTOTUNE)
    if augment:
        ds = ds.map(_augment, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds, len(subset)


def build_model(num_classes):
    base = keras.applications.MobileNetV2(
        input_shape=(*IMAGE_SIZE, 3), include_top=False, weights="imagenet"
    )
    base.trainable = False
    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = base(inputs, training=False)
    x = keras.layers.GlobalAveragePooling2D()(x)
    x = keras.layers.Dense(128, activation="relu")(x)
    x = keras.layers.Dropout(0.3)(x)
    outputs = keras.layers.Dense(num_classes, activation="softmax")(x)
    model = keras.Model(inputs, outputs)
    return model, base


def main():
    t_start = time.time()
    records = json.load(open(SPLIT_RECORDS_PATH))
    class_to_idx = {c: i for i, c in enumerate(V2_ALPHA_CLASSES)}

    train_ds, n_train = build_dataset(records, class_to_idx, "train", augment=True)
    val_ds, n_val = build_dataset(records, class_to_idx, "val", augment=False, shuffle=False)
    print(f"train={n_train} val={n_val}")

    # Class weights, justified by the real, disclosed imbalance (Potato_Healthy
    # is far smaller than every other class -- see dataset_manifest.json).
    from collections import Counter
    train_labels = [class_to_idx[r["canonical_label"]] for r in records if r["split"] == "train"]
    counts = Counter(train_labels)
    n_classes = len(V2_ALPHA_CLASSES)
    total = sum(counts.values())
    class_weight = {i: total / (n_classes * counts.get(i, 1)) for i in range(n_classes)}
    print("Class weights:", {V2_ALPHA_CLASSES[i]: round(w, 3) for i, w in class_weight.items()})

    model, base = build_model(n_classes)

    # --- Stage 1: frozen backbone ---
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=STAGE1_LR),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    ckpt_path = str(ARTIFACTS_DIR / "stage1_best.weights.h5")
    callbacks_s1 = [
        keras.callbacks.ModelCheckpoint(ckpt_path, save_best_only=True, save_weights_only=True, monitor="val_loss"),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True),
    ]
    t1 = time.time()
    hist1 = model.fit(train_ds, validation_data=val_ds, epochs=STAGE1_EPOCHS,
                       class_weight=class_weight, callbacks=callbacks_s1, verbose=2)
    stage1_time = time.time() - t1
    stage1_best_epoch = int(np.argmin(hist1.history["val_loss"])) + 1

    # --- Stage 2: unfreeze top N backbone layers, low LR fine-tune ---
    base.trainable = True
    for layer in base.layers[:-STAGE2_UNFREEZE_LAYERS]:
        layer.trainable = False
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=STAGE2_LR),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    ckpt_path2 = str(ARTIFACTS_DIR / "stage2_best.weights.h5")
    callbacks_s2 = [
        keras.callbacks.ModelCheckpoint(ckpt_path2, save_best_only=True, save_weights_only=True, monitor="val_loss"),
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True),
    ]
    t2 = time.time()
    hist2 = model.fit(train_ds, validation_data=val_ds, epochs=STAGE2_EPOCHS,
                       class_weight=class_weight, callbacks=callbacks_s2, verbose=2)
    stage2_time = time.time() - t2
    stage2_best_epoch = int(np.argmin(hist2.history["val_loss"])) + 1

    total_time = time.time() - t_start

    # Save final model
    model_path = ARTIFACTS_DIR / "agrimind_plant_disease_v2.keras"
    model.save(model_path)
    print(f"Saved model to {model_path}")

    training_config = {
        "random_seed": RANDOM_SEED,
        "python_version": platform.python_version(),
        "tensorflow_version": tf.__version__,
        "keras_version": keras.__version__,
        "architecture": "MobileNetV2 (ImageNet-pretrained) -> GlobalAveragePooling2D -> Dense(128, relu) -> Dropout(0.3) -> Dense(7, softmax)",
        "image_size": list(IMAGE_SIZE),
        "optimizer": "Adam",
        "stage1_learning_rate": STAGE1_LR,
        "stage2_learning_rate": STAGE2_LR,
        "stage2_unfrozen_top_layers": STAGE2_UNFREEZE_LAYERS,
        "batch_size": BATCH_SIZE,
        "stage1_epochs_run": len(hist1.history["loss"]),
        "stage2_epochs_run": len(hist2.history["loss"]),
        "stage1_best_epoch": stage1_best_epoch,
        "stage2_best_epoch": stage2_best_epoch,
        "augmentation": "random horizontal flip, random brightness (+-0.15), random contrast (0.85-1.15), random crop after pad -- train split only, applied after split assignment",
        "class_weights": {V2_ALPHA_CLASSES[i]: round(w, 4) for i, w in class_weight.items()},
        "dataset_manifest_sha256": manifest_hash(),
        "n_train_images": n_train,
        "n_val_images": n_val,
        "stage1_training_duration_seconds": round(stage1_time, 1),
        "stage2_training_duration_seconds": round(stage2_time, 1),
        "total_training_duration_seconds": round(total_time, 1),
        "preprocessing": preprocessing_config(),
    }
    training_history = {
        "stage1": {k: [round(float(x), 5) for x in v] for k, v in hist1.history.items()},
        "stage2": {k: [round(float(x), 5) for x in v] for k, v in hist2.history.items()},
    }

    with open(ARTIFACTS_DIR / "training_config.json", "w") as f:
        json.dump(training_config, f, indent=2)
    with open(ARTIFACTS_DIR / "training_history.json", "w") as f:
        json.dump(training_history, f, indent=2)

    print(f"\nTotal training time: {total_time:.1f}s")
    print("Wrote training_config.json and training_history.json")


if __name__ == "__main__":
    main()
