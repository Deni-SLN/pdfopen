import os, uuid, shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from .config import settings

ROOT = Path(settings.STORAGE_ROOT).resolve()
UPLOAD = ROOT / "uploads"
PROCESSING = ROOT / "processing"
RESULTS = ROOT / "results"
for p in (UPLOAD, PROCESSING, RESULTS):
    p.mkdir(parents=True, exist_ok=True)

def save_upload(file_bytes: bytes, original_name: str) -> tuple[str, Path]:
    sid = str(uuid.uuid4())
    safe = f"{sid}_{original_name.replace('/','_').replace(chr(92),'_')}"[:180]
    dest = UPLOAD / safe
    dest.write_bytes(file_bytes)
    return sid, dest

def result_path(name: str) -> Path:
    return RESULTS / f"{uuid.uuid4().hex}_{name}"

def cleanup_expired(hours: int = 24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for folder in (UPLOAD, PROCESSING, RESULTS):
        for f in folder.iterdir():
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    if f.is_dir(): shutil.rmtree(f, ignore_errors=True)
                    else: f.unlink(missing_ok=True)
            except: pass
