import uuid

from pydantic import BaseModel, Field


class CropIntelligenceRequest(BaseModel):
    season: str = Field(min_length=1, max_length=50, examples=["Kharif", "Rabi", "Summer"])
    previous_crop: str | None = None
    farmer_constraints: list[str] = Field(default_factory=list)


class CropCandidateOut(BaseModel):
    crop_type: str
    suitability_score: int
    confidence: str
    explanation: str
    limiting_factors: list[str]
    risk_note: str | None


class CropIntelligenceResponse(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    candidates: list[CropCandidateOut]
    important_assumptions: list[str]
    model_name: str
    model_version: str
    is_mock: bool = True


class PlantVisionResponse(BaseModel):
    id: uuid.UUID
    crop_id: uuid.UUID
    result_type: str
    predicted_disease: str | None
    confidence: float | None
    symptoms_matched: str | None
    guidance_text: str | None
    rejection_reason: str | None
    model_name: str
    model_version: str
    is_mock: bool = True
    disclaimer: str = (
        "This is an AI-generated prediction based on visual patterns, not a confirmed "
        "agricultural diagnosis. For treatment decisions, especially involving chemicals, "
        "confirm with a qualified agricultural expert."
    )


class TriggeredRecommendation(BaseModel):
    id: uuid.UUID
    category: str
    priority: str
    text: str


class PlantVisionDetectResponse(PlantVisionResponse):
    health_status_updated: bool
    updated_health_status: str | None
    new_risk_count: int
    triggered_recommendations: list[TriggeredRecommendation] = Field(default_factory=list)


class QuickScanResponse(BaseModel):
    status: str
    message: str
    selected_crop: str | None
    predicted_class: str | None
    confidence_percent: float
    is_disease: bool
    crop_mismatch: bool
    mismatch_message: str | None
    disclaimer: str = (
        "This is an AI-generated prediction based on visual patterns, not a confirmed "
        "agricultural diagnosis. For treatment decisions, especially involving chemicals, "
        "confirm with a qualified agricultural expert."
    )
