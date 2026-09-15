#!/bin/bash
# Rebuild Sofia Tools v2 + deploy video-downloader feature
# Jalankan di host Proxmox (bukan di container hermes)
set -euo pipefail

cd "$(dirname "$0")"
echo "[SOFIA] Rebuilding backend + frontend..."
docker compose down || true
docker compose build --no-cache backend frontend
echo "[SOFIA] Starting services..."
docker compose up -d
sleep 2
echo "[SOFIA] Status:"
docker compose ps
echo "[SOFIA] Video / MP3 Downloader siap di kategori Media."
