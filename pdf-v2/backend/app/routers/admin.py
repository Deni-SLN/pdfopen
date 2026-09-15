from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path
from datetime import datetime, timezone, timedelta
from ..database import get_db
from ..deps import require_admin
from ..models import User, Job, File as FileModel, AuditLog, SystemSetting
from ..config import settings
from ..storage import ROOT
import shutil

router=APIRouter(prefix="/api/admin", tags=["admin"])

def _period_cutoff(period: str):
    now=datetime.now(timezone.utc)
    if period=="1d": return now - timedelta(days=1)
    if period=="7d": return now - timedelta(days=7)
    if period=="30d" or period=="1m": return now - timedelta(days=30)
    if period=="1y": return now - timedelta(days=365)
    return None

@router.get("/stats")
def stats(period: str = Query("all"), admin=Depends(require_admin), db: Session=Depends(get_db)):
    cutoff=_period_cutoff(period)
    total_users=db.query(User).count()
    active=db.query(User).filter(User.is_active==True).count()
    q_jobs=db.query(Job)
    q_files=db.query(FileModel)
    if cutoff:
        q_jobs=q_jobs.filter(Job.created_at>=cutoff)
        q_files=q_files.filter(FileModel.created_at>=cutoff)
    jobs_cnt=q_jobs.count()
    failed=q_jobs.filter(Job.status=="failed").count()
    completed=q_jobs.filter(Job.status=="completed").count()
    files_cnt=q_files.count()
    total_bytes=db.query(func.coalesce(func.sum(FileModel.size),0)).filter(FileModel.created_at>=cutoff if cutoff else True).scalar() or 0
    # also from filesystem
    fs_size=0
    for p in ROOT.rglob("*"):
        if p.is_file(): fs_size+=p.stat().st_size
    # retention setting
    retention=getattr(settings,"RETENTION_HOURS",1)
    # try system_settings override
    sv=db.query(SystemSetting).filter(SystemSetting.key=="retention_hours").first()
    if sv: 
        try: retention=int(sv.value)
        except: pass
    return {"total_users":total_users,"active_users":active,"jobs_today":jobs_cnt,"jobs_completed":completed,"failed_jobs":failed,"files_count":files_cnt,"total_bytes":int(total_bytes),"storage_bytes":fs_size,"retention_hours":retention,"period":period}

@router.get("/jobs")
def admin_jobs(admin=Depends(require_admin), db: Session=Depends(get_db)):
    return db.query(Job).order_by(Job.created_at.desc()).limit(100).all()

@router.get("/storage")
def storage(admin=Depends(require_admin)):
    info=[]
    for sub in ["uploads","processing","results"]:
        p=ROOT/sub
        count=len(list(p.iterdir())) if p.exists() else 0
        sz=sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
        info.append({"dir":sub,"files":count,"bytes":sz})
    return info

@router.get("/audit")
def audit(admin=Depends(require_admin), db: Session=Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()

@router.get("/settings")
def get_settings(admin=Depends(require_admin), db: Session=Depends(get_db)):
    rows=db.query(SystemSetting).all()
    return {r.key:r.value for r in rows}

@router.post("/settings")
def save_settings(payload: dict, admin=Depends(require_admin), db: Session=Depends(get_db)):
    # payload: {"retention_hours":1, "max_file_mb":100}
    for k,v in payload.items():
        r=db.query(SystemSetting).filter(SystemSetting.key==k).first()
        if r: r.value=str(v)
        else: db.add(SystemSetting(key=k, value=str(v)))
    db.commit()
    db.add(AuditLog(actor_id=admin.id, action="update_settings", detail=str(payload))); db.commit()
    return {"ok":True}

@router.post("/cleanup")
def cleanup(admin=Depends(require_admin), db: Session=Depends(get_db)):
    from ..storage import cleanup_expired
    sv=db.query(SystemSetting).filter(SystemSetting.key=="retention_hours").first()
    hours=int(sv.value) if sv and sv.value.isdigit() else settings.RETENTION_HOURS
    cleanup_expired(hours)
    return {"ok":True, "retention_hours":hours}
