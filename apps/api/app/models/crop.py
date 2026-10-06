import enum
import uuid
from datetime import date

from sqlalchemy import String, Float, Date, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class CropStage(str, enum.Enum):
    PLANNED = "PLANNED"
    PLANTED = "PLANTED"
    GERMINATION = "GERMINATION"
    VEGETATIVE = "VEGETATIVE"
    FLOWERING = "FLOWERING"
    FRUITING = "FRUITING"
    MATURITY = "MATURITY"
    HARVESTED = "HARVESTED"
    COMPLETED = "COMPLETED"


class CropSource(str, enum.Enum):
    """Data provenance: was this crop created manually or from an AI suggestion."""
    MANUAL = "MANUAL"
    AI_SUGGESTION = "AI_SUGGESTION"


class HealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    MONITORING = "MONITORING"
    AT_RISK = "AT_RISK"
    DISEASED = "DISEASED"


class ActivityType(str, enum.Enum):
    PLANTING = "PLANTING"
    IRRIGATION = "IRRIGATION"
    FERTILIZATION = "FERTILIZATION"
    SPRAYING = "SPRAYING"
    OBSERVATION = "OBSERVATION"
    HARVEST = "HARVEST"
    CUSTOM = "CUSTOM"


class ActivityStatus(str, enum.Enum):
    LOGGED = "LOGGED"
    SCHEDULED = "SCHEDULED"
    OVERDUE = "OVERDUE"


class Crop(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One planting cycle, belonging to exactly one Field."""
    __tablename__ = "crops"

    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    crop_type: Mapped[str] = mapped_column(String(120), nullable=False)
    variety: Mapped[str] = mapped_column(String(120), nullable=True)
    stage: Mapped[CropStage] = mapped_column(SAEnum(CropStage, name="crop_stage"), default=CropStage.PLANNED, nullable=False)
    source: Mapped[CropSource] = mapped_column(SAEnum(CropSource, name="crop_source"), default=CropSource.MANUAL, nullable=False)
    health_status: Mapped[HealthStatus] = mapped_column(
        SAEnum(HealthStatus, name="health_status"), default=HealthStatus.HEALTHY, nullable=False
    )

    planting_date: Mapped[date] = mapped_column(Date, nullable=True)
    expected_harvest_date: Mapped[date] = mapped_column(Date, nullable=True)
    actual_harvest_date: Mapped[date] = mapped_column(Date, nullable=True)
    actual_yield: Mapped[float] = mapped_column(Float, nullable=True)
    yield_unit: Mapped[str] = mapped_column(String(30), nullable=True)

    notes: Mapped[str] = mapped_column(Text, nullable=True)

    field: Mapped["Field"] = relationship(back_populates="crops")
    activities: Mapped[list["CropActivity"]] = relationship(back_populates="crop", cascade="all, delete-orphan")


class CropActivity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A logged or scheduled farming action tied to a Crop. Source data for the Farm Timeline."""
    __tablename__ = "crop_activities"

    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type: Mapped[ActivityType] = mapped_column(SAEnum(ActivityType, name="activity_type"), nullable=False)
    status: Mapped[ActivityStatus] = mapped_column(
        SAEnum(ActivityStatus, name="activity_status"), default=ActivityStatus.LOGGED, nullable=False
    )
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=True)
    quantity_unit: Mapped[str] = mapped_column(String(30), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    crop: Mapped["Crop"] = relationship(back_populates="activities")
