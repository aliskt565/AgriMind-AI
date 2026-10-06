"""Plant Vision endpoints backed by the integrated MobileNetV2 CNN."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.ai import AIRecommendation, AIRisk, RecommendationStatus, RiskStatus
from app.models.crop import Crop, HealthStatus
from app.models.farm import Farm, Field
from app.models.health import DiseaseDetection, DetectionResultType as DBDetectionResultType
from app.models.user import Farmer
from app.schemas.ai import (
    PlantVisionResponse,
    PlantVisionDetectResponse,
    QuickScanResponse,
    TriggeredRecommendation,
)
from app.services.plant_vision_cnn import (
    CNNScanResult,
    CNNScanStatus,
    SUPPORTED_CROP_TYPES,
    scan_image_bytes,
    MODEL_NAME,
    MODEL_VERSION,
)
from app.services.storage import save_upload
from app.ai.contracts import DetectionResultType as ContractDetectionResultType

logger = logging.getLogger("agrimind.plant_vision")
router = APIRouter(prefix="/ai/plant-vision", tags=["AI Plant Vision"])

_HEALTHY_CLASS_SUBSTRINGS = ("healthy",)


def _is_healthy_class(class_name: str | None) -> bool:
    return bool(class_name) and any(s in class_name.lower() for s in _HEALTHY_CLASS_SUBSTRINGS)


def _get_owned_crop_or_404(crop_id: uuid.UUID, farmer: Farmer, db: Session) -> Crop:
    crop = (
        db.query(Crop)
        .join(Field, Crop.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Crop.id == crop_id, Farm.farmer_id == farmer.id)
        .first()
    )
    if crop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found")
    return crop


_HEALTH_ESCALATION = {
    HealthStatus.HEALTHY: HealthStatus.AT_RISK,
    HealthStatus.MONITORING: HealthStatus.AT_RISK,
    HealthStatus.AT_RISK: HealthStatus.DISEASED,
    HealthStatus.DISEASED: HealthStatus.DISEASED,
}


def _escalate_health(crop: Crop) -> bool:
    new_status = _HEALTH_ESCALATION.get(crop.health_status)
    if new_status is None or new_status == crop.health_status:
        return False
    crop.health_status = new_status
    return True


def _cnn_to_contract(result: CNNScanResult, crop_type: str):
    """Map the shared CNN result into the stable Plant Vision DB/API contract."""
    from app.ai.contracts import DetectionResultType, PlantVisionResult

    if result.status == CNNScanStatus.ERROR:
        return PlantVisionResult(
            result_type=DetectionResultType.SERVICE_FAILURE,
            predicted_disease=None,
            confidence=None,
            symptoms_matched=None,
            guidance_text=None,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason=result.message,
        )

    if result.status == CNNScanStatus.UNSUPPORTED_CROP:
        return PlantVisionResult(
            result_type=DetectionResultType.UNSUPPORTED_CROP,
            predicted_disease=None,
            confidence=None,
            symptoms_matched=None,
            guidance_text=None,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason=result.rejection_reason or result.message,
        )

    if result.predicted_class is None:
        return PlantVisionResult(
            result_type=DetectionResultType.REJECTED_LOW_QUALITY,
            predicted_disease=None,
            confidence=(result.confidence_percent / 100.0) if result.confidence_percent else None,
            symptoms_matched=None,
            guidance_text=None,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason=result.rejection_reason or result.message,
        )

    confidence = result.confidence_percent / 100.0

    if result.crop_mismatch:
        return PlantVisionResult(
            result_type=DetectionResultType.UNSUPPORTED_CROP,
            predicted_disease=result.predicted_class,
            confidence=confidence,
            symptoms_matched=None,
            guidance_text="The image prediction belongs to a different crop family than this crop record.",
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason=result.mismatch_detail,
        )

    if result.status == CNNScanStatus.REJECTED:
        rejection_type = (
            DetectionResultType.REJECTED_NON_PLANT
            if "plant leaf" in result.message.lower() or "plant" in result.message.lower()
            else DetectionResultType.REJECTED_LOW_QUALITY
        )
        return PlantVisionResult(
            result_type=rejection_type,
            predicted_disease=result.predicted_class,
            confidence=confidence if result.confidence_percent else None,
            symptoms_matched=None,
            guidance_text=None,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason=result.message,
        )

    if not result.is_disease:
        return PlantVisionResult(
            result_type=DetectionResultType.HEALTHY,
            predicted_disease=result.predicted_class,
            confidence=confidence,
            symptoms_matched="No disease class detected by the V2 CNN.",
            guidance_text="The uploaded image was classified as healthy by the current V2 CNN model.",
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
        )

    if result.ood_state == "LOW_CONFIDENCE":
        return PlantVisionResult(
            result_type=DetectionResultType.LOW_CONFIDENCE,
            predicted_disease=result.predicted_class,
            confidence=confidence,
            symptoms_matched="Visual pattern matched a V2 trained class, but confidence is below the high-confidence guidance threshold.",
            guidance_text="Treat this as a low-confidence AI screening result and confirm the crop/disease before taking action.",
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
            rejection_reason="Model confidence is below the high-confidence threshold.",
        )

    return PlantVisionResult(
        result_type=DetectionResultType.HIGH_CONFIDENCE,
        predicted_disease=result.predicted_class,
        confidence=confidence,
        symptoms_matched="Visual pattern matched a trained disease class.",
        guidance_text=(
            f"The CNN detected {result.predicted_class} in the {crop_type} image. "
            "Treat this as an AI screening result and confirm before treatment decisions."
        ),
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
    )


@router.post("/scan", response_model=QuickScanResponse, status_code=status.HTTP_200_OK)
async def quick_scan(
    file: UploadFile = File(...),
    selected_crop: str = Form(...),
    farmer: Farmer = Depends(require_farmer),
):
    """Run a non-persistent CNN scan with explicit crop context."""
    if selected_crop not in SUPPORTED_CROP_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{selected_crop}' is not a supported crop type. Choose one of: {', '.join(SUPPORTED_CROP_TYPES)}.",
        )
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Please upload an image file.")

    contents = await file.read()
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Image exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit.")

    result = scan_image_bytes(contents, crop_context=selected_crop)
    if result.status == CNNScanStatus.ERROR:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.message)

    return QuickScanResponse(
        status=result.status.value,
        message=result.message,
        selected_crop=selected_crop,
        predicted_class=result.predicted_class,
        confidence_percent=result.confidence_percent,
        is_disease=result.is_disease,
        crop_mismatch=result.crop_mismatch,
        mismatch_message=result.mismatch_detail,
    )


@router.post("/crops/{crop_id}/detect", response_model=PlantVisionDetectResponse, status_code=status.HTTP_201_CREATED)
async def detect_disease(
    crop_id: uuid.UUID,
    image: UploadFile = File(...),
    farmer: Farmer = Depends(require_farmer),
    db: Session = Depends(get_db),
):
    """Run the same real CNN used by Quick Scan, persist the result, and trigger farm intelligence."""
    crop = _get_owned_crop_or_404(crop_id, farmer, db)
    settings = get_settings()

    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Please upload an image file.")

    content = await image.read()
    size_bytes = len(content)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Image exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit.")

    # The CNN is the source of truth for Plant Vision in the merged release.
    result = scan_image_bytes(content, crop_context=crop.crop_type)
    if result.status == CNNScanStatus.ERROR:
        detection = DiseaseDetection(
            crop_id=crop_id,
            image_path="",
            result_type=DBDetectionResultType.SERVICE_FAILURE,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
        )
        db.add(detection)
        db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.message)

    contract_result = _cnn_to_contract(result, crop.crop_type)

    image_path = ""
    if contract_result.result_type != ContractDetectionResultType.REJECTED_LOW_QUALITY:
        try:
            image_path = save_upload(content, image.content_type or "application/octet-stream")
        except Exception:
            logger.warning("Image storage failed for crop_id=%s; continuing without stored image.", crop_id, exc_info=True)

    detection = DiseaseDetection(
        crop_id=crop_id,
        image_path=image_path,
        result_type=DBDetectionResultType(contract_result.result_type.value),
        predicted_disease=contract_result.predicted_disease,
        confidence=contract_result.confidence,
        symptoms_matched=contract_result.symptoms_matched,
        guidance_text=contract_result.guidance_text,
        model_name=contract_result.model_name,
        model_version=contract_result.model_version,
    )
    db.add(detection)
    db.flush()

    health_status_updated = False
    updated_health_status: str | None = None
    new_risk_count = 0
    triggered_recs: list[TriggeredRecommendation] = []

    is_confirmed_disease = (
        contract_result.result_type.value == "HIGH_CONFIDENCE"
        and contract_result.predicted_disease is not None
        and not _is_healthy_class(contract_result.predicted_disease)
        and result.crop_mismatch is False
    )

    if is_confirmed_disease:
        health_status_updated = _escalate_health(crop)
        if health_status_updated:
            updated_health_status = crop.health_status.value

        try:
            from app.services.risk_engine import evaluate_field_risks
            field = db.query(Field).filter(Field.id == crop.field_id).first()
            if field:
                evaluate_field_risks(field, db)
        except Exception:
            logger.exception("Risk engine failed after disease detection for crop_id=%s", crop_id)

        try:
            from app.services.recommendation_engine import generate_recommendations_for_farmer
            generate_recommendations_for_farmer(farmer.id, db)
            triggered_recs = [
                TriggeredRecommendation(
                    id=rec.id,
                    category=rec.category.value,
                    priority=rec.priority.value,
                    text=rec.text,
                )
                for rec in db.query(AIRecommendation)
                .filter(
                    AIRecommendation.farmer_id == farmer.id,
                    AIRecommendation.crop_id == crop_id,
                    AIRecommendation.status == RecommendationStatus.ACTIVE,
                )
                .order_by(AIRecommendation.created_at.desc())
                .limit(5)
                .all()
            ]
        except Exception:
            logger.exception("Recommendation engine failed after disease detection for crop_id=%s", crop_id)

        try:
            new_risk_count = (
                db.query(AIRisk)
                .filter(AIRisk.field_id == crop.field_id, AIRisk.status == RiskStatus.ACTIVE)
                .count()
            )
        except Exception:
            logger.exception("Risk count failed after disease detection for crop_id=%s", crop_id)

    db.commit()
    db.refresh(detection)

    return PlantVisionDetectResponse(
        id=detection.id,
        crop_id=crop_id,
        result_type=detection.result_type.value,
        predicted_disease=detection.predicted_disease,
        confidence=detection.confidence,
        symptoms_matched=detection.symptoms_matched,
        guidance_text=detection.guidance_text,
        rejection_reason=contract_result.rejection_reason,
        model_name=detection.model_name,
        model_version=detection.model_version,
        is_mock=False,
        health_status_updated=health_status_updated,
        updated_health_status=updated_health_status,
        new_risk_count=new_risk_count,
        triggered_recommendations=triggered_recs,
    )


@router.get("/crops/{crop_id}/history", response_model=list[PlantVisionResponse])
def get_detection_history(crop_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    _get_owned_crop_or_404(crop_id, farmer, db)
    detections = (
        db.query(DiseaseDetection)
        .filter(DiseaseDetection.crop_id == crop_id)
        .order_by(DiseaseDetection.created_at.desc())
        .all()
    )
    return [
        PlantVisionResponse(
            id=d.id,
            crop_id=crop_id,
            result_type=d.result_type.value,
            predicted_disease=d.predicted_disease,
            confidence=d.confidence,
            symptoms_matched=d.symptoms_matched,
            guidance_text=d.guidance_text,
            rejection_reason=None,
            model_name=d.model_name,
            model_version=d.model_version,
            is_mock=False,
        )
        for d in detections
    ]
