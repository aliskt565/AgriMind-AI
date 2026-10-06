import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate, FarmPublic

router = APIRouter(prefix="/farms", tags=["Farms"])


def _to_public(farm: Farm) -> FarmPublic:
    public = FarmPublic.model_validate(farm)
    public.field_count = len(farm.fields)
    return public


def _get_owned_farm_or_404(farm_id: uuid.UUID, farmer: Farmer, db: Session) -> Farm:
    """
    Ownership enforcement: a farm is only returned if it belongs to the
    authenticated farmer. This check happens here, server-side, regardless
    of what the client believes it's allowed to access.
    """
    farm = (
        db.query(Farm)
        .options(joinedload(Farm.fields))
        .filter(Farm.id == farm_id, Farm.farmer_id == farmer.id)
        .first()
    )
    if farm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


@router.post("", response_model=FarmPublic, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    farm = Farm(farmer_id=farmer.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return _to_public(farm)


@router.get("", response_model=list[FarmPublic])
def list_farms(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    farms = (
        db.query(Farm)
        .options(joinedload(Farm.fields))
        .filter(Farm.farmer_id == farmer.id)
        .order_by(Farm.created_at.desc())
        .all()
    )
    return [_to_public(f) for f in farms]


@router.get("/{farm_id}", response_model=FarmPublic)
def get_farm(farm_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    farm = _get_owned_farm_or_404(farm_id, farmer, db)
    return _to_public(farm)


@router.patch("/{farm_id}", response_model=FarmPublic)
def update_farm(
    farm_id: uuid.UUID, payload: FarmUpdate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)
):
    farm = _get_owned_farm_or_404(farm_id, farmer, db)
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(farm, field_name, value)
    db.commit()
    db.refresh(farm)
    return _to_public(farm)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(farm_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    farm = _get_owned_farm_or_404(farm_id, farmer, db)
    db.delete(farm)
    db.commit()
    return None
