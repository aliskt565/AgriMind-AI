import uuid

from pydantic import BaseModel, Field, field_validator

from app.models.farm import FarmStatus, FieldStatus, SoilType, IrrigationType
from app.schemas.crop import CropPublic


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    total_area_acres: float | None = Field(default=None, ge=0)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    total_area_acres: float | None = Field(default=None, ge=0)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: FarmStatus | None = None


class FarmPublic(BaseModel):
    id: uuid.UUID
    name: str
    total_area_acres: float | None
    location: str | None
    latitude: float | None
    longitude: float | None
    status: FarmStatus
    field_count: int = 0

    model_config = {"from_attributes": True}


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    area_acres: float | None = Field(default=None, ge=0)
    soil_type: SoilType = SoilType.UNKNOWN
    irrigation_type: IrrigationType = IrrigationType.UNKNOWN
    latitude: float | None = None
    longitude: float | None = None
    # Initial crop TYPES (e.g. "Wheat", "Rice") to plant in this field
    # immediately on creation -- NOT existing crop IDs. Crops in this system
    # are always instance records permanently owned by the field they were
    # created under (see Crop.field_id, NOT NULL + CASCADE), so there is no
    # concept of a reusable "crop entity" that could be selected from
    # elsewhere and attached here. Each entry becomes a brand-new Crop row
    # scoped to this field -- which also means there is no cross-tenant
    # attachment surface to defend against here by construction.
    initial_crop_types: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("initial_crop_types")
    @classmethod
    def _validate_crop_types(cls, value: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for raw in value:
            trimmed = raw.strip()
            if not trimmed:
                raise ValueError("Crop type cannot be blank.")
            if len(trimmed) > 120:
                raise ValueError("Crop type is too long.")
            key = trimmed.lower()
            if key in seen:
                continue  # silently dedupe rather than reject -- not worth failing the whole request over
            seen.add(key)
            cleaned.append(trimmed)
        return cleaned


class FieldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    area_acres: float | None = Field(default=None, ge=0)
    soil_type: SoilType | None = None
    irrigation_type: IrrigationType | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: FieldStatus | None = None


class FieldPublic(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    name: str
    area_acres: float | None
    soil_type: SoilType
    irrigation_type: IrrigationType
    status: FieldStatus
    crop_count: int = 0
    crops: list[CropPublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}
