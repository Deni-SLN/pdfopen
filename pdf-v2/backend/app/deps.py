from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .database import get_db
from .auth import decode_token
from .models import User

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ",1)[1]
    try:
        payload = decode_token(token)
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == uid).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user

def require_admin(user: User = Depends(get_current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "Admin required")
    return user
