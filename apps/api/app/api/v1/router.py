from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, farms, fields, crops, dashboard, ai_crop_intelligence, ai_plant_vision,
    weather, risk, recommendations, copilot,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(farms.router)
api_router.include_router(fields.router)
api_router.include_router(crops.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai_crop_intelligence.router)
api_router.include_router(ai_plant_vision.router)
api_router.include_router(weather.router)
api_router.include_router(risk.router)
api_router.include_router(recommendations.router)
api_router.include_router(copilot.router)
