import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.farm import Farm, Field
from app.models.ai import AIRisk, RiskStatus

router = APIRouter(prefix="/risk", tags=["Farm Risk Engine"])


class RiskResponse(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID | None
    field_id: uuid.UUID | None
    crop_id: uuid.UUID | None
    risk_type: str
    risk_level: str
    confidence: str
    reason: str
    recommended_action: str | None
    status: str

    model_config = {"from_attributes": True}


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


@router.post("/fields/{field_id}/scan", response_model=list[RiskResponse])
def scan_field_risks(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    from app.services.risk_engine import evaluate_field_risks
    field = _get_owned_field_or_404(field_id, farmer, db)
    findings = evaluate_field_risks(field, db)
    return findings


@router.get("", response_model=list[RiskResponse])
def list_active_risks(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    return (
        db.query(AIRisk)
        .join(Farm, AIRisk.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer.id, AIRisk.status == RiskStatus.ACTIVE)
        .order_by(AIRisk.created_at.desc())
        .all()
    )


@router.post("/{risk_id}/acknowledge", response_model=RiskResponse)
def acknowledge_risk(risk_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    risk = (
        db.query(AIRisk)
        .join(Farm, AIRisk.farm_id == Farm.id)
        .filter(AIRisk.id == risk_id, Farm.farmer_id == farmer.id)
        .first()
    )
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    risk.status = RiskStatus.ACKNOWLEDGED
    db.commit()
    db.refresh(risk)
    return risk
