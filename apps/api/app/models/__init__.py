"""
Import every ORM model here so that:
1. `Base.metadata` is fully populated for Alembic autogenerate.
2. Application code can do `from app.models import User, Farm, ...`.
"""
from app.models.user import User, Farmer, Admin, UserRole, AdminTier  # noqa: F401
from app.models.farm import Farm, Field, FarmStatus, FieldStatus, SoilType, IrrigationType  # noqa: F401
from app.models.crop import (  # noqa: F401
    Crop, CropActivity, CropStage, CropSource, HealthStatus, ActivityType, ActivityStatus,
)
from app.models.health import CropHealthRecord, DiseaseDetection, DetectionResultType  # noqa: F401
from app.models.ai import (  # noqa: F401
    AIPrediction, PredictionStatus,
    AIRisk, RiskType, RiskLevel, ConfidenceLevel, RiskStatus,
    AIRecommendation, RecommendationCategory, RecommendationPriority, RecommendationStatus,
)
from app.models.system import (  # noqa: F401
    Notification, NotificationType, NotificationPriority,
    WeatherSnapshot, FarmTimelineEvent, AuditLog,
)
from app.models.copilot import CopilotConversation, CopilotMessage, MessageRole  # noqa: F401
