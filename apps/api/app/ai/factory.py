"""
Factory: the ONLY place in the codebase that knows which concrete provider
implementation is active. Endpoints depend on `get_crop_intelligence_provider`
/ `get_plant_vision_provider`, never on a concrete class -- this is what
makes swapping mock -> real a non-breaking change.
"""
from app.core.config import get_settings
from app.ai.base import CropIntelligenceProvider, PlantVisionProvider, WeatherProvider, CopilotProvider
from app.ai.mock_crop_intelligence import MockCropIntelligenceProvider
from app.ai.mock_plant_vision import MockPlantVisionProvider
from app.ai.mock_weather import MockWeatherProvider
from app.ai.mock_copilot import MockCopilotProvider


def get_crop_intelligence_provider() -> CropIntelligenceProvider:
    settings = get_settings()
    if settings.AI_MODE == "real":
        # A real implementation would be imported and returned here once a
        # trained model / inference service exists. Deliberately not stubbed
        # further than this -- there is nothing to fall back to silently.
        raise NotImplementedError(
            "AI_MODE=real is not yet wired to a real Crop Intelligence model. "
            "Set AI_MODE=mock, or implement a real provider before enabling this."
        )
    return MockCropIntelligenceProvider()


def get_plant_vision_provider() -> PlantVisionProvider:
    settings = get_settings()
    if settings.AI_MODE == "real":
        raise NotImplementedError(
            "AI_MODE=real is not yet wired to a real Plant Vision model. "
            "Set AI_MODE=mock, or implement a real provider before enabling this."
        )
    return MockPlantVisionProvider()


def get_weather_provider() -> WeatherProvider:
    settings = get_settings()
    if settings.WEATHER_PROVIDER == "real":
        raise NotImplementedError(
            "WEATHER_PROVIDER=real is not yet wired to a real weather API. "
            "Set WEATHER_PROVIDER=mock, or implement RealWeatherProvider before enabling this."
        )
    return MockWeatherProvider()


def get_copilot_provider() -> CopilotProvider:
    settings = get_settings()
    if settings.COPILOT_PROVIDER == "real":
        raise NotImplementedError(
            "COPILOT_PROVIDER=real is not yet wired to a real LLM provider. "
            "Set COPILOT_PROVIDER=mock, or implement a RealCopilotProvider (see app/ai/base.py::CopilotProvider) "
            "before enabling this. When implemented, it should read COPILOT_LLM_API_KEY / COPILOT_LLM_MODEL_NAME "
            "from settings -- never hard-code credentials."
        )
    return MockCopilotProvider()
