import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class FarmerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    location: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    is_email_verified: bool

    model_config = {"from_attributes": True}


class FarmerPublic(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str | None
    location: str | None
    experience_level: str | None
    user: UserPublic

    model_config = {"from_attributes": True}
