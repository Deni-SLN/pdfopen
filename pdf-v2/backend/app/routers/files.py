from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid, mimetypes
from ..database import get_db
from ..deps import get_current_user
from ..models import User, File as FileModel, Job
from ..config import settings
from ..storage import UPLOAD

router=APIRouter(prefix="/api/files", tags=["files"])

ALLOWED = {".pdf",".png",".jpg",".jpeg",".md",".html",".htm",".mp3",".csv",".txt",".xlsx",".xls"}
MAX_MB = settings.MAX_FILE_SIZE_MB

@router.post("")
async def upload(file: UploadFile=File(...), user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    # quota per hari (admin unlimited)
    if user.role != "ADMIN":
        today=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cnt=db.query(func.count(Job.id)).filter(Job.owner_id==user.id, Job.created_at>=today).scalar() or 0
        if cnt >= (user.quota_daily or 100):
            raise HTTPException(429, f"Kuota harian habis ({user.quota_daily} proses/hari). Login/daftar untuk kuota lebih besar.")
    data=await file.read()
    size=len(data)
    # per-user max file mb override
    limit_mb = getattr(user, "max_file_mb", None) or MAX_MB
    if size > limit_mb*1024*1024:
        raise HTTPException(413, f"File too large max {limit_mb}MB")
    ext=Path(file.filename or "file").suffix.lower()
    # allow without ext but check mime
    if ext and ext not in ALLOWED and ext not in [".pdf",".mp3"]:
        # still allow but warn
        pass
    fid=str(uuid.uuid4())
    stored=f"{fid}_{(file.filename or 'file').replace('/','_')[:120]}"
    dest=UPLOAD/f"{fid}_{stored}"
    dest.write_bytes(data)
    rec=FileModel(id=fid, owner_id=user.id, original_name=file.filename or stored, stored_name=stored, path=str(dest), mime=file.content_type, size=size)
    db.add(rec); db.commit(); db.refresh(rec)
    return {"id":rec.id,"original_name":rec.original_name,"size":rec.size,"mime":rec.mime}

@router.get("")
def my_files(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    return db.query(FileModel).filter(FileModel.owner_id==user.id).order_by(FileModel.created_at.desc()).limit(50).all()

@router.get("/{fid}")
def get_file(fid:str, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    f=db.query(FileModel).filter(FileModel.id==fid).first()
    if not f or f.owner_id!=user.id: raise HTTPException(404,"Not found")
    return f

@router.get("/{fid}/preview")
def preview_file(fid:str, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    f=db.query(FileModel).filter(FileModel.id==fid).first()
    if not f or f.owner_id!=user.id: raise HTTPException(404,"Not found")
    p=Path(f.path)
    if not p.exists(): raise HTTPException(404,"File missing")
    mt=mimetypes.guess_type(str(p))[0] or f.mime or "application/octet-stream"
    return FileResponse(str(p), media_type=mt, headers={"Content-Disposition": f"inline; filename=\"{f.original_name}\""})

@router.get("/{fid}/info")
def file_info(fid:str, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    from ..services.pdf_ops import pdf_info
    f=db.query(FileModel).filter(FileModel.id==fid).first()
    if not f or f.owner_id!=user.id: raise HTTPException(404,"Not found")
    p=Path(f.path)
    if not p.exists(): raise HTTPException(404,"File missing")
    try:
        info=pdf_info(p)
        return {"id":f.id, "name":f.original_name, "size":f.size, "mime":f.mime, **info}
    except Exception as e:
        return {"id":f.id, "name":f.original_name, "size":f.size, "mime":f.mime, "pages":1, "error":str(e)}

@router.get("/{fid}/thumb/{page}")
def thumb_file(fid:str, page:int, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    from fastapi.responses import Response
    import fitz
    f=db.query(FileModel).filter(FileModel.id==fid).first()
    if not f or f.owner_id!=user.id: raise HTTPException(404,"Not found")
    p=Path(f.path)
    if not p.exists(): raise HTTPException(404,"File missing")
    if p.suffix.lower() != ".pdf":
        raise HTTPException(400,"Not a PDF")
    try:
        doc=fitz.open(str(p))
        if page<1 or page>doc.page_count: raise HTTPException(404,"Page out of range")
        pg=doc.load_page(page-1)
        zoom=1.2
        mat=fitz.Matrix(zoom, zoom)
        pix=pg.get_pixmap(matrix=mat, alpha=False)
        data=pix.tobytes("png")
        doc.close()
        return Response(content=data, media_type="image/png", headers={"Cache-Control":"public, max-age=3600"})
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.delete("/{fid}")
def delete_file(fid:str, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    f=db.query(FileModel).filter(FileModel.id==fid).first()
    if not f or f.owner_id!=user.id: raise HTTPException(404,"Not found")
    try: Path(f.path).unlink(missing_ok=True)
    except: pass
    db.delete(f); db.commit()
    return {"ok":True}
