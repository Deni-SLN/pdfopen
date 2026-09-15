# Sofia Tools v2

Modern PDF tools, self-hosted, private, and simple. Inspired by Stirling-PDF but with SaaS-style UX, modular workers, and Proxmox + Docker deployment. No AI / no GPU required.

## Fitur sesuai PRD
- **Organize**: Merge, Split, Extract/Delete/Reorder, Rotate
- **Compress**: Compress/Optimize
- **Convert**: PDF ↔ Images (ZIP), JPG/PNG → PDF
- **Security**: Protect (password), Unlock
- **Edit**: Watermark, Page Numbers
- **Data**: PDF → CSV (table detection, delimiter comma/semicolon/tab, UTF-8, preview, ZIP jika multi-tabel)
- **Document**: Markdown → PDF (editor + paper/orientation/margin), HTML → PDF
- **Media**: Trim MP3 (start/end sec, FFmpeg copy-or-reencode)
- Workspace, drag-drop, preview, dual progress (upload vs processing), download, auto-cleanup
- Auth + RBAC (ADMIN/USER, ADMIN pertama auto), Job state machine `queued→validating→processing→packaging→completed|failed|cancelled`, storage UUID, IDOR guard, audit, admin dashboard

## Stack PRD
Frontend: React + Vite + TypeScript + Tailwind + Lucide + pdf.js · Backend: FastAPI + PostgreSQL + Redis+RQ (fallback ke BackgroundThread jika Redis tak ada) + PyMuPDF/pypdf/pdfplumber/ReportLab/Markdown/FFmpeg · Deploy: Docker Compose

## Cara Jalan

### Docker (Proxmox) — Recommended
```bash
cp .env.example .env   # ganti SECRET_KEY
docker compose up --build -d
# frontend http://HOST:3000  backend http://HOST:8000  docs http://HOST:8000/docs
```
Default `ADMIN` = user pertama yang register.

### Local tanpa Docker (Windows)
```bash
# backend
cd backend
py -3 -m venv venv; venv\Scripts\activate
pip install -r requirements.txt
copy ..\ .env  # atau set DATABASE_URL=sqlite:///./sofia.db
py -3 -m uvicorn app.main:app --reload --port 8000

# frontend (terminal kedua)
cd frontend
npm install
npm run dev   # http://localhost:5173  proxy /api → :8000
# build untuk FastAPI serve static:
npm run build
```

## Env
`DATABASE_URL` (postgres atau sqlite fallback), `REDIS_URL`, `SECRET_KEY`, `MAX_FILE_SIZE_MB=100`, `RETENTION_HOURS=24`, `CORS_ORIGINS`

## API
`POST /api/auth/register|login` `GET /api/auth/me` `GET /api/tools` `POST /api/files` `POST /api/jobs` `GET /api/jobs/{id}` `POST /api/jobs/{id}/cancel` `GET /api/jobs/{id}/download` `GET /api/jobs/{id}/preview` `GET /api/admin/stats|jobs|storage` · `GET /api/health`

## Struktur
```
backend/app/{main,config,database,models,auth,storage,routers/*,services/*,workers/*}
frontend/src/{components, pages, lib}
storage/{uploads,processing,results}
docker-compose.yml  .env.example
```

## Catatan PRD V2.0
- PDF→CSV pakai `pdfplumber`; ZIP bila >1 tabel; preview 30 baris.
- Markdown/HTML → PDF: coba WeasyPrint (Linux Docker), fallback ReportLab di Windows tanpa pango.
- MP3 Trim: `ffmpeg -c copy` lalu re-encode `libmp3lame` jika perlu; butuh FFmpeg di container/host.
- Cleanup cron: `POST /api/admin/cleanup` atau `storage.cleanup_expired()` tiap RETENTION_HOURS.
