import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.crop import CropStage, CropSource, HealthStatus, ActivityType, ActivityStatus


class CropCreate(BaseModel):
    crop_type: str = Field(min_length=1, max_length=120)
    variety: str | None = None
    planting_date: date | None = None
    expected_harvest_date: date | None = None
    notes: str | None = None


class CropUpdate(BaseModel):
    stage: CropStage | None = None
    health_status: HealthStatus | None = None
    planting_date: date | None = None
    expected_harvest_date: date | None = None
    actual_harvest_date: date | None = None
    actual_yield: float | None = Field(default=None, ge=0)
    yield_unit: str | None = None
    notes: str | None = None


class CropPublic(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    crop_type: str
    variety: str | None
    stage: CropStage
    source: CropSource
    health_status: HealthStatus
    planting_date: date | None
    expected_harvest_date: date | None
    actual_harvest_date: date | None
    actual_yield: float | None
    yield_unit: str | None
    notes: str | None

    model_config = {"from_attributes": True}


class CropActivityCreate(BaseModel):
    activity_type: ActivityType
    activity_date: date
    quantity: float | None = Field(default=None, ge=0)
    quantity_unit: str | None = None
    notes: str | None = None
    status: ActivityStatus = ActivityStatus.LOGGED


class CropActivityPublic(BaseModel):
    id: uuid.UUID
    crop_id: uuid.UUID
    activity_type: ActivityType
    status: ActivityStatus
    activity_date: date
    quantity: float | None
    quantity_unit: str | None
    notes: str | None

    model_config = {"from_attributes": True}
