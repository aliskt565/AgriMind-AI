"""
Provider interfaces. `AI_MODE` in settings selects which implementation the
factory in `app/ai/factory.py` returns -- endpoints never import a concrete
provider class directly.
"""
from abc import ABC, abstractmethod

from app.ai.contracts import (
    CropIntelligenceInput, CropIntelligenceResult, PlantVisionInput, PlantVisionResult,
    WeatherRequestInput, WeatherSnapshotResult, CopilotRequest, CopilotResponse,
)


class CropIntelligenceProvider(ABC):
    @abstractmethod
    def predict(self, data: CropIntelligenceInput) -> CropIntelligenceResult:
        ...


class PlantVisionProvider(ABC):
    @abstractmethod
    def analyze(self, data: PlantVisionInput) -> PlantVisionResult:
        ...


class WeatherProvider(ABC):
    @abstractmethod
    def get_current(self, data: WeatherRequestInput) -> WeatherSnapshotResult:
        ...


class CopilotProvider(ABC):
    @abstractmethod
    def respond(self, request: CopilotRequest) -> CopilotResponse:
        ...
