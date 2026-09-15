from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database import get_db
from ..models import User, AuditLog, Job
from ..schemas import RegisterIn, LoginIn, TokenOut, UserOut
from ..auth import hash_password, verify_password, create_token
from ..deps import get_current_user

def _ident(data):
    # identifier may be email, username, or identifier field
    raw = (getattr(data,'identifier',None) or getattr(data,'username',None) or getattr(data,'email',None) or "").strip()
    return raw

def _is_email(s: str): return "@" in s

router=APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session=Depends(get_db)):
    ident = _ident(data)
    if not ident or len(ident)<2: raise HTTPException(400,"Username/email required")
    if len(data.password)<4: raise HTTPException(400,"Password too short")
    is_email = _is_email(ident)
    # check exists on either column
    if db.query(User).filter(or_(User.email==ident, User.username==ident)).first():
        raise HTTPException(400,"Already registered")
    role = "ADMIN" if db.query(User).count()==0 else "USER"
    if is_email:
        u=User(email=ident, username=None, password_hash=hash_password(data.password), role=role)
    else:
        u=User(username=ident.lower(), email=None, password_hash=hash_password(data.password), role=role)
    db.add(u); db.commit(); db.refresh(u)
    token=create_token(u.id)
    # build UserOut compatible dict
    u.identifier = u.username or u.email
    return {"access_token":token,"user":u}

@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session=Depends(get_db)):
    ident = _ident(data)
    if not ident: raise HTTPException(400,"identifier required")
    u=db.query(User).filter(or_(User.email==ident, User.username==ident.lower(), User.username==ident)).first()
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(401,"Invalid credentials")
    if not u.is_active: raise HTTPException(403,"Account disabled")
    import datetime
    u.last_login=datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    u.identifier = u.username or u.email
    token=create_token(u.id)
    return {"access_token":token,"user":u, "must_change_password": bool(getattr(u,'must_change_password', False))}

@router.post("/guest", response_model=TokenOut)
def guest(db: Session=Depends(get_db)):
    """Sesi tamu tanpa login: kuota 5 proses/hari. Token disimpan di browser."""
    import uuid as _uuid
    uname = f"guest-{_uuid.uuid4().hex[:10]}"
    u=User(username=uname, email=None, password_hash=hash_password(_uuid.uuid4().hex),
           role="USER", quota_daily=5, is_active=True, must_change_password=False)
    db.add(u); db.commit(); db.refresh(u)
    token=create_token(u.id)
    u.identifier = u.username
    return {"access_token":token,"user":u}

@router.get("/quota")
def quota(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    from datetime import datetime, timezone
    from sqlalchemy import func
    today=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used=db.query(func.count(Job.id)).filter(Job.owner_id==user.id, Job.created_at>=today).scalar() or 0
    if user.role=="ADMIN":
        return {"role":user.role, "used":int(used), "quota":None, "remaining":None, "unlimited":True}
    q=user.quota_daily or 100
    return {"role":user.role, "used":int(used), "quota":q, "remaining":max(0, q-int(used)), "unlimited":False}

@router.get("/me", response_model=UserOut)
def me(user: User=Depends(get_current_user)):
    user.identifier = user.username or user.email
    return user

@router.post("/logout")
def logout(user: User=Depends(get_current_user)):
    return {"ok":True}

@router.post("/change-password")
def change_password(payload: dict, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    old=payload.get("old_password") or payload.get("current_password") or ""
    new=payload.get("new_password") or payload.get("password") or ""
    if len(new)<8: raise HTTPException(400,"Password baru minimal 8 karakter")
    # if must_change, allow without old check if old is default? but require old
    if not verify_password(old, user.password_hash):
        raise HTTPException(400,"Password lama salah")
    if old==new: raise HTTPException(400,"Password baru harus berbeda")
    user.password_hash=hash_password(new)
    user.must_change_password=False
    db.commit()
    return {"ok":True}

@router.post("/force-change")
def force_change(payload: dict, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    # for first-login after reset: old is 12345678
    new=payload.get("new_password") or ""
    if len(new)<8: raise HTTPException(400,"Minimal 8 karakter")
    if not getattr(user,'must_change_password', False):
        raise HTTPException(400,"Tidak perlu ganti password")
    user.password_hash=hash_password(new)
    user.must_change_password=False
    db.commit()
    return {"ok":True}
