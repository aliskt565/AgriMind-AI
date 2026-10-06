import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class NotificationType(str, enum.Enum):
    RECOMMENDATION_GENERATED = "RECOMMENDATION_GENERATED"
    RISK_DETECTED = "RISK_DETECTED"
    ACTIVITY_DUE = "ACTIVITY_DUE"
    ACTIVITY_OVERDUE = "ACTIVITY_OVERDUE"
    AI_RESULT_COMPLETED = "AI_RESULT_COMPLETED"
    DISEASE_DETECTED = "DISEASE_DETECTED"


class NotificationPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType, name="notification_type"), nullable=False)
    priority: Mapped[NotificationPriority] = mapped_column(
        SAEnum(NotificationPriority, name="notification_priority"), default=NotificationPriority.MEDIUM, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_type: Mapped[str] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=True, index=True)


class WeatherSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Cached external weather data for a Field. `source` and `fetched_at` are
    always shown alongside displayed weather so staleness is never hidden
    from the farmer, per the roadmap's Weather Intelligence requirements.
    """
    __tablename__ = "weather_snapshots"

    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class FarmTimelineEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Unified chronological record aggregating activities, detections,
    predictions, recommendations, weather alerts, stage changes, and harvest
    events for a single farm/field/crop timeline view.
    """
    __tablename__ = "farm_timeline_events"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=True, index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin/system audit trail. Never stores raw secrets or unnecessary sensitive data."""
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(50), nullable=True)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
