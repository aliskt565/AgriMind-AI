import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_farmer, get_current_user
from app.db.session import get_db
from app.models.user import Farmer, User
from app.models.farm import Farm, Field
from app.models.ai import AIPrediction, PredictionStatus
from app.schemas.ai import CropIntelligenceRequest, CropIntelligenceResponse, CropCandidateOut
from app.ai.contracts import CropIntelligenceInput
from app.ai.factory import get_crop_intelligence_provider
from app.core.config import get_settings
from app.services.weather_service import get_weather_for_field
from app.models.crop import Crop

router = APIRouter(prefix="/ai/crop-intelligence", tags=["AI Crop Intelligence"])


def _get_owned_field_or_404(field_id: uuid.UUID, farmer: Farmer, db: Session) -> Field:
    field = (
        db.query(Field)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Field.id == field_id, Farm.farmer_id == farmer.id)
        .first()
    )
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return field


@router.post("/fields/{field_id}", response_model=CropIntelligenceResponse, status_code=status.HTTP_201_CREATED)
def request_crop_prediction(
    field_id: uuid.UUID,
    payload: CropIntelligenceRequest,
    farmer: Farmer = Depends(require_farmer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs the AI Crop Intelligence contract for a field and persists the
    result. Currently always backed by the MOCK provider (AI_MODE=mock) --
    every response is explicitly labeled `is_mock: true` so the frontend
    never has to guess.
    """
    field = _get_owned_field_or_404(field_id, farmer, db)
    settings = get_settings()

    # Real weather context, when available -- previously this was never
    # populated, which silently degraded every prediction's confidence and
    # assumptions text even though the Weather Intelligence service already
    # has current data for this field. Weather being unavailable is not
    # fatal to the request; the provider already degrades gracefully when
    # weather_context is None (see MockCropIntelligenceProvider).
    weather_context = None
    try:
        snapshot = get_weather_for_field(field, db)
        weather_context = {
            "temperature_celsius": (snapshot.data or {}).get("temperature_celsius"),
            "humidity_percent": (snapshot.data or {}).get("humidity_percent"),
            "rainfall_mm_last_24h": (snapshot.data or {}).get("rainfall_mm_last_24h"),
            "is_stale": snapshot.is_stale,
        }
    except Exception:
        pass

    # Rotation history: the field's own past crops (most recent first,
    # excluding any still-active crop), giving the provider genuine
    # multi-season context rather than only the single most-recent crop.
    past_crops = (
        db.query(Crop)
        .filter(Crop.field_id == field_id, Crop.stage.in_(["HARVESTED", "COMPLETED"]))
        .order_by(Crop.created_at.desc())
        .limit(5)
        .all()
    )
    rotation_history = [c.crop_type for c in past_crops]

    provider_input = CropIntelligenceInput(
        soil_type=field.soil_type.value,
        irrigation_type=field.irrigation_type.value,
        season=payload.season,
        location=field.farm.location if field.farm else None,
        field_size_acres=field.area_acres,
        previous_crop=payload.previous_crop or (rotation_history[0] if rotation_history else None),
        rotation_history=rotation_history,
        weather_context=weather_context,
        farmer_constraints=payload.farmer_constraints,
    )

    inputs_json = {
        "soil_type": provider_input.soil_type,
        "irrigation_type": provider_input.irrigation_type,
        "season": provider_input.season,
        "field_size_acres": provider_input.field_size_acres,
        "previous_crop": provider_input.previous_crop,
        "rotation_history": provider_input.rotation_history,
        "weather_context": provider_input.weather_context,
        "farmer_constraints": provider_input.farmer_constraints,
    }

    try:
        provider = get_crop_intelligence_provider()
        result = provider.predict(provider_input)
        status_value = PredictionStatus.COMPLETED
    except Exception:
        # AI failures must never become fabricated successful results --
        # persist the failure explicitly rather than swallowing it.
        prediction = AIPrediction(
            field_id=field_id, requested_by_user_id=current_user.id,
            status=PredictionStatus.FAILED, inputs=inputs_json, results=None,
        )
        db.add(prediction)
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Crop Intelligence service is unavailable. Please try again.")

    results_json = {
        "candidates": [
            {
                "crop_type": c.crop_type,
                "suitability_score": c.suitability_score,
                "confidence": c.confidence.value,
                "explanation": c.explanation,
                "limiting_factors": c.limiting_factors,
                "risk_note": c.risk_note,
            }
            for c in result.candidates
        ],
        "important_assumptions": result.important_assumptions,
    }

    prediction = AIPrediction(
        field_id=field_id,
        requested_by_user_id=current_user.id,
        status=status_value,
        inputs=inputs_json,
        results=results_json,
        model_name=result.model_name,
        model_version=result.model_version,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return CropIntelligenceResponse(
        id=prediction.id,
        field_id=field_id,
        candidates=[CropCandidateOut(**c) for c in results_json["candidates"]],
        important_assumptions=result.important_assumptions,
        model_name=result.model_name,
        model_version=result.model_version,
        is_mock=(settings.AI_MODE == "mock"),
    )


@router.get("/fields/{field_id}/history", response_model=list[CropIntelligenceResponse])
def get_prediction_history(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    _get_owned_field_or_404(field_id, farmer, db)
    settings = get_settings()
    predictions = (
        db.query(AIPrediction)
        .filter(AIPrediction.field_id == field_id, AIPrediction.status == PredictionStatus.COMPLETED)
        .order_by(AIPrediction.created_at.desc())
        .all()
    )
    return [
        CropIntelligenceResponse(
            id=p.id,
            field_id=field_id,
            candidates=[CropCandidateOut(**c) for c in (p.results or {}).get("candidates", [])],
            important_assumptions=(p.results or {}).get("important_assumptions", []),
            model_name=p.model_name,
            model_version=p.model_version,
            is_mock=(settings.AI_MODE == "mock"),
        )
        for p in predictions
    ]
