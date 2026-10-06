"""
SINGLE shared preprocessing implementation for AgriMind Plant Disease V2.

This module is imported by training, evaluation, AND the inference wrapper --
it must never be reimplemented separately in any of those places. This is a
direct, explicit fix for V1's documented preprocessing ambiguity (V1's
inference path did raw img_to_array with no explicit preprocess_input call,
of uncertain match to whatever its training pipeline actually did).

Backbone: MobileNetV2 (matches V1, per the execution brief's architecture
instruction). MobileNetV2's canonical preprocessing is
tf.keras.applications.mobilenet_v2.preprocess_input, which scales pixel
values from [0, 255] to [-1, 1]. That exact function is called here and
nowhere else is a competing normalization implemented.
"""
import numpy as np
from PIL import Image
import tensorflow as tf

IMAGE_SIZE = (224, 224)  # matches V1's input size for direct comparability


def load_and_preprocess(path_or_bytes, is_bytes: bool = False) -> np.ndarray:
    """Load an image (from a file path or raw bytes), resize to IMAGE_SIZE,
    convert to RGB, and apply MobileNetV2's canonical preprocessing.
    Returns a (224, 224, 3) float32 array ready for model input (add a batch
    dim with np.expand_dims for single-image inference).
    """
    if is_bytes:
        import io
        im = Image.open(io.BytesIO(path_or_bytes))
    else:
        im = Image.open(path_or_bytes)
    im = im.convert("RGB")
    im = im.resize(IMAGE_SIZE, Image.BILINEAR)
    arr = np.asarray(im, dtype=np.float32)
    arr = tf.keras.applications.mobilenet_v2.preprocess_input(arr)
    return arr


def preprocessing_config() -> dict:
    """Machine-readable record of the exact preprocessing applied, for
    inclusion in model metadata."""
    return {
        "image_size": list(IMAGE_SIZE),
        "resize_method": "PIL bilinear",
        "color_mode": "RGB",
        "normalization": "tf.keras.applications.mobilenet_v2.preprocess_input (scales to [-1, 1])",
        "shared_implementation_module": "scripts/preprocessing.py:load_and_preprocess",
        "used_identically_by": ["training", "validation", "test evaluation", "OOD evaluation", "inference wrapper"],
    }
