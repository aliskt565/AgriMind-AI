"""
Weather service: sits between the API layer and the WeatherProvider,
implementing the caching/staleness behavior described in the roadmap
(Section 17): fetch, cache with a TTL, and if a refresh fails, serve the
last-known snapshot explicitly marked stale rather than silently pretending
it's fresh.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.contracts import WeatherRequestInput
from app.ai.factory import get_weather_provider
from app.models.farm import Field
from app.models.system import WeatherSnapshot

WEATHER_TTL = timedelta(hours=3)


def get_weather_for_field(field: Field, db: Session) -> WeatherSnapshot:
    latest = (
        db.query(WeatherSnapshot)
        .filter(WeatherSnapshot.field_id == field.id)
        .order_by(WeatherSnapshot.fetched_at.desc())
        .first()
    )

    now = datetime.now(timezone.utc)
    is_fresh = latest is not None and (now - latest.fetched_at) < WEATHER_TTL

    if is_fresh:
        return latest

    try:
        provider = get_weather_provider()
        result = provider.get_current(WeatherRequestInput(
            latitude=field.latitude, longitude=field.longitude, location_label=field.name,
        ))
        snapshot = WeatherSnapshot(
            field_id=field.id,
            source=result.source,
            fetched_at=datetime.fromisoformat(result.fetched_at),
            data={
                "temperature_celsius": result.temperature_celsius,
                "humidity_percent": result.humidity_percent,
                "rainfall_mm_last_24h": result.rainfall_mm_last_24h,
                "forecast_summary": result.forecast_summary,
                "extreme_weather_alert": result.extreme_weather_alert,
            },
            is_stale=False,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot
    except Exception:
        # External provider failure: never fabricate fresh data. Serve the
        # last-known snapshot explicitly marked stale, if one exists at all.
        if latest is not None:
            latest.is_stale = True
            db.commit()
            db.refresh(latest)
            return latest
        raise
