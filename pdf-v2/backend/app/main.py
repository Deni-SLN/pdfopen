from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from .config import settings
from .database import Base, engine
from .routers import auth, users, tools, files, jobs, admin

# create tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print("DB init failed, will retry on request:", e)

app = FastAPI(title="Sofia Tools v2", version="2.0.0")

origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tools.router)
app.include_router(files.router)
app.include_router(jobs.router)
app.include_router(admin.router)

@app.get("/api/health")
def health(): return {"status":"ok","version":"2.0.0"}

@app.get("/api/ready")
def ready(): return {"ready":True}

@app.on_event("startup")
def _startup_cleanup():
    try:
        from .storage import cleanup_expired
        from sqlalchemy import text
        # run cleanup in thread every 30 min
        import threading, time
        def loop():
            while True:
                try:
                    # respect SystemSetting retention
                    from .database import SessionLocal
                    from .models import SystemSetting
                    db=SessionLocal()
                    sv=db.query(SystemSetting).filter(SystemSetting.key=="retention_hours").first()
                    hrs=int(sv.value) if sv and sv.value.isdigit() else settings.RETENTION_HOURS
                    db.close()
                    cleanup_expired(hrs)
                    # hapus user guest (>2 hari) agar tabel users tidak menumpuk
                    try:
                        from datetime import datetime, timezone, timedelta
                        from .models import User as U
                        db2=SessionLocal()
                        cutoff=datetime.now(timezone.utc)-timedelta(days=2)
                        olds=db2.query(U).filter(U.username.like("guest-%"), U.created_at<cutoff).all()
                        for g in olds: db2.delete(g)
                        if olds: db2.commit()
                        db2.close()
                    except Exception as e2: print("guest cleanup", e2)
                except Exception as e: print("cleanup loop", e)
                time.sleep(1800)
        threading.Thread(target=loop, daemon=True).start()
    except Exception as e:
        print("startup cleanup fail", e)

# serve frontend if built (SPA fallback: route non-/api return index.html)
frontend_dist=Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        from fastapi.responses import FileResponse
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(frontend_dist / "index.html"))
