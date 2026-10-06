from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.farm import Farm, Field
from app.models.crop import Crop
from app.models.ai import AIRisk, RiskStatus, AIRecommendation, RecommendationStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardSummary(BaseModel):
    farm_count: int
    field_count: int
    active_crop_count: int
    active_risk_count: int
    active_recommendation_count: int


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    """
    Every number here answers 'what is the current state of my farm' or
    'what needs my attention' -- per the roadmap's dashboard design rule,
    nothing decorative is included.
    """
    farm_count = db.query(func.count(Farm.id)).filter(Farm.farmer_id == farmer.id).scalar() or 0

    field_count = (
        db.query(func.count(Field.id))
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer.id)
        .scalar()
        or 0
    )

    active_crop_count = (
        db.query(func.count(Crop.id))
        .join(Field, Crop.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer.id)
        .scalar()
        or 0
    )

    active_risk_count = (
        db.query(func.count(AIRisk.id))
        .join(Farm, AIRisk.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer.id, AIRisk.status == RiskStatus.ACTIVE)
        .scalar()
        or 0
    )

    active_recommendation_count = (
        db.query(func.count(AIRecommendation.id))
        .filter(AIRecommendation.farmer_id == farmer.id, AIRecommendation.status == RecommendationStatus.ACTIVE)
        .scalar()
        or 0
    )

    return DashboardSummary(
        farm_count=farm_count,
        field_count=field_count,
        active_crop_count=active_crop_count,
        active_risk_count=active_risk_count,
        active_recommendation_count=active_recommendation_count,
    )
