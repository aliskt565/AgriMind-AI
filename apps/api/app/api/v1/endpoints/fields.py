import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.farm import Farm, Field
from app.models.crop import Crop, CropSource
from app.schemas.farm import FieldCreate, FieldUpdate, FieldPublic
from app.schemas.crop import CropPublic

router = APIRouter(tags=["Fields"])


def _to_public(field: Field) -> FieldPublic:
    public = FieldPublic.model_validate(field)
    public.crop_count = len(field.crops)
    public.crops = [CropPublic.model_validate(c) for c in field.crops]
    return public


def _get_owned_farm_or_404(farm_id: uuid.UUID, farmer: Farmer, db: Session) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id, Farm.farmer_id == farmer.id).first()
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _get_owned_field_or_404(field_id: uuid.UUID, farmer: Farmer, db: Session) -> Field:
    """Ownership is checked by joining through Farm -> Farmer, never trusting a bare field_id."""
    field = (
        db.query(Field)
        .join(Farm, Field.farm_id == Farm.id)
        .options(joinedload(Field.crops))
        .filter(Field.id == field_id, Farm.farmer_id == farmer.id)
        .first()
    )
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    return field


@router.post("/farms/{farm_id}/fields", response_model=FieldPublic, status_code=status.HTTP_201_CREATED)
def create_field(
    farm_id: uuid.UUID, payload: FieldCreate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)
):
    _get_owned_farm_or_404(farm_id, farmer, db)
    data = payload.model_dump()
    initial_crop_types = data.pop("initial_crop_types")

    field = Field(farm_id=farm_id, **data)
    db.add(field)
    db.flush()  # get field.id without committing yet

    # Each selected crop type becomes a brand-new Crop planting scoped to
    # THIS field -- never a reference to an existing crop_id from anywhere
    # else, which is what keeps this free of any cross-tenant attachment risk.
    for crop_type in initial_crop_types:
        db.add(Crop(field_id=field.id, crop_type=crop_type, source=CropSource.MANUAL))

    db.commit()
    db.refresh(field)
    return _to_public(field)


@router.get("/farms/{farm_id}/fields", response_model=list[FieldPublic])
def list_fields(farm_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    _get_owned_farm_or_404(farm_id, farmer, db)
    fields = (
        db.query(Field)
        .options(joinedload(Field.crops))
        .filter(Field.farm_id == farm_id)
        .order_by(Field.created_at.desc())
        .all()
    )
    return [_to_public(f) for f in fields]


@router.get("/fields/{field_id}", response_model=FieldPublic)
def get_field(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    field = _get_owned_field_or_404(field_id, farmer, db)
    return _to_public(field)


@router.patch("/fields/{field_id}", response_model=FieldPublic)
def update_field(
    field_id: uuid.UUID, payload: FieldUpdate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)
):
    field = _get_owned_field_or_404(field_id, farmer, db)
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(field, field_name, value)
    db.commit()
    db.refresh(field)
    return _to_public(field)


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    field = _get_owned_field_or_404(field_id, farmer, db)
    db.delete(field)
    db.commit()
    return None
