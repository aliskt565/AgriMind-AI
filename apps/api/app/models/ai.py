import enum
import uuid

from sqlalchemy import String, Float, ForeignKey, Enum as SAEnum, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class PredictionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIPrediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One AI Crop Intelligence request/result. `inputs` and `results` are stored
    as JSON since their shape is defined by the AI contract (see app/ai/),
    not by a rigid relational schema -- this keeps the contract free to
    evolve without a migration every time an output field changes.
    """
    __tablename__ = "ai_predictions"

    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[PredictionStatus] = mapped_column(SAEnum(PredictionStatus, name="prediction_status"), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    results: Mapped[dict] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-crop-intelligence")
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.0.0-mock")


class RiskType(str, enum.Enum):
    WEATHER = "WEATHER"
    ACTIVITY_GAP = "ACTIVITY_GAP"
    DISEASE = "DISEASE"
    DATA_QUALITY = "DATA_QUALITY"
    IRRIGATION = "IRRIGATION"
    HARVEST_TIMING = "HARVEST_TIMING"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AIRisk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A Farm Risk Engine record. `risk_level` and `confidence` are intentionally
    two separate columns -- collapsing them into one score is explicitly
    disallowed by the product principles.
    """
    __tablename__ = "ai_risks"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True)
    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=True, index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=True, index=True)

    risk_type: Mapped[RiskType] = mapped_column(SAEnum(RiskType, name="risk_type"), nullable=False)
    # Distinguishes multiple concurrent findings that share the same risk_type
    # for the same field (e.g. heat stress vs. waterlogging are both WEATHER
    # risks) so the Risk Engine's upsert logic doesn't collapse them into one.
    # Null for risk types that are naturally singular per field/crop already
    # (DATA_QUALITY, ACTIVITY_GAP, DISEASE).
    signal_key: Mapped[str] = mapped_column(String(60), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(SAEnum(RiskLevel, name="risk_level"), nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(SAEnum(ConfidenceLevel, name="risk_confidence"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_signals: Mapped[dict] = mapped_column(JSON, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[RiskStatus] = mapped_column(SAEnum(RiskStatus, name="risk_status"), default=RiskStatus.ACTIVE, nullable=False)


class RecommendationCategory(str, enum.Enum):
    CROP_SELECTION = "CROP_SELECTION"
    CROP_HEALTH = "CROP_HEALTH"
    DISEASE_PREVENTION = "DISEASE_PREVENTION"
    IRRIGATION = "IRRIGATION"
    SOIL = "SOIL"
    SEASONAL_PLANNING = "SEASONAL_PLANNING"
    HARVEST_TIMING = "HARVEST_TIMING"
    RISK_ALERT = "RISK_ALERT"


class RecommendationPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISMISSED = "DISMISSED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class AIRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One Recommendation Engine output. Every row must trace to a real trigger
    (`trigger_reason`) -- the engine never fabricates a recommendation to
    fill the UI.
    """
    __tablename__ = "ai_recommendations"

    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), nullable=True)
    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=True)

    category: Mapped[RecommendationCategory] = mapped_column(
        SAEnum(RecommendationCategory, name="recommendation_category"), nullable=False
    )
    priority: Mapped[RecommendationPriority] = mapped_column(
        SAEnum(RecommendationPriority, name="recommendation_priority"), nullable=False
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        SAEnum(RecommendationStatus, name="recommendation_status"), default=RecommendationStatus.ACTIVE, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
