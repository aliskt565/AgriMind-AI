import enum
import uuid

from sqlalchemy import String, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class FarmStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class FieldStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FALLOW = "FALLOW"


class SoilType(str, enum.Enum):
    LOAMY = "LOAMY"
    CLAY = "CLAY"
    SANDY = "SANDY"
    SILTY = "SILTY"
    PEATY = "PEATY"
    CHALKY = "CHALKY"
    UNKNOWN = "UNKNOWN"


class IrrigationType(str, enum.Enum):
    RAINFED = "RAINFED"
    CANAL = "CANAL"
    TUBEWELL = "TUBEWELL"
    DRIP = "DRIP"
    FLOOD = "FLOOD"
    SPRINKLER = "SPRINKLER"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class Farm(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level property owned by a Farmer. Ownership is enforced at the API layer."""
    __tablename__ = "farms"

    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_area_acres: Mapped[float] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[FarmStatus] = mapped_column(SAEnum(FarmStatus, name="farm_status"), default=FarmStatus.ACTIVE, nullable=False)

    farmer: Mapped["Farmer"] = relationship(back_populates="farms")
    fields: Mapped[list["Field"]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class Field(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A sub-plot within a Farm. This is the primary intelligence unit per the
    roadmap: soil/irrigation/size attributes here drive AI Crop Intelligence
    and the Farm Risk Engine, not the Farm-level record.
    """
    __tablename__ = "fields"

    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    area_acres: Mapped[float] = mapped_column(Float, nullable=True)
    soil_type: Mapped[SoilType] = mapped_column(SAEnum(SoilType, name="soil_type"), default=SoilType.UNKNOWN, nullable=False)
    irrigation_type: Mapped[IrrigationType] = mapped_column(
        SAEnum(IrrigationType, name="irrigation_type"), default=IrrigationType.UNKNOWN, nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[FieldStatus] = mapped_column(SAEnum(FieldStatus, name="field_status"), default=FieldStatus.ACTIVE, nullable=False)

    farm: Mapped["Farm"] = relationship(back_populates="fields")
    crops: Mapped[list["Crop"]] = relationship(back_populates="field", cascade="all, delete-orphan")
