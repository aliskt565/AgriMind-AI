from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import get_db
from app.models.user import User, Farmer, UserRole
from app.schemas.auth import FarmerRegisterRequest, TokenResponse, FarmerPublic, UserPublic

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=FarmerPublic, status_code=status.HTTP_201_CREATED)
def register_farmer(payload: FarmerRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.FARMER,
        is_active=True,
        is_email_verified=False,  # verification flow is a Should-Have; not gating access in MVP
    )
    db.add(user)
    db.flush()  # get user.id without committing yet

    farmer = Farmer(
        user_id=user.id,
        full_name=payload.full_name,
        phone=payload.phone,
        location=payload.location,
    )
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return farmer


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    token = create_access_token(subject=str(user.id), role=user.role.value)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
