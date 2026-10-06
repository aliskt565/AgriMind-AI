"""
Authorization dependencies.

Every protected endpoint depends on `get_current_user` (or a role-specific
variant). Ownership of farm/field/crop resources is checked explicitly in
each endpoint against the authenticated farmer's own ID -- never trusted
from a client-supplied ID. This is the server-side enforcement the roadmap
requires; the frontend never gets to decide access on its own.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, Farmer, Admin, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_farmer(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Farmer:
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmer role required")
    farmer = db.query(Farmer).filter(Farmer.user_id == current_user.id).first()
    if farmer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer profile not found")
    return farmer


def require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Admin:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    admin = db.query(Admin).filter(Admin.user_id == current_user.id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin profile not found")
    return admin


def require_super_admin(admin: Admin = Depends(require_admin)) -> Admin:
    from app.models.user import AdminTier
    if admin.tier != AdminTier.SUPER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin tier required")
    return admin
