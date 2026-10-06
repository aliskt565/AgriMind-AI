import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.ai import AIRecommendation, RecommendationStatus

router = APIRouter(prefix="/recommendations", tags=["Recommendation Engine"])


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID | None
    field_id: uuid.UUID | None
    crop_id: uuid.UUID | None
    category: str
    priority: str
    status: str
    text: str
    trigger_reason: str

    model_config = {"from_attributes": True}


@router.post("/generate", response_model=list[RecommendationResponse])
def generate_recommendations(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    from app.services.recommendation_engine import generate_recommendations_for_farmer
    return generate_recommendations_for_farmer(farmer.id, db)


@router.get("", response_model=list[RecommendationResponse])
def list_recommendations(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    return (
        db.query(AIRecommendation)
        .filter(AIRecommendation.farmer_id == farmer.id, AIRecommendation.status == RecommendationStatus.ACTIVE)
        .order_by(AIRecommendation.created_at.desc())
        .all()
    )


@router.post("/{recommendation_id}/dismiss", response_model=RecommendationResponse)
def dismiss_recommendation(recommendation_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    rec = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.id == recommendation_id, AIRecommendation.farmer_id == farmer.id)
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    rec.status = RecommendationStatus.DISMISSED
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/{recommendation_id}/complete", response_model=RecommendationResponse)
def complete_recommendation(recommendation_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    rec = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.id == recommendation_id, AIRecommendation.farmer_id == farmer.id)
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    rec.status = RecommendationStatus.COMPLETED
    db.commit()
    db.refresh(rec)
    return rec
