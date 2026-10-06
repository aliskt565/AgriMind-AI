"""
ContextBuilder -- the authorization boundary for the Copilot.

CRITICAL: every query in this module is scoped by `farmer.id`, which comes
from the authenticated session (see app/core/deps.py::require_farmer), NEVER
from any client-supplied ID. This module is the only place that decides what
data the AI provider is allowed to see; the provider itself has no database
access at all, so it structurally cannot leak another farmer's data even if
it wanted to -- it only ever sees what this function hands it.

The context is intentionally compact (capped lists, no raw ORM objects) --
this is NOT a full database dump, per the roadmap's explicit instruction.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.user import Farmer
from app.models.farm import Farm, Field
from app.models.crop import Crop, CropActivity
from app.models.ai import AIRisk, RiskStatus, AIRecommendation, RecommendationStatus
from app.models.system import WeatherSnapshot

MAX_FIELDS = 20
MAX_CROPS = 30
MAX_RISKS = 15
MAX_RECOMMENDATIONS = 15
MAX_ACTIVITIES = 10
RECENT_ACTIVITY_WINDOW_DAYS = 14


def build_farmer_context(farmer: Farmer, db: Session) -> dict:
    """Builds a compact, structured, pre-authorized context for a single farmer."""

    farms = db.query(Farm).filter(Farm.farmer_id == farmer.id).all()
    farm_ids = [f.id for f in farms]

    fields = (
        db.query(Field).filter(Field.farm_id.in_(farm_ids)).limit(MAX_FIELDS).all()
        if farm_ids else []
    )
    field_ids = [f.id for f in fields]
    field_name_by_id = {f.id: f.name for f in fields}
    farm_name_by_id = {f.id: f.name for f in farms}

    crops = (
        db.query(Crop).filter(Crop.field_id.in_(field_ids)).limit(MAX_CROPS).all()
        if field_ids else []
    )
    crop_ids = [c.id for c in crops]
    crop_type_by_id = {c.id: c.crop_type for c in crops}

    active_risks = (
        db.query(AIRisk)
        .filter(AIRisk.farm_id.in_(farm_ids), AIRisk.status == RiskStatus.ACTIVE)
        .order_by(AIRisk.risk_level.desc(), AIRisk.created_at.desc())
        .limit(MAX_RISKS)
        .all()
        if farm_ids else []
    )

    active_recommendations = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.farmer_id == farmer.id, AIRecommendation.status == RecommendationStatus.ACTIVE)
        .order_by(AIRecommendation.priority.desc(), AIRecommendation.created_at.desc())
        .limit(MAX_RECOMMENDATIONS)
        .all()
    )

    since = date.today() - timedelta(days=RECENT_ACTIVITY_WINDOW_DAYS)
    recent_activities = (
        db.query(CropActivity)
        .filter(CropActivity.crop_id.in_(crop_ids), CropActivity.activity_date >= since)
        .order_by(CropActivity.activity_date.desc())
        .limit(MAX_ACTIVITIES)
        .all()
        if crop_ids else []
    )

    weather_snapshots = (
        db.query(WeatherSnapshot).filter(WeatherSnapshot.field_id.in_(field_ids)).all()
        if field_ids else []
    )
    # Keep only the latest snapshot per field
    latest_weather_by_field: dict = {}
    for w in weather_snapshots:
        existing = latest_weather_by_field.get(w.field_id)
        if existing is None or w.fetched_at > existing.fetched_at:
            latest_weather_by_field[w.field_id] = w

    def _field_name_for_crop(crop_field_id):
        return field_name_by_id.get(crop_field_id)

    context = {
        "farmer": {"full_name": farmer.full_name, "location": farmer.location},
        "farms": [{"id": str(f.id), "name": f.name, "field_count": sum(1 for fl in fields if fl.farm_id == f.id)} for f in farms],
        "fields": [
            {
                "id": str(f.id), "name": f.name, "farm_id": str(f.farm_id), "farm_name": farm_name_by_id.get(f.farm_id),
                "soil_type": f.soil_type.value, "irrigation_type": f.irrigation_type.value,
            }
            for f in fields
        ],
        "crops": [
            {
                "id": str(c.id), "field_id": str(c.field_id), "field_name": _field_name_for_crop(c.field_id),
                "crop_type": c.crop_type, "stage": c.stage.value, "health_status": c.health_status.value,
            }
            for c in crops
        ],
        "active_risks": [
            {
                "id": str(r.id), "risk_type": r.risk_type.value, "risk_level": r.risk_level.value,
                "confidence": r.confidence.value, "reason": r.reason,
                "field_name": field_name_by_id.get(r.field_id) if r.field_id else None,
                "crop_type": crop_type_by_id.get(r.crop_id) if r.crop_id else None,
            }
            for r in active_risks
        ],
        "active_recommendations": [
            {
                "id": str(r.id), "category": r.category.value, "priority": r.priority.value, "text": r.text,
                "field_name": field_name_by_id.get(r.field_id) if r.field_id else None,
                "crop_type": crop_type_by_id.get(r.crop_id) if r.crop_id else None,
            }
            for r in active_recommendations
        ],
        "recent_activities": [
            {
                "id": str(a.id), "crop_type": crop_type_by_id.get(a.crop_id), "activity_type": a.activity_type.value,
                "activity_date": a.activity_date.isoformat(),
            }
            for a in recent_activities
        ],
        "weather": [
            {
                "field_name": field_name_by_id.get(field_id),
                "temperature_celsius": (w.data or {}).get("temperature_celsius"),
                "is_stale": w.is_stale,
                "source": w.source,
                "fetched_at": w.fetched_at.isoformat(),
            }
            for field_id, w in latest_weather_by_field.items()
        ],
    }
    return context
