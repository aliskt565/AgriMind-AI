"""
Farm Risk Engine -- first version, deterministic rules (not ML), per the
roadmap's explicit instruction to start here before any model-based risk
scoring. Risk level and confidence are always two separate fields on the
persisted AIRisk record; this function never collapses them.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.farm import Field, SoilType, IrrigationType
from app.models.crop import Crop, CropActivity
from app.models.health import DiseaseDetection, DetectionResultType
from app.models.ai import AIRisk, RiskType, RiskLevel, ConfidenceLevel, RiskStatus
from app.services.weather_service import get_weather_for_field

ACTIVITY_GAP_DAYS = 14

# Thresholds for weather-driven risk findings. Bounds chosen to match
# MockWeatherProvider's actual generated ranges (temp 18-42C, humidity
# 25-85%, rainfall 0-40mm) so these checks fire meaningfully often during
# demo/testing rather than only on the rare extreme_weather_alert flag.
HEAT_STRESS_TEMP_C = 38.0
HEAVY_RAINFALL_MM = 25.0
LOW_RAINFALL_MM = 3.0
HIGH_HUMIDITY_PERCENT = 75.0
POOR_DRAINAGE_SOIL_TYPES = ("CLAY", "SILTY")


def _upsert_risk(db: Session, *, farm_id, field_id, crop_id, risk_type: RiskType, risk_level: RiskLevel,
                  confidence: ConfidenceLevel, reason: str, supporting_signals: dict, recommended_action: str,
                  signal_key: str | None = None) -> AIRisk:
    """
    Avoid duplicate active risks of the same type for the same entity --
    update the existing active risk in place rather than piling up
    duplicates every time the scan runs. `signal_key` further distinguishes
    concurrent findings that legitimately share the same risk_type (e.g.
    heat stress vs. waterlogging are both WEATHER risks); without it, a
    second weather finding on the same scan would silently overwrite the
    first.
    """
    existing = (
        db.query(AIRisk)
        .filter(
            AIRisk.field_id == field_id,
            AIRisk.crop_id == crop_id,
            AIRisk.risk_type == risk_type,
            AIRisk.signal_key == signal_key,
            AIRisk.status == RiskStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        existing.risk_level = risk_level
        existing.confidence = confidence
        existing.reason = reason
        existing.supporting_signals = supporting_signals
        existing.recommended_action = recommended_action
        return existing

    risk = AIRisk(
        farm_id=farm_id, field_id=field_id, crop_id=crop_id,
        risk_type=risk_type, signal_key=signal_key, risk_level=risk_level, confidence=confidence,
        reason=reason, supporting_signals=supporting_signals,
        recommended_action=recommended_action, status=RiskStatus.ACTIVE,
    )
    db.add(risk)
    # See the identical comment in recommendation_engine.py::_upsert_recommendation
    # -- autoflush=False means later calls in the same scan must not rely on
    # this row being query-visible without an explicit flush.
    db.flush()
    return risk


def evaluate_field_risks(field: Field, db: Session) -> list[AIRisk]:
    """Runs all rule checks for a single field and its crops, persisting/updating AIRisk rows."""
    findings: list[AIRisk] = []
    farm_id = field.farm_id

    # --- Data-quality risk: missing soil/irrigation info degrades every downstream AI capability ---
    if field.soil_type == SoilType.UNKNOWN or field.irrigation_type == IrrigationType.UNKNOWN:
        findings.append(_upsert_risk(
            db, farm_id=farm_id, field_id=field.id, crop_id=None,
            risk_type=RiskType.DATA_QUALITY, risk_level=RiskLevel.MODERATE, confidence=ConfidenceLevel.HIGH,
            reason="Soil type and/or irrigation type is not set for this field, reducing the accuracy of AI Crop Intelligence and other risk checks.",
            supporting_signals={"soil_type": field.soil_type.value, "irrigation_type": field.irrigation_type.value},
            recommended_action="Update the field's soil and irrigation information.",
            signal_key="data_quality",
        ))

    # --- Weather risk ---
    try:
        snapshot = get_weather_for_field(field, db)
        data = snapshot.data or {}
        weather_confidence = ConfidenceLevel.LOW if snapshot.is_stale else ConfidenceLevel.MEDIUM
        weather_signals = {"source": snapshot.source, "fetched_at": snapshot.fetched_at.isoformat(), "is_stale": snapshot.is_stale}

        if data.get("extreme_weather_alert"):
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=None,
                risk_type=RiskType.WEATHER, risk_level=RiskLevel.HIGH,
                confidence=weather_confidence,
                reason=data["extreme_weather_alert"],
                supporting_signals=weather_signals,
                recommended_action="Review irrigation and drainage plans for this field ahead of the forecast conditions.",
                signal_key="extreme_alert",
            ))

        # Heat stress: high temperature regardless of irrigation, since even
        # well-irrigated crops can be stressed by sustained heat.
        temperature = data.get("temperature_celsius")
        if temperature is not None and temperature >= HEAT_STRESS_TEMP_C:
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=None,
                risk_type=RiskType.WEATHER, risk_level=RiskLevel.MODERATE,
                confidence=weather_confidence,
                reason=f"Recent temperature ({temperature}°C) is high enough to stress crops during sensitive growth stages.",
                supporting_signals={**weather_signals, "temperature_celsius": temperature},
                recommended_action="Consider adjusting irrigation timing to cooler parts of the day and monitor for heat stress symptoms.",
                signal_key="heat_stress",
            ))

        # Waterlogging: heavy recent rainfall combined with poor-draining
        # soil or an irrigation method that already adds significant water.
        rainfall = data.get("rainfall_mm_last_24h")
        if (
            rainfall is not None and rainfall >= HEAVY_RAINFALL_MM
            and (field.soil_type.value in POOR_DRAINAGE_SOIL_TYPES or field.irrigation_type.value in ("FLOOD", "CANAL"))
        ):
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=None,
                risk_type=RiskType.WEATHER, risk_level=RiskLevel.MODERATE,
                confidence=weather_confidence,
                reason=(
                    f"Recent rainfall ({rainfall}mm/24h) combined with this field's "
                    f"{field.soil_type.value.lower()} soil and {field.irrigation_type.value.lower()} irrigation "
                    "increases waterlogging risk."
                ),
                supporting_signals={**weather_signals, "rainfall_mm_last_24h": rainfall, "soil_type": field.soil_type.value, "irrigation_type": field.irrigation_type.value},
                recommended_action="Check field drainage and consider delaying additional irrigation until soil moisture normalizes.",
                signal_key="waterlogging",
            ))

        # Moisture stress: low recent rainfall on a field with no active
        # irrigation infrastructure to compensate.
        if (
            rainfall is not None and rainfall <= LOW_RAINFALL_MM
            and field.irrigation_type.value in ("RAINFED", "UNKNOWN")
        ):
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=None,
                risk_type=RiskType.WEATHER, risk_level=RiskLevel.MODERATE,
                confidence=weather_confidence,
                reason=f"Recent rainfall ({rainfall}mm/24h) is low, and this field has no active irrigation source to compensate.",
                supporting_signals={**weather_signals, "rainfall_mm_last_24h": rainfall, "irrigation_type": field.irrigation_type.value},
                recommended_action="Plan supplemental irrigation, or monitor crops closely for drought stress.",
                signal_key="moisture_stress",
            ))

        # High humidity: disease-conducive conditions, independent of
        # whether a disease has actually been detected yet.
        humidity = data.get("humidity_percent")
        if humidity is not None and humidity >= HIGH_HUMIDITY_PERCENT:
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=None,
                risk_type=RiskType.WEATHER, risk_level=RiskLevel.LOW,
                confidence=weather_confidence,
                reason=f"Humidity ({humidity}%) is high enough to favor fungal disease development -- worth extra observation.",
                supporting_signals={**weather_signals, "humidity_percent": humidity},
                recommended_action="Inspect crops for early disease symptoms; consider using Plant Vision if anything looks unusual.",
                signal_key="humidity",
            ))
    except Exception:
        # Weather unavailable is not itself a risk finding -- dependent
        # features simply omit the weather-derived signal, per the
        # roadmap's graceful-degradation requirement.
        pass

    # --- Per-crop risks: activity gap + disease ---
    active_crops = [c for c in field.crops if c.stage not in ("HARVESTED", "COMPLETED")]
    for crop in active_crops:
        last_activity = (
            db.query(CropActivity)
            .filter(CropActivity.crop_id == crop.id)
            .order_by(CropActivity.activity_date.desc())
            .first()
        )
        reference_date = last_activity.activity_date if last_activity else crop.planting_date
        if reference_date and (date.today() - reference_date).days >= ACTIVITY_GAP_DAYS:
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=crop.id,
                risk_type=RiskType.ACTIVITY_GAP, risk_level=RiskLevel.MODERATE, confidence=ConfidenceLevel.HIGH,
                reason=f"No activity has been logged for {crop.crop_type} in over {ACTIVITY_GAP_DAYS} days.",
                supporting_signals={"last_activity_date": reference_date.isoformat(), "days_since": (date.today() - reference_date).days},
                recommended_action="Log a recent activity, or verify the crop is being tended as expected.",
                signal_key="activity_gap",
            ))

        latest_detection = (
            db.query(DiseaseDetection)
            .filter(DiseaseDetection.crop_id == crop.id, DiseaseDetection.result_type == DetectionResultType.HIGH_CONFIDENCE)
            .order_by(DiseaseDetection.created_at.desc())
            .first()
        )
        if latest_detection:
            findings.append(_upsert_risk(
                db, farm_id=farm_id, field_id=field.id, crop_id=crop.id,
                risk_type=RiskType.DISEASE, risk_level=RiskLevel.HIGH, confidence=ConfidenceLevel.HIGH,
                reason=f"A high-confidence disease detection ({latest_detection.predicted_disease}) exists for {crop.crop_type}.",
                supporting_signals={"detection_id": str(latest_detection.id), "confidence": latest_detection.confidence},
                recommended_action="Review the Plant Vision result and consider consulting an agricultural expert.",
                signal_key="disease",
            ))

    db.commit()
    return findings
