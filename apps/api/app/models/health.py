import enum
import uuid
from datetime import date

from sqlalchemy import String, Float, Date, Text, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin
from app.models.crop import HealthStatus


class CropHealthRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A point-in-time health snapshot for a crop (farmer-observed or system-derived)."""
    __tablename__ = "crop_health_records"

    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[HealthStatus] = mapped_column(SAEnum(HealthStatus, name="health_record_status"), nullable=False)
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="FARMER", nullable=False)  # FARMER | SYSTEM_DERIVED
    notes: Mapped[str] = mapped_column(Text, nullable=True)


class DetectionResultType(str, enum.Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    HEALTHY = "HEALTHY"
    REJECTED_LOW_QUALITY = "REJECTED_LOW_QUALITY"
    REJECTED_NON_PLANT = "REJECTED_NON_PLANT"
    UNSUPPORTED_CROP = "UNSUPPORTED_CROP"
    SERVICE_FAILURE = "SERVICE_FAILURE"


class DiseaseDetection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One Plant Vision analysis result. `result_type` distinguishes the 7 outcome
    states defined in the roadmap -- never collapsed into simple pass/fail.
    """
    __tablename__ = "disease_detections"

    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    result_type: Mapped[DetectionResultType] = mapped_column(
        SAEnum(DetectionResultType, name="detection_result_type"), nullable=False
    )
    predicted_disease: Mapped[str] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    symptoms_matched: Mapped[str] = mapped_column(Text, nullable=True)
    guidance_text: Mapped[str] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-plant-vision")
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.0.0-mock")
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=True)
