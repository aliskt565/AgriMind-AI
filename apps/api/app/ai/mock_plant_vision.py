"""
MOCK IMPLEMENTATION -- NOT A TRAINED MODEL.

Exercises the full 7-state Plant Vision contract (see roadmap Section 18)
using real validation (format/size) plus a deterministic pseudo-inference
step, so the API/UI can be built and tested against every outcome branch --
including rejections and low-confidence results -- before a real image
classification model is wired in.
"""
import hashlib
import random

from app.ai.base import PlantVisionProvider
from app.ai.contracts import PlantVisionInput, PlantVisionResult, DetectionResultType

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB, matches settings.MAX_UPLOAD_SIZE_MB
MIN_IMAGE_SIZE_BYTES = 1024  # anything smaller is almost certainly not a usable photo

SUPPORTED_CROPS = {"wheat", "rice", "cotton", "maize", "sugarcane", "tomato", "potato"}

_MOCK_DISEASES = {
    "wheat": [("Leaf Rust", "yellow-orange pustules on leaf surface"), ("Powdery Mildew", "white powdery patches on leaves")],
    "rice": [("Bacterial Leaf Blight", "water-soaked lesions turning yellow-white"), ("Rice Blast", "diamond-shaped lesions with gray centers")],
    "cotton": [("Leaf Curl Virus", "upward curling and thickening of leaves")],
    "maize": [("Northern Corn Leaf Blight", "long grayish-green lesions on leaves")],
    "sugarcane": [("Red Rot", "reddish discoloration inside the stalk")],
    "tomato": [("Early Blight", "concentric dark rings on lower leaves")],
    "potato": [("Late Blight", "dark, water-soaked spots that spread rapidly")],
}


class MockPlantVisionProvider(PlantVisionProvider):
    def analyze(self, data: PlantVisionInput) -> PlantVisionResult:
        # --- Stage 1: format/size validation (real checks, not mocked) ---
        if data.image_content_type not in ALLOWED_CONTENT_TYPES:
            return PlantVisionResult(
                result_type=DetectionResultType.REJECTED_LOW_QUALITY,
                predicted_disease=None, confidence=None, symptoms_matched=None, guidance_text=None,
                model_name="mock-plant-vision", model_version="0.1.0-mock",
                rejection_reason=f"Unsupported file type '{data.image_content_type}'. Please upload a JPEG, PNG, or WEBP image.",
            )

        if data.image_size_bytes > MAX_IMAGE_SIZE_BYTES:
            return PlantVisionResult(
                result_type=DetectionResultType.REJECTED_LOW_QUALITY,
                predicted_disease=None, confidence=None, symptoms_matched=None, guidance_text=None,
                model_name="mock-plant-vision", model_version="0.1.0-mock",
                rejection_reason="Image file is too large. Please upload an image under 8MB.",
            )

        if data.image_size_bytes < MIN_IMAGE_SIZE_BYTES:
            return PlantVisionResult(
                result_type=DetectionResultType.REJECTED_LOW_QUALITY,
                predicted_disease=None, confidence=None, symptoms_matched=None, guidance_text=None,
                model_name="mock-plant-vision", model_version="0.1.0-mock",
                rejection_reason="Image appears too small/corrupted to analyze. Please retake the photo.",
            )

        # --- Stage 2: crop support check ---
        crop_key = data.crop_type.strip().lower()
        if crop_key not in SUPPORTED_CROPS:
            return PlantVisionResult(
                result_type=DetectionResultType.UNSUPPORTED_CROP,
                predicted_disease=None, confidence=None, symptoms_matched=None, guidance_text=None,
                model_name="mock-plant-vision", model_version="0.1.0-mock",
                rejection_reason=f"'{data.crop_type}' is not yet supported by Plant Vision.",
            )

        # --- Stage 3: deterministic pseudo-inference from image bytes ---
        # Real inference would run a trained classifier here. This mock derives
        # a stable-but-varied outcome from the image content hash purely so
        # repeated uploads of the same test image behave consistently, and
        # different images exercise different branches (healthy / low-confidence
        # / high-confidence / non-plant) during development and testing.
        digest = hashlib.sha256(data.image_bytes).hexdigest()
        rng = random.Random(digest)
        roll = rng.random()

        if roll < 0.10:
            return PlantVisionResult(
                result_type=DetectionResultType.REJECTED_NON_PLANT,
                predicted_disease=None, confidence=None, symptoms_matched=None, guidance_text=None,
                model_name="mock-plant-vision", model_version="0.1.0-mock",
                rejection_reason="No plant material was detected in this image. Please retake, ensuring the plant fills the frame.",
            )

        if roll < 0.35:
            return PlantVisionResult(
                result_type=DetectionResultType.HEALTHY,
                predicted_disease=None, confidence=round(rng.uniform(0.80, 0.97), 2),
                symptoms_matched="No disease symptoms detected.",
                guidance_text="This crop appears healthy. Continue routine monitoring.",
                model_name="mock-plant-vision", model_version="0.1.0-mock",
            )

        disease_name, symptoms = rng.choice(_MOCK_DISEASES[crop_key])
        confidence = round(rng.uniform(0.35, 0.95), 2)
        result_type = DetectionResultType.HIGH_CONFIDENCE if confidence >= 0.65 else DetectionResultType.LOW_CONFIDENCE

        guidance = (
            f"Possible {disease_name.lower()} detected. Isolate affected plants where practical and monitor spread. "
            "This is a general starting point, not a treatment plan -- confirm with a local agricultural expert "
            "before applying any chemical treatment."
        )

        return PlantVisionResult(
            result_type=result_type,
            predicted_disease=disease_name,
            confidence=confidence,
            symptoms_matched=symptoms,
            guidance_text=guidance,
            model_name="mock-plant-vision",
            model_version="0.1.0-mock",
        )
