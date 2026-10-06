import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_farmer, get_current_user
from app.db.session import get_db
from app.models.user import Farmer, User
from app.models.farm import Farm, Field
from app.models.crop import Crop, CropActivity, ActivityType, ActivityStatus
from app.schemas.crop import CropCreate, CropUpdate, CropPublic, CropActivityCreate, CropActivityPublic

router = APIRouter(tags=["Crops"])


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


def _get_owned_crop_or_404(crop_id: uuid.UUID, farmer: Farmer, db: Session) -> Crop:
    """Ownership chain: Crop -> Field -> Farm -> Farmer. Every hop is checked, not assumed."""
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


@router.post("/fields/{field_id}/crops", response_model=CropPublic, status_code=status.HTTP_201_CREATED)
def create_crop(
    field_id: uuid.UUID, payload: CropCreate, farmer: Farmer = Depends(require_farmer),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_owned_field_or_404(field_id, farmer, db)
    crop = Crop(field_id=field_id, **payload.model_dump())
    db.add(crop)
    db.flush()

    # Planting is a real farming activity -- recording it here (rather than
    # requiring a separate manual log entry) means the Farm Risk Engine has
    # a genuine reference point for activity-gap checks from day one, and a
    # newly created crop with a backdated planting_date doesn't immediately
    # look "neglected" just because no one logged planting separately.
    if crop.planting_date:
        db.add(CropActivity(
            crop_id=crop.id,
            activity_type=ActivityType.PLANTING,
            status=ActivityStatus.LOGGED,
            activity_date=crop.planting_date,
            notes="Automatically logged from crop creation.",
            created_by_user_id=current_user.id,
        ))

    db.commit()
    db.refresh(crop)
    return crop


@router.get("/fields/{field_id}/crops", response_model=list[CropPublic])
def list_crops_for_field(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    _get_owned_field_or_404(field_id, farmer, db)
    return db.query(Crop).filter(Crop.field_id == field_id).order_by(Crop.created_at.desc()).all()


@router.get("/crops", response_model=list[CropPublic])
def list_all_crops(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    """All crops across all of the farmer's farms/fields -- backs the Crops List page."""
    return (
        db.query(Crop)
        .join(Field, Crop.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.farmer_id == farmer.id)
        .order_by(Crop.created_at.desc())
        .all()
    )


@router.get("/crops/{crop_id}", response_model=CropPublic)
def get_crop(crop_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    return _get_owned_crop_or_404(crop_id, farmer, db)


@router.patch("/crops/{crop_id}", response_model=CropPublic)
def update_crop(
    crop_id: uuid.UUID, payload: CropUpdate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)
):
    crop = _get_owned_crop_or_404(crop_id, farmer, db)
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(crop, field_name, value)
    db.commit()
    db.refresh(crop)
    return crop


@router.delete("/crops/{crop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crop(crop_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    crop = _get_owned_crop_or_404(crop_id, farmer, db)
    db.delete(crop)
    db.commit()
    return None


@router.post("/crops/{crop_id}/activities", response_model=CropActivityPublic, status_code=status.HTTP_201_CREATED)
def log_activity(
    crop_id: uuid.UUID,
    payload: CropActivityCreate,
    farmer: Farmer = Depends(require_farmer),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_crop_or_404(crop_id, farmer, db)
    activity = CropActivity(crop_id=crop_id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/crops/{crop_id}/activities", response_model=list[CropActivityPublic])
def list_activities(crop_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    _get_owned_crop_or_404(crop_id, farmer, db)
    return (
        db.query(CropActivity)
        .filter(CropActivity.crop_id == crop_id)
        .order_by(CropActivity.activity_date.desc())
        .all()
    )
