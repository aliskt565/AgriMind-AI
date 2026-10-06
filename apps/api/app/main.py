"""AgriMind AI FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_exception_handlers
from app.services.plant_vision_cnn import CNNScanStatus, scan_image_bytes

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

_DEV_ONLY_SECRET_KEY = "CHANGE_ME_IN_PRODUCTION_this_is_a_dev_only_default_secret"
if settings.ENVIRONMENT != "development" and settings.SECRET_KEY == _DEV_ONLY_SECRET_KEY:
    raise RuntimeError(
        "Refusing to start: ENVIRONMENT is not 'development' but SECRET_KEY is still the "
        "default placeholder value. Set a real, random SECRET_KEY in your environment "
        "before running outside local development."
    )

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Smart Agriculture & Farm Intelligence Platform (AgriMind AI) -- Core API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.post("/predict-disease", tags=["AI Prediction"])
async def predict_disease(file: UploadFile = File(...)):
    """Backward-compatible direct CNN endpoint.

    The same shared inference service used by both Quick Scan and crop-specific
    Plant Vision powers this endpoint, so preprocessing and confidence behavior
    cannot drift between product surfaces.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid image file.")

    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.")

    result = scan_image_bytes(contents)
    if result.status == CNNScanStatus.ERROR:
        raise HTTPException(status_code=503, detail=result.message)

    if result.status == CNNScanStatus.REJECTED:
        return {
            "status": "rejected",
            "message": result.message,
            "confidence_score": round(result.confidence_percent, 2),
        }

    return {
        "status": "success",
        "prediction": result.predicted_class,
        "confidence_score": round(result.confidence_percent, 2),
    }


@app.get("/health", tags=["System"])
def health_check():
    """Basic liveness check. The CNN remains lazy-loaded until first inference."""
    from app.services import plant_vision_cnn

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "model_loaded": plant_vision_cnn.is_model_loaded(),
        "plant_vision_model": plant_vision_cnn.MODEL_VERSION,
    }
