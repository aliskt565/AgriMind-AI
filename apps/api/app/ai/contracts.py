"""
AI contract layer.

This module defines the STABLE INTERFACE every AI capability must honor.
Mock implementations return schema-valid, contract-shaped data today; a real
model/inference service can replace a mock implementation later WITHOUT any
change to the API endpoints or frontend, because both sides only ever talk
to these dataclasses/protocols -- never to a specific implementation.

Per the roadmap's non-negotiable principle:
"Confidence, suitability, and risk are three separate concepts and are
never collapsed into one number."
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ConfidenceLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# AI Crop Intelligence contract
# ---------------------------------------------------------------------------

@dataclass
class CropIntelligenceInput:
    soil_type: str
    irrigation_type: str
    season: str  # e.g. "Kharif", "Rabi", "Summer"
    location: str | None = None
    field_size_acres: float | None = None
    previous_crop: str | None = None
    rotation_history: list[str] = field(default_factory=list)
    weather_context: dict | None = None
    farmer_constraints: list[str] = field(default_factory=list)


@dataclass
class CropCandidate:
    crop_type: str
    suitability_score: int  # 0-100, NEVER presented as guaranteed yield
    confidence: ConfidenceLevel  # separate from suitability, per product principle
    explanation: str  # "key factors considered" -- not a claimed exact causal explanation
    limiting_factors: list[str]
    risk_note: str | None  # separate again from confidence/suitability


@dataclass
class CropIntelligenceResult:
    candidates: list[CropCandidate]  # ranked, top-first
    important_assumptions: list[str]
    model_name: str
    model_version: str


# ---------------------------------------------------------------------------
# Plant Vision (disease detection) contract
# ---------------------------------------------------------------------------

class DetectionResultType(str, enum.Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    HEALTHY = "HEALTHY"
    REJECTED_LOW_QUALITY = "REJECTED_LOW_QUALITY"
    REJECTED_NON_PLANT = "REJECTED_NON_PLANT"
    UNSUPPORTED_CROP = "UNSUPPORTED_CROP"
    SERVICE_FAILURE = "SERVICE_FAILURE"


@dataclass
class PlantVisionInput:
    crop_type: str
    image_bytes: bytes
    image_content_type: str
    image_size_bytes: int


@dataclass
class PlantVisionResult:
    result_type: DetectionResultType
    predicted_disease: str | None
    confidence: float | None  # 0.0 - 1.0; None when not applicable (e.g. rejected image)
    symptoms_matched: str | None
    guidance_text: str | None
    model_name: str
    model_version: str
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Weather Intelligence contract
# ---------------------------------------------------------------------------

@dataclass
class WeatherRequestInput:
    latitude: float | None
    longitude: float | None
    location_label: str | None


@dataclass
class WeatherSnapshotResult:
    temperature_celsius: float | None
    humidity_percent: float | None
    rainfall_mm_last_24h: float | None
    forecast_summary: str
    extreme_weather_alert: str | None
    source: str  # e.g. "mock-weather", future: real provider name
    fetched_at: str  # ISO timestamp -- staleness is computed by the caller, never hidden
    is_stale: bool = False


# ---------------------------------------------------------------------------
# AI Farm Copilot contract
# ---------------------------------------------------------------------------

@dataclass
class ReferencedEntity:
    entity_type: str  # "farm" | "field" | "crop" | "risk" | "recommendation" | "activity"
    entity_id: str
    label: str  # short human-readable label, e.g. "North Plot" or "Leaf Rust risk"


@dataclass
class CopilotMessageInput:
    role: str  # "USER" | "ASSISTANT"
    content: str


@dataclass
class CopilotRequest:
    conversation_history: list[CopilotMessageInput]  # prior turns, oldest first
    user_message: str
    context: dict  # compact, structured, pre-authorized farm context -- see ContextBuilder


@dataclass
class CopilotResponse:
    content: str
    referenced_entities: list[ReferencedEntity]
    context_freshness_warnings: list[str]
    provider_name: str
    is_mock: bool



class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskFinding:
    risk_type: str  # matches app.models.ai.RiskType values
    risk_level: RiskLevel
    confidence: ConfidenceLevel
    reason: str
    supporting_signals: dict
    recommended_action: str


# ---------------------------------------------------------------------------
# Recommendation Engine contract
# ---------------------------------------------------------------------------

@dataclass
class RecommendationCandidate:
    category: str  # matches app.models.ai.RecommendationCategory values
    priority: str  # LOW | MEDIUM | HIGH
    text: str
    trigger_reason: str  # every recommendation MUST trace to a real signal
