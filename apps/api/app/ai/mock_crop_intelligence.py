"""
MOCK IMPLEMENTATION -- NOT A TRAINED MODEL.

This is a deterministic, rule-based stand-in that returns realistic,
contract-shaped data so the rest of the system (API, frontend, tests) can be
built and verified against the real AI Crop Intelligence contract before an
actual model exists. Every response is clearly labeled with
model_name="mock-crop-intelligence" so it can never be mistaken for a real
prediction downstream.

Swapping this for a real model later means writing a new class that
implements `CropIntelligenceProvider` and satisfies the same contract --
no endpoint or frontend code changes.
"""
import random

from app.ai.base import CropIntelligenceProvider
from app.ai.contracts import (
    CropIntelligenceInput, CropIntelligenceResult, CropCandidate, ConfidenceLevel,
)

# A small, deliberately simple knowledge base -- not a trained model, just
# enough rule variety to exercise the full contract (varied scores,
# confidence levels, and risk notes) during development.
_SOIL_CROP_AFFINITY = {
    "LOAMY": ["Wheat", "Maize", "Sugarcane", "Cotton"],
    "CLAY": ["Rice", "Wheat", "Sugarcane"],
    "SANDY": ["Groundnut", "Millet", "Watermelon"],
    "SILTY": ["Rice", "Vegetables", "Wheat"],
    "PEATY": ["Vegetables", "Rice"],
    "CHALKY": ["Barley", "Spinach"],
    "UNKNOWN": ["Wheat", "Maize", "Vegetables"],
}

_IRRIGATION_RISK_NOTE = {
    "RAINFED": "Rainfed irrigation increases sensitivity to seasonal rainfall variability.",
    "CANAL": "Canal-fed irrigation depends on scheduled water availability -- confirm your canal turn (warabandi) schedule aligns with this crop's water needs.",
    "TUBEWELL": "Tubewell irrigation gives more control but adds a recurring pumping cost -- factor this into your input budget.",
    "DRIP": None,
    "FLOOD": "Flood irrigation with this soil type may increase waterlogging risk.",
    "SPRINKLER": None,
    "OTHER": "Irrigation method not fully specified -- confidence is reduced accordingly.",
    "UNKNOWN": "Irrigation type not specified -- confidence is reduced accordingly.",
}


class MockCropIntelligenceProvider(CropIntelligenceProvider):
    def predict(self, data: CropIntelligenceInput) -> CropIntelligenceResult:
        candidates_pool = _SOIL_CROP_AFFINITY.get(data.soil_type, _SOIL_CROP_AFFINITY["UNKNOWN"])

        # Deterministic-ish pseudo-scoring so results are stable for a given input
        # but still varied across different inputs, without pretending to be a
        # trained model's output.
        rng = random.Random(f"{data.soil_type}-{data.irrigation_type}-{data.season}-{data.previous_crop}")

        candidates: list[CropCandidate] = []
        for crop in candidates_pool:
            base_score = rng.randint(55, 92)

            # Rotation penalty: discourage repeating a crop that appears
            # anywhere in the field's recent rotation history, not just the
            # single most-recent crop -- a slightly more realistic
            # agronomic heuristic while still clearly not a trained model.
            recent_rotation = [c.lower() for c in (data.rotation_history or [])]
            if data.previous_crop and data.previous_crop.lower() == crop.lower():
                base_score -= 15
            elif crop.lower() in recent_rotation:
                base_score -= 8

            confidence = ConfidenceLevel.HIGH
            if data.irrigation_type == "UNKNOWN" or not data.weather_context:
                confidence = ConfidenceLevel.MEDIUM
            if data.soil_type == "UNKNOWN":
                confidence = ConfidenceLevel.LOW

            limiting_factors = []
            if data.irrigation_type == "RAINFED":
                limiting_factors.append("Yield sensitive to rainfall timing")
            if data.field_size_acres and data.field_size_acres < 1:
                limiting_factors.append("Small field size limits mechanized options")
            if data.weather_context and data.weather_context.get("rainfall_mm_last_24h", 0) < 2 and data.irrigation_type in ("RAINFED", "UNKNOWN"):
                limiting_factors.append("Recent rainfall is low for a rainfed field -- irrigation planning is important")

            weather_clause = ""
            if data.weather_context:
                temp = data.weather_context.get("temperature_celsius")
                if temp is not None:
                    weather_clause = f" Recent conditions (~{temp}°C) were also factored in."

            explanation = (
                f"Key factors considered: {data.soil_type.title()} soil is commonly suited to {crop}; "
                f"{data.irrigation_type.title()} irrigation and the {data.season} season were also factored in."
                f"{weather_clause}"
            )

            candidates.append(CropCandidate(
                crop_type=crop,
                suitability_score=max(0, min(100, base_score)),
                confidence=confidence,
                explanation=explanation,
                limiting_factors=limiting_factors,
                risk_note=_IRRIGATION_RISK_NOTE.get(data.irrigation_type),
            ))

        candidates.sort(key=lambda c: c.suitability_score, reverse=True)

        assumptions = [
            "Assumes normal rainfall and temperature for the stated season.",
            "Does not account for pest/disease outbreaks not reflected in the input data.",
        ]
        if not data.weather_context:
            assumptions.append("No live weather data was available for this request; confidence is reduced.")

        return CropIntelligenceResult(
            candidates=candidates,
            important_assumptions=assumptions,
            model_name="mock-crop-intelligence",
            model_version="0.1.0-mock",
        )
