# Sofia PDF Tools — Open Edition

Versi open-source dari Sofia Tools PDF. Tanpa login, tanpa batasan, tanpa database.

## Fitur

| Kategori | Tools |
|----------|-------|
| Organize | Merge, Split, Extract Pages, Delete Pages, Reorder, Remove Blanks |
| Compress | Compress PDF |
| Convert | PDF→JPG/PNG, JPG/PNG→PDF, Markdown→PDF, HTML→PDF |
| Security | Protect PDF, Unlock PDF |
| Edit | Watermark, Remove Watermark, Page Numbers, Remove Annotations, Remove Images |
| Data | PDF→CSV, PDF→Excel, PDF→Excel CAM (BSN), Extract Images |
| Media | Trim MP3 |

## Cara Pakai

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Jalankan

```bash
python sofia_pdf_open.py
```

Buka `http://localhost:8080` di browser.

### 3. Custom Port

```bash
PORT=9000 python sofia_pdf_open.py
```

## Struktur

```
sofia_pdf_open.py      # Semua dalam satu file (backend + frontend)
requirements.txt       # Python dependencies
```

## Spesifikasi

- **Storage**: File disimpan di `/tmp/sofia_pdf_*` (temp)
- **Auto-cleanup**: File dihapus otomatis setelah 1 jam
- **No auth**: Akses langsung, tidak perlu login
- **No limits**: Tidak ada batasan jumlah proses atau ukuran file
- **Self-contained**: Tidak perlu PostgreSQL, Redis, atau Docker

## API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/tools` | Daftar semua tools |
| GET | `/api/health` | Health check |
| POST | `/api/process` | Proses file |

### Contoh API

```bash
# Kompres PDF
curl -X POST http://localhost:8080/api/process \
  -F "tool=compress" \
  -F "file=@input.pdf" \
  -o compressed.pdf

# Merge beberapa PDF
curl -X POST http://localhost:8080/api/process \
  -F "tool=merge" \
  -F "files=@a.pdf" \
  -F "files=@b.pdf" \
  -o merged.pdf

# Ekstrak halaman 1-3
curl -X POST http://localhost:8080/api/process \
  -F "tool=extract-pages" \
  -F "pages=[1,2,3]" \
  -F "file=@input.pdf" \
  -o extracted.pdf
```

## Catatan

- Dibuat dari codebase Sofia Tools PDF v2
- Untuk penggunaan production, tambahkan rate limiting dan HTTPS
- File temporary tidak persisten — download hasil segera

## License

Open source — bebas digunakan dan dimodifikasi.
