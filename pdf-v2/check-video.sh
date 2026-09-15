#!/bin/bash
# Diagnosis: cek apakah video-downloader sudah aktif
# Jalankan: bash /opt/data/pdf-v2/check-video.sh

echo "=== A. docker-compose.yml ==="
grep -E 'build:|image:|context:' /opt/data/pdf-v2/docker-compose.yml

echo ""
echo "=== B. Container + Image ==="
docker-compose -f /opt/data/pdf-v2/docker-compose.yml ps
docker images pdf-v2-backend --format '{{.Repository}} {{.Tag}} {{.CreatedAt}}'

echo ""
echo "=== C. File di container yang BERJALAN ==="
BID=$(docker-compose -f /opt/data/pdf-v2/docker-compose.yml ps -q backend)
docker exec "$BID" grep video /app/app/routers/tools.py || echo ">>> VIDEO TIDAK DITEMUKAN DI CONTAINER <<<"

echo ""
echo "=== D. API /tools (cek video) ==="
docker exec "$BID" curl -s http://localhost:8000/api/tools | grep -o 'video-downloader' || echo ">>> VIDEO TIDAK MUNCUL DI API <<<"
