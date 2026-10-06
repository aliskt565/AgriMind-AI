"""
Recommendation Engine -- first version, trigger-based rules. Every
recommendation persisted here traces to a real signal via `trigger_reason`;
this module never fabricates a recommendation to fill the UI, per the
roadmap's non-negotiable principle.
"""
from sqlalchemy.orm import Session

from app.models.crop import Crop, CropStage
from app.models.ai import (
    AIRisk, RiskStatus, RiskType,
    AIRecommendation, RecommendationCategory, RecommendationPriority, RecommendationStatus,
)


def _upsert_recommendation(db: Session, *, farmer_id, farm_id, field_id, crop_id,
                            category: RecommendationCategory, priority: RecommendationPriority,
                            text: str, trigger_reason: str) -> AIRecommendation:
    existing = (
        db.query(AIRecommendation)
        .filter(
            # CRITICAL: farmer_id must be part of this dedup key. Without it,
            # this query can match -- and silently overwrite -- a DIFFERENT
            # farmer's recommendation whenever crop_id is None (true for
            # every field-level risk: DATA_QUALITY and all WEATHER findings),
            # since crop_id/category/status alone are not farmer-scoped.
            # This was a real, confirmed cross-tenant data integrity bug:
            # one farmer's risk scan silently overwrote another farmer's
            # existing recommendation row instead of creating their own.
            AIRecommendation.farmer_id == farmer_id,
            # field_id closes the same class of bug WITHIN one farmer: two
            # different fields both missing soil/irrigation data both
            # produce a crop_id=None, category=SOIL recommendation: without
            # field_id in the key, the second field's finding would
            # silently overwrite the first field's recommendation.
            AIRecommendation.field_id == field_id,
            AIRecommendation.crop_id == crop_id,
            AIRecommendation.category == category,
            AIRecommendation.status == RecommendationStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        existing.text = text
        existing.trigger_reason = trigger_reason
        existing.priority = priority
        return existing

    rec = AIRecommendation(
        farmer_id=farmer_id, farm_id=farm_id, field_id=field_id, crop_id=crop_id,
        category=category, priority=priority, status=RecommendationStatus.ACTIVE,
        text=text, trigger_reason=trigger_reason,
    )
    db.add(rec)
    # Flush (not commit) immediately: the session is configured with
    # autoflush=False, so without this, a second call to this function
    # later in the SAME request/transaction would not see this pending
    # insert when it runs its own dedup query -- producing duplicate
    # near-identical recommendations instead of an in-place update. This
    # was a real, observed bug: 3 simultaneous weather risks produced 3
    # separate generic recommendations rather than being deduped/merged.
    db.flush()
    return rec


_RISK_TO_RECOMMENDATION = {
    RiskType.ACTIVITY_GAP: (
        RecommendationCategory.CROP_HEALTH, RecommendationPriority.MEDIUM,
        "Log a recent activity or inspect this crop -- it's been a while since anything was recorded.",
    ),
    RiskType.DISEASE: (
        RecommendationCategory.DISEASE_PREVENTION, RecommendationPriority.HIGH,
        "Review the recent disease detection and consider isolating affected plants until confirmed by an expert.",
    ),
    RiskType.DATA_QUALITY: (
        RecommendationCategory.SOIL, RecommendationPriority.LOW,
        "Fill in soil and irrigation details for this field to improve AI recommendation accuracy.",
    ),
}

# Weather risks all share RiskType.WEATHER, but the underlying conditions
# (heat stress, waterlogging, moisture stress, humidity, an extreme alert)
# call for genuinely different advice. Mapping by `signal_key` instead of
# the flat risk_type keeps each condition's recommendation accurate and
# gives each a distinct category, which also means the existing
# (crop_id, category, status) dedup key in _upsert_recommendation naturally
# keeps them as separate, non-duplicating recommendations -- no recommendation
# spam, because waterlogging and moisture stress are mutually exclusive by
# threshold definition and can never both be active for the same field at once.
_WEATHER_SIGNAL_TO_RECOMMENDATION = {
    "heat_stress": (
        RecommendationCategory.CROP_HEALTH, RecommendationPriority.MEDIUM,
        "Recent temperatures are high enough to stress this crop -- consider irrigating during cooler hours and watch for heat stress symptoms.",
    ),
    "waterlogging": (
        RecommendationCategory.IRRIGATION, RecommendationPriority.MEDIUM,
        "Recent rainfall plus this field's soil/irrigation combination increases waterlogging risk -- check drainage and hold off on additional irrigation.",
    ),
    "moisture_stress": (
        RecommendationCategory.IRRIGATION, RecommendationPriority.MEDIUM,
        "Recent rainfall has been low and this field has no active irrigation source -- plan supplemental watering soon.",
    ),
    "humidity": (
        RecommendationCategory.DISEASE_PREVENTION, RecommendationPriority.LOW,
        "Humidity is high enough to favor fungal disease -- inspect crops closely and consider a Plant Vision check if anything looks unusual.",
    ),
    "extreme_alert": (
        RecommendationCategory.RISK_ALERT, RecommendationPriority.HIGH,
        "An extreme weather alert is active for this field -- review your irrigation and drainage plans now.",
    ),
}

_STAGE_RECOMMENDATION = {
    CropStage.MATURITY: (
        RecommendationCategory.HARVEST_TIMING, RecommendationPriority.MEDIUM,
        "This crop has reached maturity -- plan your harvest window soon.",
    ),
}


def generate_recommendations_for_farmer(farmer_id, db: Session) -> list[AIRecommendation]:
    """
    Scans a farmer's active risks and crop stages for real triggers and
    persists/updates the corresponding recommendations. Returns everything
    currently active for the farmer.
    """
    from app.models.farm import Farm

    active_risks = (
        db.query(AIRisk)
        .join(Farm, AIRisk.farm_id == Farm.id)
        .filter(AIRisk.status == RiskStatus.ACTIVE, Farm.farmer_id == farmer_id)
        .all()
    )

    for risk in active_risks:
        mapping = None
        if risk.risk_type == RiskType.WEATHER:
            mapping = _WEATHER_SIGNAL_TO_RECOMMENDATION.get(risk.signal_key)
        else:
            mapping = _RISK_TO_RECOMMENDATION.get(risk.risk_type)

        if mapping is None:
            continue
        category, priority, text = mapping
        # Field-level risks (e.g. DATA_QUALITY, most WEATHER findings) have
        # no crop_id -- the recommendation is still generated, just scoped
        # to the field instead of a specific crop.
        _upsert_recommendation(
            db, farmer_id=farmer_id, farm_id=risk.farm_id, field_id=risk.field_id, crop_id=risk.crop_id,
            category=category, priority=priority, text=text,
            trigger_reason=f"Triggered by active {risk.risk_type.value} risk: {risk.reason}",
        )

    # Stage-based triggers, independent of the risk engine
    from app.models.farm import Field
    crops = (
        db.query(Crop)
        .join(Field, Crop.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer_id)
        .all()
    )
    for crop in crops:
        if crop.stage in _STAGE_RECOMMENDATION:
            category, priority, text = _STAGE_RECOMMENDATION[crop.stage]
            _upsert_recommendation(
                db, farmer_id=farmer_id, farm_id=crop.field.farm_id, field_id=crop.field_id, crop_id=crop.id,
                category=category, priority=priority, text=text,
                trigger_reason=f"Triggered by crop stage: {crop.stage.value}",
            )

    db.commit()

    return (
        db.query(AIRecommendation)
        .filter(AIRecommendation.farmer_id == farmer_id, AIRecommendation.status == RecommendationStatus.ACTIVE)
        .order_by(AIRecommendation.priority.desc(), AIRecommendation.created_at.desc())
        .all()
    )
