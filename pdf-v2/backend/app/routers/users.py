from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, AuditLog
from ..deps import get_current_user, require_admin
from pydantic import BaseModel

router=APIRouter(prefix="/api/users", tags=["users"])

class CreateUser(BaseModel):
    identifier: str
    email: str = None
    username: str = None
    password:str
    role:str="USER"
    quota_daily:int=100
    max_file_mb:int=100

@router.get("")
def list_users(admin: User=Depends(require_admin), db:Session=Depends(get_db)):
    users=db.query(User).all()
    for u in users: u.identifier = u.username or u.email
    return users

@router.post("")
def create_user(data: CreateUser, admin: User=Depends(require_admin), db:Session=Depends(get_db)):
    from ..auth import hash_password
    from sqlalchemy import or_
    ident = (data.identifier or data.username or data.email or "").strip()
    if not ident: raise HTTPException(400,"identifier required")
    if len(data.password)<4: raise HTTPException(400,"Password too short")
    if db.query(User).filter(or_(User.email==ident, User.username==ident.lower(), User.username==ident)).first():
        raise HTTPException(400,"Exists")
    is_email="@" in ident
    if is_email:
        u=User(email=ident, username=None, password_hash=hash_password(data.password), role=data.role, quota_daily=data.quota_daily, max_file_mb=data.max_file_mb)
    else:
        u=User(username=ident.lower(), email=None, password_hash=hash_password(data.password), role=data.role, quota_daily=data.quota_daily, max_file_mb=data.max_file_mb)
    db.add(u); db.commit(); db.refresh(u)
    db.add(AuditLog(actor_id=admin.id, action="create_user", target=u.id, detail=f"create {ident}")); db.commit()
    u.identifier = u.username or u.email
    return u

@router.patch("/{uid}")
def update_user(uid:str, payload:dict, admin:User=Depends(require_admin), db:Session=Depends(get_db)):
    u=db.query(User).filter(User.id==uid).first()
    if not u: raise HTTPException(404,"Not found")
    # allow editing identifier (username/email)
    if "identifier" in payload and payload["identifier"]:
        new_ident=payload["identifier"].strip()
        from sqlalchemy import or_
        # check duplicate
        if new_ident != (u.username or u.email):
            if db.query(User).filter(or_(User.email==new_ident, User.username==new_ident.lower())).filter(User.id!=u.id).first():
                raise HTTPException(400,"Identifier already used")
            if "@" in new_ident:
                u.email=new_ident; u.username=None
            else:
                u.username=new_ident.lower(); u.email=None
    if "email" in payload and payload["email"]:
        u.email=payload["email"]; u.username=None
    if "username" in payload and payload["username"]:
        u.username=payload["username"].lower(); u.email=None
    if "role" in payload: u.role=payload["role"]
    if "is_active" in payload: u.is_active=bool(payload["is_active"])
    if "quota_daily" in payload: u.quota_daily=int(payload["quota_daily"])
    if "max_file_mb" in payload: u.max_file_mb=int(payload["max_file_mb"])
    if "quota" in payload: u.quota_daily=int(payload["quota"])
    if "password" in payload and payload["password"]:
        from ..auth import hash_password
        if len(payload["password"])<4: raise HTTPException(400,"Password too short")
        u.password_hash=hash_password(payload["password"])
        u.must_change_password=False
    db.commit()
    db.refresh(u)
    u.identifier = u.username or u.email
    db.add(AuditLog(actor_id=admin.id, action="update_user", target=u.id, detail=str(payload))); db.commit()
    return u

@router.post("/{uid}/reset-password")
def reset_password(uid:str, admin:User=Depends(require_admin), db:Session=Depends(get_db)):
    u=db.query(User).filter(User.id==uid).first()
    if not u: raise HTTPException(404,"Not found")
    if u.id==admin.id: raise HTTPException(400,"Cannot reset own password")
    from ..auth import hash_password
    u.password_hash=hash_password("12345678")
    u.must_change_password=True
    db.commit()
    db.add(AuditLog(actor_id=admin.id, action="reset_password", target=u.id)); db.commit()
    return {"ok":True, "default":"12345678", "must_change":True}

@router.delete("/{uid}")
def delete_user(uid:str, admin:User=Depends(require_admin), db:Session=Depends(get_db)):
    u=db.query(User).filter(User.id==uid).first()
    if not u: raise HTTPException(404,"Not found")
    if u.id==admin.id: raise HTTPException(400,"Cannot delete self")
    db.delete(u); db.commit()
    db.add(AuditLog(actor_id=admin.id, action="delete_user", target=uid)); db.commit()
    return {"ok":True}

@router.get("/me/profile")
def my_profile(user:User=Depends(get_current_user)):
    return user
