"""
MOCK IMPLEMENTATION -- NOT A REAL WEATHER PROVIDER.

Returns deterministic, contract-shaped weather data so the Risk Engine and
Recommendation Engine can be built and tested against real weather-shaped
signals before an external weather API is integrated. Every response
carries `source="mock-weather"` and a `fetched_at` timestamp so staleness is
never hidden -- the same fields a `RealWeatherProvider` would need to
populate identically.
"""
import random
from datetime import datetime, timezone

from app.ai.base import WeatherProvider
from app.ai.contracts import WeatherRequestInput, WeatherSnapshotResult

_FORECAST_SUMMARIES = [
    "Clear skies expected for the next 3 days.",
    "Light rain expected in the next 48 hours.",
    "Hot and dry conditions expected to continue.",
    "Moderate rainfall expected, favorable for irrigation planning.",
]


class MockWeatherProvider(WeatherProvider):
    def get_current(self, data: WeatherRequestInput) -> WeatherSnapshotResult:
        seed = f"{data.latitude}-{data.longitude}-{data.location_label}-{datetime.now(timezone.utc).date()}"
        rng = random.Random(seed)

        extreme_alert = None
        if rng.random() < 0.12:
            extreme_alert = "Heavy rainfall warning issued for this region in the next 24 hours."

        return WeatherSnapshotResult(
            temperature_celsius=round(rng.uniform(18, 42), 1),
            humidity_percent=round(rng.uniform(25, 85), 1),
            rainfall_mm_last_24h=round(rng.uniform(0, 40), 1),
            forecast_summary=rng.choice(_FORECAST_SUMMARIES),
            extreme_weather_alert=extreme_alert,
            source="mock-weather",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            is_stale=False,
        )
