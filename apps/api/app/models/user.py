import enum
import uuid

from sqlalchemy import String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class UserRole(str, enum.Enum):
    FARMER = "FARMER"
    ADMIN = "ADMIN"
    ADVISOR = "ADVISOR"  # reserved for future use per roadmap; not activated in MVP


class AdminTier(str, enum.Enum):
    SUPPORT = "SUPPORT"
    SUPER = "SUPER"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Base account. Every human actor in the system (Farmer, Admin, future
    Advisor) has exactly one User row. Role-specific data lives in the
    related Farmer/Admin profile tables, not on User itself.
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    farmer_profile: Mapped["Farmer"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    admin_profile: Mapped["Admin"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Farmer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Farmer-specific profile. Owns Farms."""
    __tablename__ = "farmers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=True)

    user: Mapped["User"] = relationship(back_populates="farmer_profile")
    farms: Mapped[list["Farm"]] = relationship(back_populates="farmer", cascade="all, delete-orphan")


class Admin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-specific profile, tiered per the roadmap (support vs. super)."""
    __tablename__ = "admins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[AdminTier] = mapped_column(SAEnum(AdminTier, name="admin_tier"), default=AdminTier.SUPPORT, nullable=False)

    user: Mapped["User"] = relationship(back_populates="admin_profile")
