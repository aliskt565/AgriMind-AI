import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.farm import Farm, Field
from app.services.weather_service import get_weather_for_field

router = APIRouter(prefix="/weather", tags=["Weather Intelligence"])


class WeatherResponse(BaseModel):
    field_id: uuid.UUID
    source: str
    fetched_at: str
    is_stale: bool
    temperature_celsius: float | None
    humidity_percent: float | None
    rainfall_mm_last_24h: float | None
    forecast_summary: str | None
    extreme_weather_alert: str | None


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


@router.get("/fields/{field_id}", response_model=WeatherResponse)
def get_field_weather(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    field = _get_owned_field_or_404(field_id, farmer, db)
    try:
        snapshot = get_weather_for_field(field, db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Weather data is currently unavailable.")

    data = snapshot.data or {}
    return WeatherResponse(
        field_id=field_id,
        source=snapshot.source,
        fetched_at=snapshot.fetched_at.isoformat(),
        is_stale=snapshot.is_stale,
        temperature_celsius=data.get("temperature_celsius"),
        humidity_percent=data.get("humidity_percent"),
        rainfall_mm_last_24h=data.get("rainfall_mm_last_24h"),
        forecast_summary=data.get("forecast_summary"),
        extreme_weather_alert=data.get("extreme_weather_alert"),
    )
