#!/usr/bin/env python3
"""
Sofia PDF Tools — Open Edition
Tanpa login, tanpa batasan. Jalankan: python sofia_pdf_open.py
Dependencies: pip install fastapi uvicorn python-multipart pymupdf pypdf pillow pdfplumber openpyxl reportlab markdown
Optional: weasyprint (untuk MD/HTML→PDF yang lebih bagus)
"""
import os, io, json, uuid, shutil, zipfile, tempfile, threading, time, re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ── storage ──────────────────────────────────────────────────────────
ROOT = Path(tempfile.mkdtemp(prefix="sofia_pdf_"))
UPLOAD = ROOT / "uploads"
RESULTS = ROOT / "results"
for p in (UPLOAD, RESULTS):
    p.mkdir(exist_ok=True)

TTL_HOURS = 1

def cleanup_loop():
    while True:
        time.sleep(1800)  # 30 min
        cutoff = datetime.now(timezone.utc) - timedelta(hours=TTL_HOURS)
        for folder in (UPLOAD, RESULTS):
            for f in folder.iterdir():
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        if f.is_dir(): shutil.rmtree(f, ignore_errors=True)
                        else: f.unlink(missing_ok=True)
                except: pass

threading.Thread(target=cleanup_loop, daemon=True).start()

def save_upload(file: UploadFile) -> Path:
    sid = uuid.uuid4().hex
    name = (file.filename or "file.pdf").replace("/", "_").replace("\\", "_")[:120]
    dest = UPLOAD / f"{sid}_{name}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest

def result_name(tool: str, ext: str = "pdf") -> Path:
    return RESULTS / f"{uuid.uuid4().hex}_{tool}.{ext}"

# ── PDF operations ───────────────────────────────────────────────────
import fitz
from pypdf import PdfReader, PdfWriter
from PIL import Image

def merge_pdfs(inputs: list, output: Path):
    doc = fitz.open()
    for p in inputs:
        src = fitz.open(str(p))
        doc.insert_pdf(src)
        src.close()
    doc.save(str(output)); doc.close()
    return output

def split_pdf(inp: Path, params: dict) -> Path:
    r = PdfReader(str(inp))
    n = len(r.pages)
    parts = params.get("parts") or []
    if parts:
        outs = []
        for idx, part in enumerate(parts):
            pages = part.get("pages") or []
            if isinstance(pages, str):
                parsed = []
                for seg in pages.split(","):
                    seg = seg.strip()
                    if "-" in seg:
                        try:
                            a, b = map(lambda x: int(x.strip()), seg.split("-", 1))
                            lo, hi = min(a, b), max(a, b)
                            for v in range(lo, hi + 1):
                                if 1 <= v <= n: parsed.append(v)
                        except: pass
                    else:
                        try:
                            v = int(seg)
                            if 1 <= v <= n: parsed.append(v)
                        except: pass
                pages = parsed
            pages = [int(p) for p in pages if 1 <= int(p) <= n]
            if not pages: continue
            w = PdfWriter()
            for pnum in pages:
                w.add_page(r.pages[pnum - 1])
            o = result_name(f"part_{idx+1}")
            with open(o, "wb") as fh: w.write(fh)
            outs.append(o)
        if not outs: raise ValueError("No valid pages")
        if len(outs) == 1: return outs[0]
        z = result_name("split", "zip")
        with zipfile.ZipFile(z, "w") as zf:
            for o in outs: zf.write(o, o.name)
        for o in outs: o.unlink(missing_ok=True)
        return z
    else:
        outs = []
        for i, pg in enumerate(r.pages):
            w = PdfWriter(); w.add_page(pg)
            o = result_name(f"page_{i+1}")
            with open(o, "wb") as fh: w.write(fh)
            outs.append(o)
        z = result_name("split", "zip")
        with zipfile.ZipFile(z, "w") as zf:
            for o in outs: zf.write(o, o.name)
        for o in outs: o.unlink(missing_ok=True)
        return z

def rotate_pdf(inp: Path, angle: int = 90) -> Path:
    doc = fitz.open(str(inp))
    for page in doc:
        page.set_rotation((page.rotation + angle) % 360)
    out = result_name("rotated")
    doc.save(str(out)); doc.close()
    return out

def delete_pages(inp: Path, pages: list) -> Path:
    reader = PdfReader(str(inp))
    writer = PdfWriter()
    for i, pg in enumerate(reader.pages, 1):
        if i not in pages: writer.add_page(pg)
    out = result_name("deleted")
    with open(out, "wb") as f: writer.write(f)
    return out

def extract_pages(inp: Path, pages: list) -> Path:
    reader = PdfReader(str(inp))
    writer = PdfWriter()
    for i in pages:
        if 1 <= i <= len(reader.pages): writer.add_page(reader.pages[i - 1])
    out = result_name("extracted")
    with open(out, "wb") as f: writer.write(f)
    return out

def reorder_pages(inp: Path, order: list) -> Path:
    return extract_pages(inp, order)

def compress_pdf(inp: Path) -> Path:
    doc = fitz.open(str(inp))
    out = result_name("compressed")
    doc.save(str(out), garbage=4, deflate=True, clean=True)
    doc.close()
    return out

def pdf_to_images(inp: Path, fmt: str = "png", dpi: int = 150) -> Path:
    doc = fitz.open(str(inp))
    out_dir = RESULTS / f"{uuid.uuid4().hex}_imgs"
    out_dir.mkdir()
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    outs = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        o = out_dir / f"page_{i+1}.{fmt}"
        pix.save(str(o))
        outs.append(o)
    doc.close()
    z = result_name("images", "zip")
    with zipfile.ZipFile(z, "w") as zf:
        for o in outs: zf.write(o, o.name)
    return z

def images_to_pdf(images: list) -> Path:
    imgs = [Image.open(str(p)).convert("RGB") for p in images]
    if not imgs: raise ValueError("No images")
    out = result_name("from_images")
    imgs[0].save(str(out), save_all=True, append_images=imgs[1:])
    return out

def protect_pdf(inp: Path, password: str) -> Path:
    reader = PdfReader(str(inp)); writer = PdfWriter()
    for pg in reader.pages: writer.add_page(pg)
    writer.encrypt(password)
    out = result_name("protected")
    with open(out, "wb") as f: writer.write(f)
    return out

def unlock_pdf(inp: Path, password: str) -> Path:
    reader = PdfReader(str(inp))
    if reader.is_encrypted: reader.decrypt(password)
    writer = PdfWriter()
    for pg in reader.pages: writer.add_page(pg)
    out = result_name("unlocked")
    with open(out, "wb") as f: writer.write(f)
    return out

def add_watermark(inp: Path, text: str) -> Path:
    doc = fitz.open(str(inp))
    for page in doc:
        # diagonal watermark via Shape (compatible with new PyMuPDF)
        rect = page.rect
        shape = page.new_shape()
        # estimate text width
        tw = fitz.get_text_length(text, fontsize=40)
        # center point
        cx = rect.width / 2
        cy = rect.height / 2
        # draw rotated text: insert at center with rotate=45
        # PyMuPDF new API: insert_text accepts rotate in {0,90,180,270} only
        # Use write_text with rotation matrix instead
        mat = fitz.Matrix(1, 1).prerotate(45)
        tw_rot = fitz.get_text_length(text, fontsize=40)
        shape.insert_text(
            fitz.Point(cx - tw_rot / 2, cy),
            text,
            fontsize=40,
            color=(0.8, 0.8, 0.8),
            morph=(fitz.Point(cx, cy), mat)
        )
        shape.commit()
    out = result_name("watermark")
    doc.save(str(out)); doc.close()
    return out

def remove_watermark(inp: Path, text: str = "") -> Path:
    doc = fitz.open(str(inp))
    target = text.strip().lower() if text else ""
    for page in doc:
        try:
            for annot in list(page.annots() or []):
                try: page.delete_annot(annot)
                except: pass
        except: pass
        try:
            drawings = page.get_drawings()
            for d in drawings:
                col = d.get("color") or [0, 0, 0]
                if isinstance(col, (list, tuple)) and len(col) >= 3 and all(0.65 <= c <= 0.95 for c in col[:3]):
                    try:
                        rect = fitz.Rect(d["rect"])
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                    except: pass
            try: page.apply_redactions()
            except: pass
        except: pass
        try:
            if target:
                insts = page.search_for(target)
                for r in insts:
                    page.add_redact_annot(r, fill=(1, 1, 1))
                if insts: page.apply_redactions()
        except: pass
    out = result_name("no_watermark")
    doc.save(str(out), garbage=4, deflate=True, clean=True)
    doc.close()
    return out

def add_page_numbers(inp: Path) -> Path:
    doc = fitz.open(str(inp))
    for i, page in enumerate(doc):
        page.insert_text((page.rect.width / 2 - 20, page.rect.height - 20), str(i + 1), fontsize=10)
    out = result_name("paged")
    doc.save(str(out)); doc.close()
    return out

def pdf_info(inp: Path) -> dict:
    doc = fitz.open(str(inp))
    info = {"pages": doc.page_count, "metadata": doc.metadata}
    doc.close()
    return info

def remove_blanks(inp: Path) -> Path:
    doc = fitz.open(str(inp)); out = fitz.open()
    for p in doc:
        txt = p.get_text().strip()
        if txt or len(p.get_images()) > 0:
            out.insert_pdf(doc, from_page=p.number, to_page=p.number)
    if out.page_count == 0: out.insert_pdf(doc, from_page=0, to_page=0)
    o = result_name("no_blanks")
    out.save(str(o)); out.close(); doc.close()
    return o

def remove_annotations(inp: Path) -> Path:
    doc = fitz.open(str(inp))
    for p in doc:
        for annot in list(p.annots() or []):
            p.delete_annot(annot)
    out = result_name("no_annots")
    doc.save(str(out)); doc.close()
    return out

def remove_images_func(inp: Path) -> Path:
    doc = fitz.open(str(inp))
    for p in doc:
        for img in p.get_images(full=True):
            try: p.delete_image(img[0])
            except: pass
    out = result_name("no_images")
    doc.save(str(out)); doc.close()
    return out

def extract_images_func(inp: Path) -> Path:
    doc = fitz.open(str(inp))
    out_dir = RESULTS / f"{uuid.uuid4().hex}_extimg"
    out_dir.mkdir()
    outs = []
    for i, p in enumerate(doc):
        for j, img in enumerate(p.get_images(full=True)):
            try:
                pix = fitz.Pixmap(doc, img[0])
                if pix.n > 4: pix = fitz.Pixmap(fitz.csRGB, pix)
                o = out_dir / f"page{i+1}_img{j+1}.png"
                pix.save(str(o)); outs.append(o)
            except: pass
    doc.close()
    if not outs: raise ValueError("No images found")
    z = result_name("extracted_images", "zip")
    with zipfile.ZipFile(z, "w") as zf:
        for o in outs: zf.write(o, o.name)
    return z

# ── table extraction ─────────────────────────────────────────────────
def pdf_to_csv_func(inp: Path, delimiter: str = ",") -> Path:
    import pdfplumber, csv
    outs = []
    t_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines",
                  "intersection_tolerance": 5, "snap_tolerance": 3, "join_tolerance": 3}
    with pdfplumber.open(str(inp)) as pdf:
        for pi, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables(table_settings=t_settings)
                if not tables: tables = page.extract_tables()
            except: tables = []
            if not tables:
                txt = page.extract_text() or ""
                if txt.strip():
                    o = result_name(f"page_{pi+1}", "csv")
                    with open(o, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f, delimiter=delimiter)
                        for line in txt.splitlines():
                            if line.strip(): w.writerow([line])
                    outs.append(o)
            else:
                for ti, tbl in enumerate(tables):
                    o = result_name(f"page_{pi+1}_table_{ti+1}", "csv")
                    with open(o, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f, delimiter=delimiter)
                        for row in tbl:
                            w.writerow([c if c is not None else "" for c in row])
                    outs.append(o)
    if not outs: raise ValueError("No tables or text extracted")
    if len(outs) == 1: return outs[0]
    z = result_name("tables", "zip")
    with zipfile.ZipFile(z, "w") as zf:
        for o in outs: zf.write(o, o.name)
    for o in outs: o.unlink(missing_ok=True)
    return z

def pdf_to_excel_func(inp: Path, mode: str = "per_sheet") -> Path:
    from openpyxl import Workbook
    import csv
    csv_path = pdf_to_csv_func(inp, ",")
    # re-extract all CSVs
    import pdfplumber
    outs = []
    with pdfplumber.open(str(inp)) as pdf:
        for pi, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables()
            except: tables = []
            if not tables:
                txt = page.extract_text() or ""
                if txt.strip():
                    o = result_name(f"page_{pi+1}", "csv")
                    with open(o, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f)
                        for line in txt.splitlines():
                            if line.strip(): w.writerow([line])
                    outs.append(o)
            else:
                for ti, tbl in enumerate(tables):
                    o = result_name(f"page_{pi+1}_table_{ti+1}", "csv")
                    with open(o, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f)
                        for row in tbl:
                            w.writerow([c if c is not None else "" for c in row])
                    outs.append(o)
    out = result_name("converted", "xlsx")
    wb = Workbook()
    wb.remove(wb.active)
    if mode == "merge":
        ws = wb.create_sheet(title="Semua Halaman")
        first = True
        for csv_path in outs:
            with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                rows = list(csv.reader(fh))
                if not rows: continue
                if not first: ws.append([])
                for row in rows: ws.append(row)
                first = False
        if len(ws['A']) == 0: ws.append(["No data"])
    else:
        for csv_path in outs:
            m = re.search(r'page_(\d+)', csv_path.name)
            page_label = f"Halaman {m.group(1)}" if m else csv_path.stem[:31]
            if page_label in wb.sheetnames:
                ws = wb[page_label]
                ws.append([])
                with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                    for row in csv.reader(fh): ws.append(row)
            else:
                ws = wb.create_sheet(title=page_label[:31])
                with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                    for row in csv.reader(fh): ws.append(row)
    if len(wb.sheetnames) == 0:
        wb.create_sheet("Sheet1")
    wb.save(str(out))
    for o in outs: o.unlink(missing_ok=True)
    return out

# ── MD/HTML to PDF ───────────────────────────────────────────────────
def md_to_pdf_func(md_text: str, paper: str = "A4", orientation: str = "portrait", margin: str = "20mm") -> Path:
    try:
        from weasyprint import HTML
        import markdown
        html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
        css = "body{font-family:Arial,sans-serif;line-height:1.6;max-width:800px;margin:40px auto;padding:0 20px;color:#1a1a1a}"
        html = f"<html><head><meta charset='utf-8'><style>@page{{size:{paper} {orientation};margin:{margin}}}{css}</style></head><body>{html_body}</body></html>"
        out = result_name("from_md")
        HTML(string=html).write_pdf(str(out))
        return out
    except:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        out = result_name("from_md")
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
        story = []
        for line in md_text.splitlines():
            if not line.strip(): story.append(Spacer(1, 8))
            else:
                esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(esc, styles['Normal']))
                story.append(Spacer(1, 4))
        doc.build(story)
        return out

def html_to_pdf_func(html_text: str, paper: str = "A4", orientation: str = "portrait", margin: str = "15mm") -> Path:
    try:
        from weasyprint import HTML
        css = f"@page{{size:{paper} {orientation};margin:{margin}}}"
        full = f"<style>{css}</style>" + html_text if "<html" not in html_text.lower() else html_text
        out = result_name("from_html")
        HTML(string=full).write_pdf(str(out))
        return out
    except:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4
        out = result_name("from_html")
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
        story = []
        for line in html_text.splitlines():
            if not line.strip(): story.append(Spacer(1, 8))
            else:
                esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(esc, styles['Normal']))
                story.append(Spacer(1, 4))
        doc.build(story)
        return out

# ── MP3 trim ─────────────────────────────────────────────────────────
def trim_mp3_func(inp: Path, start: float, end: float) -> Path:
    out = result_name("trimmed", "mp3")
    dur = end - start
    if dur <= 0: raise ValueError("End must be after start")
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(inp), "-c", "copy", str(out)]
    try:
        import subprocess
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if out.stat().st_size == 0: raise Exception("empty")
    except:
        cmd2 = ["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(inp), "-c:a", "libmp3lame", "-q:a", "2", str(out)]
        subprocess.check_call(cmd2)
    return out

# ── CAM Excel ────────────────────────────────────────────────────────
CAM_HEADERS = [
    "No CIF", "No Loan", "Kode Cabang", "Kode Outlet", "Nama Nasabah",
    "Nama Produk", "Nama Produk Simplifikasi", "Kol EOM", "Prioritas",
    "KOL SOM", "KOL EOD", "Predictive KOL", "Sisa Pokok Outstanding",
    "Angsuran", "Tgl Due Date", "Tgl Bayar Pokok", "Start Monitoring Restru",
    "End Monitoring Restru", "Proper", "Developer", "Kriteria Nasabah",
    "Kondisi Agunan", "Permasalahan", "Kelengkapan Dokumen", "PIC Desk Coll KP",
    "PIC Desk Coll KC", "PIC Field Collector", "Status Pembinaan",
    "Tgl Janji Bayar", "Int. Telepon", "Int. Visit", "Load Timestamp",
]
NCOL = len(CAM_HEADERS)

def pdf_to_excel_cam_func(inp: Path) -> Path:
    buf = _remove_cam_watermark(inp)
    import pdfplumber
    pdf = pdfplumber.open(io.BytesIO(buf))
    try:
        n = len(pdf.pages)
        page_rows = [None] * n
        def work(args):
            i, page = args
            try: return i, _extract_cam_page(page)
            except: return i, []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i, rows in ex.map(work, list(enumerate(pdf.pages))):
                page_rows[i] = rows
    finally:
        pdf.close()
    data = []
    for rows in page_rows:
        if not rows: continue
        for row, cont in rows:
            if not any((c or "").strip() for c in row): continue
            joined = " ".join((c or "") for c in row[:3])
            if "No CIF" in joined: continue
            norm = [_norm_cam_col(i, c) for i, c in enumerate(row)]
            if data and not norm[0].strip() and not norm[1].strip():
                prev = data[-1]
                for i in range(NCOL):
                    v = norm[i]
                    if not v: continue
                    sep = "" if (i in cont or i in {7,9,10,11} or i in {0,1,2,3,12,13,14,15,16,17,18,28,29,30,31}) else " "
                    prev[i] = _norm_cam_col(i, prev[i] + sep + v)
                continue
            data.append(norm)
    if not data: raise ValueError("Tidak ada baris data CAM")
    out = result_name("CAM", "xlsx")
    _write_cam_xlsx(out, data)
    return out

def _remove_cam_watermark(inp: Path) -> bytes:
    doc = fitz.open(str(inp))
    try:
        for page in doc:
            xrefs = page.get_contents()
            if not xrefs: continue
            if len(xrefs) > 1:
                page.clean_contents()
                xrefs = page.get_contents()
            xref = xrefs[0]
            new, n = _strip_wm(doc.xref_stream(xref))
            if n: doc.update_stream(xref, new)
        return doc.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

_BT_ET = re.compile(rb"BT(?:(?!BT|ET).)*?ET", re.S)
_TM = re.compile(rb"([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+Tm")

def _strip_wm(data: bytes):
    removed = 0
    def repl(m):
        nonlocal removed
        block = m.group(0)
        for tm in _TM.finditer(block):
            b = float(tm.group(2)); c = float(tm.group(3))
            if abs(b) > 1e-4 or abs(c) > 1e-4:
                removed += 1
                return b""
        return block
    return _BT_ET.sub(repl, data), removed

def _extract_cam_page(page):
    import bisect
    tables = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines",
                                "intersection_tolerance": 5, "snap_tolerance": 3, "join_tolerance": 3})
    out = []
    for tbl in tables:
        bbox = tbl.bbox
        inside = [c for c in page.chars
                  if bbox[0] - 1 <= (c["x0"] + c["x1"]) / 2 <= bbox[2] + 1
                  and bbox[1] - 1 <= (c["top"] + c["bottom"]) / 2 <= bbox[3] + 1]
        centers = sorted((((c["x0"] + c["x1"]) / 2, c) for c in inside), key=lambda t: t[0])
        xs = [t[0] for t in centers]
        for row in tbl.rows:
            r = []
            cont = set()
            for j, cell in enumerate(row.cells):
                if cell is None: r.append(""); continue
                lo = bisect.bisect_left(xs, cell[0] - 0.01)
                hi = bisect.bisect_right(xs, cell[2] - 0.01)
                cc = [c for x, c in centers[lo:hi]
                      if cell[1] <= (c["top"] + c["bottom"]) / 2 < cell[3]]
                txt, filled = _cell_cam_text(cc, cell)
                if filled and txt: cont.add(j)
                r.append(txt)
            out.append((r, cont))
    return out

def _cell_cam_text(chars, bbox):
    if not chars: return "", False
    x0c, _topc, x1c, _botc = bbox
    pad = max(0.0, min(c["x0"] for c in chars) - x0c)
    chars = sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"]))
    lines, cur, cur_top = [], [], None
    for ch in chars:
        if cur_top is None or abs(ch["top"] - cur_top) <= 2.0:
            cur.append(ch)
            if cur_top is None: cur_top = ch["top"]
        else:
            lines.append(cur); cur = [ch]; cur_top = ch["top"]
    if cur: lines.append(cur)
    parsed = []
    for ln in lines:
        ln = sorted(ln, key=lambda c: c["x0"])
        size = ln[0].get("size", 5) or 5
        thr = max(0.75, size * 0.18)
        s, words, cur_w = "", [], [ln[0]]
        prev = None
        for ch in ln:
            if prev is not None:
                if ch["x0"] - prev["x1"] > thr:
                    s += " "; words.append(cur_w); cur_w = [ch]
                else: cur_w.append(ch)
            s += ch["text"]
            prev = ch
        words.append(cur_w)
        parsed.append((s.strip(), ln, words))
    out = parsed[0][0]
    U = x1c - pad
    W = (x1c - x0c) - 2 * pad
    for i in range(1, len(parsed)):
        _ps, prev_ln, prev_words = parsed[i - 1]
        cur_s, cur_ln, cur_words = parsed[i]
        if not prev_words or not cur_words or not prev_ln or not cur_ln:
            out += (" " + cur_s) if cur_s else ""
            continue
        lw, fw = prev_words[-1], cur_words[0]
        w1 = lw[-1]["x1"] - lw[0]["x0"]
        w2 = fw[-1]["x1"] - fw[0]["x0"]
        gap_right = U - prev_ln[-1]["x1"]
        nch_w = cur_ln[0]["x1"] - cur_ln[0]["x0"]
        if (w1 + w2) > W and gap_right < nch_w:
            out += cur_s
        else:
            out += " " + cur_s
    filled = False
    last = parsed[-1]
    if last and last[1]:
        last_ln = last[1]
        gap_right = U - last_ln[-1]["x1"]
        ws = [c["x1"] - c["x0"] for c in last_ln if c["x1"] > c["x0"]] or [1.0]
        avg_w = sum(ws) / len(ws)
        filled = gap_right < avg_w * 0.6
    return re.sub(r"\s{2,}", " ", out).strip(), filled

_NOSPACE_IDX = {0, 1, 2, 3, 12, 13, 14, 15, 16, 17, 18, 28, 29, 30, 31}
_KOL_IDX = {7, 9, 10, 11}
_PRIORITAS_IDX = 8

def _norm_nospace(s):
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})", r"\1 \2", s)
    s = re.sub(r"^Rp", "Rp ", s)
    return s

def _norm_kol(s):
    s = re.sub(r"\s+", "", s)
    return re.sub(r"^KOL(?=[\d.])", "KOL ", s)

def _norm_prioritas(s):
    s = re.sub(r"\s+", "", s)
    return re.sub(r"^PRIORITAS(?=\d)", "PRIORITAS ", s)

def _norm_cam_col(i, c):
    c = (c or "").strip()
    if not c: return ""
    if i in _KOL_IDX: return _norm_kol(c)
    if i == _PRIORITAS_IDX: return _norm_prioritas(c)
    if i in _NOSPACE_IDX: return _norm_nospace(c)
    return re.sub(r"\s{2,}", " ", c)

def _write_cam_xlsx(out_path, data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "CAM"
    ws.append(CAM_HEADERS)
    hf = PatternFill("solid", fgColor="1E3A8A")
    for j in range(1, NCOL + 1):
        c = ws.cell(row=1, column=j)
        c.font = Font(bold=True, color="FFFFFF", size=10)
        c.fill = hf
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in data:
        row = list(row[:NCOL]) + [""] * (NCOL - len(row))
        ws.append([(c if c is not None else "") for c in row])
    widths = [len(h) for h in CAM_HEADERS]
    for row in data:
        for i, v in enumerate(row[:NCOL]):
            l = len(v or "")
            if l > widths[i]: widths[i] = min(l, 45)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(w + 2, 45)
    ws.freeze_panes = "A2"
    wb.save(str(out_path))

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(title="Sofia PDF Tools — Open Edition", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/tools")
def list_tools():
    return [
        {"id": "merge", "name": "Merge PDF", "cat": "Organize", "desc": "Gabungkan beberapa PDF jadi satu"},
        {"id": "split", "name": "Split PDF", "cat": "Organize", "desc": "Pisahkan halaman (ZIP)"},
        {"id": "rotate", "name": "Rotate PDF", "cat": "Organize", "desc": "Putar semua halaman"},
        {"id": "compress", "name": "Compress PDF", "cat": "Optimize", "desc": "Kecilkan ukuran file"},
        {"id": "extract-pages", "name": "Extract Pages", "cat": "Organize", "desc": "Ambil halaman tertentu"},
        {"id": "delete-pages", "name": "Delete Pages", "cat": "Organize", "desc": "Hapus halaman tertentu"},
        {"id": "reorder", "name": "Reorder Pages", "cat": "Organize", "desc": "Atur ulang urutan halaman"},
        {"id": "pdf-to-image", "name": "PDF → JPG/PNG", "cat": "Convert", "desc": "Export halaman sebagai gambar (ZIP)"},
        {"id": "image-to-pdf", "name": "JPG/PNG → PDF", "cat": "Convert", "desc": "Gambar ke PDF"},
        {"id": "protect", "name": "Protect PDF", "cat": "Security", "desc": "Tambah password"},
        {"id": "unlock", "name": "Unlock PDF", "cat": "Security", "desc": "Hapus password"},
        {"id": "watermark", "name": "Watermark", "cat": "Edit", "desc": "Tambah teks watermark"},
        {"id": "remove-watermark", "name": "Remove Watermark", "cat": "Edit", "desc": "Hapus watermark"},
        {"id": "page-numbers", "name": "Page Numbers", "cat": "Edit", "desc": "Tambah nomor halaman"},
        {"id": "pdf-to-csv", "name": "PDF → CSV", "cat": "Data", "desc": "Ekstrak tabel ke CSV"},
        {"id": "pdf-to-excel", "name": "PDF → Excel", "cat": "Data", "desc": "Ekstrak tabel ke XLSX"},
        {"id": "pdf-to-excel-cam", "name": "PDF → Excel CAM", "cat": "Data", "desc": "Khusus Detail CAM Prioritisasi (BSN)"},
        {"id": "md-to-pdf", "name": "Markdown → PDF", "cat": "Document", "desc": "Markdown ke PDF"},
        {"id": "html-to-pdf", "name": "HTML → PDF", "cat": "Document", "desc": "HTML/CSS ke PDF"},
        {"id": "mp3-trim", "name": "Trim MP3", "cat": "Media", "desc": "Potong MP3"},
        {"id": "remove-blanks", "name": "Remove Blanks", "cat": "Organize", "desc": "Hapus halaman kosong"},
        {"id": "remove-annotations", "name": "Remove Annotations", "cat": "Edit", "desc": "Hapus anotasi/komentar"},
        {"id": "remove-image", "name": "Remove Images", "cat": "Edit", "desc": "Hapus gambar embedded"},
        {"id": "extract-images", "name": "Extract Images", "cat": "Data", "desc": "Ekstrak gambar dari PDF (ZIP)"},
        {"id": "get-pdf-info", "name": "PDF Info", "cat": "Data", "desc": "Lihat metadata & jumlah halaman"},
    ]

@app.get("/api/health")
def health(): return {"status": "ok", "edition": "open"}

@app.post("/api/process")
async def process(
    tool: str = Form(...),
    file: UploadFile = File(None),
    files: list[UploadFile] = File(None),
    password: str = Form(None),
    text: str = Form(None),
    angle: int = Form(90),
    fmt: str = Form("png"),
    dpi: int = Form(150),
    delimiter: str = Form(","),
    excel_mode: str = Form("per_sheet"),
    paper: str = Form("A4"),
    orientation: str = Form("portrait"),
    margin: str = Form("20mm"),
    start: float = Form(0),
    end: float = Form(10),
    pages: str = Form(None),
    order: str = Form(None),
    parts: str = Form(None),
):
    try:
        input_path = None
        input_paths = []
        if file and file.filename:
            input_path = save_upload(file)
        if files:
            for f in files:
                if f.filename:
                    input_paths.append(save_upload(f))
        
        if tool == "merge":
            if not input_paths: raise HTTPException(400, "Need at least 2 files")
            out = merge_pdfs(input_paths, result_name("merged"))
            return FileResponse(str(out), filename="merged.pdf", media_type="application/pdf")
        
        if not input_path and not input_paths:
            if tool in ("md-to-pdf", "html-to-pdf"):
                pass  # text-based
            else:
                raise HTTPException(400, "No file uploaded")
        
        inp = input_path or (input_paths[0] if input_paths else None)
        
        if tool == "split":
            params = {}
            if parts:
                try: params["parts"] = json.loads(parts)
                except: pass
            out = split_pdf(inp, params)
            if out.suffix == ".zip":
                return FileResponse(str(out), filename="split.zip", media_type="application/zip")
            return FileResponse(str(out), filename=out.name, media_type="application/pdf")
        
        elif tool == "rotate":
            out = rotate_pdf(inp, angle)
            return FileResponse(str(out), filename="rotated.pdf", media_type="application/pdf")
        
        elif tool == "compress":
            out = compress_pdf(inp)
            return FileResponse(str(out), filename="compressed.pdf", media_type="application/pdf")
        
        elif tool == "extract-pages":
            pgs = json.loads(pages) if pages else [1]
            out = extract_pages(inp, pgs)
            return FileResponse(str(out), filename="extracted.pdf", media_type="application/pdf")
        
        elif tool == "delete-pages":
            pgs = json.loads(pages) if pages else []
            out = delete_pages(inp, pgs)
            return FileResponse(str(out), filename="deleted.pdf", media_type="application/pdf")
        
        elif tool == "reorder":
            ord = json.loads(order) if order else []
            out = reorder_pages(inp, ord)
            return FileResponse(str(out), filename="reordered.pdf", media_type="application/pdf")
        
        elif tool == "pdf-to-image":
            out = pdf_to_images(inp, fmt, dpi)
            return FileResponse(str(out), filename="images.zip", media_type="application/zip")
        
        elif tool == "image-to-pdf":
            if not input_paths: raise HTTPException(400, "Need at least 1 image")
            out = images_to_pdf(input_paths)
            return FileResponse(str(out), filename="from_images.pdf", media_type="application/pdf")
        
        elif tool == "protect":
            if not password: raise HTTPException(400, "Password required")
            out = protect_pdf(inp, password)
            return FileResponse(str(out), filename="protected.pdf", media_type="application/pdf")
        
        elif tool == "unlock":
            if not password: raise HTTPException(400, "Password required")
            out = unlock_pdf(inp, password)
            return FileResponse(str(out), filename="unlocked.pdf", media_type="application/pdf")
        
        elif tool == "watermark":
            out = add_watermark(inp, text or "SOFIA")
            return FileResponse(str(out), filename="watermark.pdf", media_type="application/pdf")
        
        elif tool == "remove-watermark":
            out = remove_watermark(inp, text or "")
            return FileResponse(str(out), filename="no_watermark.pdf", media_type="application/pdf")
        
        elif tool == "page-numbers":
            out = add_page_numbers(inp)
            return FileResponse(str(out), filename="paged.pdf", media_type="application/pdf")
        
        elif tool == "pdf-to-csv":
            out = pdf_to_csv_func(inp, delimiter)
            if out.suffix == ".zip":
                return FileResponse(str(out), filename="tables.zip", media_type="application/zip")
            return FileResponse(str(out), filename=out.name, media_type="text/csv")
        
        elif tool == "pdf-to-excel":
            out = pdf_to_excel_func(inp, excel_mode)
            return FileResponse(str(out), filename="converted.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        elif tool == "pdf-to-excel-cam":
            out = pdf_to_excel_cam_func(inp)
            return FileResponse(str(out), filename="CAM_Excel.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        elif tool == "md-to-pdf":
            if not text: raise HTTPException(400, "No markdown text")
            out = md_to_pdf_func(text, paper, orientation, margin)
            return FileResponse(str(out), filename="document.pdf", media_type="application/pdf")
        
        elif tool == "html-to-pdf":
            if not text: raise HTTPException(400, "No HTML content")
            out = html_to_pdf_func(text, paper, orientation, margin)
            return FileResponse(str(out), filename="document.pdf", media_type="application/pdf")
        
        elif tool == "mp3-trim":
            out = trim_mp3_func(inp, start, end)
            return FileResponse(str(out), filename="trimmed.mp3", media_type="audio/mpeg")
        
        elif tool == "remove-blanks":
            out = remove_blanks(inp)
            return FileResponse(str(out), filename="no_blanks.pdf", media_type="application/pdf")
        
        elif tool == "remove-annotations":
            out = remove_annotations(inp)
            return FileResponse(str(out), filename="no_annots.pdf", media_type="application/pdf")
        
        elif tool == "remove-image":
            out = remove_images_func(inp)
            return FileResponse(str(out), filename="no_images.pdf", media_type="application/pdf")
        
        elif tool == "extract-images":
            out = extract_images_func(inp)
            return FileResponse(str(out), filename="extracted_images.zip", media_type="application/zip")
        
        elif tool == "get-pdf-info":
            info = pdf_info(inp)
            return JSONResponse(info)
        
        else:
            raise HTTPException(400, f"Unknown tool: {tool}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Frontend ─────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sofia PDF Tools — Open</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.header{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);padding:20px 0;border-bottom:1px solid #1e293b}
.header h1{font-size:1.5rem;font-weight:700;color:#f1f5f9}
.header p{font-size:.85rem;color:#94a3b8;margin-top:4px}
.container{max-width:1200px;margin:0 auto;padding:20px}
.tools-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:20px 0}
.tool-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;cursor:pointer;transition:all .2s}
.tool-card:hover{border-color:#6366f1;transform:translateY(-2px);box-shadow:0 4px 20px rgba(99,102,241,.15)}
.tool-card h3{font-size:.95rem;font-weight:600;color:#f1f5f9;margin-bottom:4px}
.tool-card .cat{font-size:.7rem;color:#6366f1;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.tool-card p{font-size:.8rem;color:#94a3b8;line-height:1.4}
.process-area{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-top:20px;display:none}
.process-area.active{display:block}
.dropzone{border:2px dashed #475569;border-radius:10px;padding:40px;text-align:center;cursor:pointer;transition:all .2s;margin-bottom:16px}
.dropzone:hover,.dropzone.drag{border-color:#6366f1;background:rgba(99,102,241,.05)}
.dropzone p{color:#94a3b8;margin-top:8px}
.dropzone .icon{font-size:2rem}
input[type=file]{display:none}
.btn{background:#6366f1;color:#fff;border:none;padding:10px 20px;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;transition:all .2s}
.btn:hover{background:#4f46e5}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-secondary{background:#334155}
.btn-secondary:hover{background:#475569}
.input-group{margin-bottom:12px}
.input-group label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:4px}
.input-group input,.input-group select,.input-group textarea{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:8px 12px;color:#e2e8f0;font-size:.9rem}
.input-group textarea{min-height:120px;resize:vertical;font-family:monospace}
.status{margin-top:16px;padding:12px;border-radius:8px;font-size:.85rem;display:none}
.status.show{display:block}
.status.processing{background:rgba(99,102,241,.1);border:1px solid #6366f1;color:#a5b4fc}
.status.success{background:rgba(34,197,94,.1);border:1px solid #22c55e;color:#86efac}
.status.error{background:rgba(239,68,68,.1);border:1px solid #ef4444;color:#fca5a5}
.file-list{margin:8px 0}
.file-item{display:flex;align-items:center;gap:8px;background:#0f172a;padding:6px 10px;border-radius:6px;margin-bottom:4px;font-size:.8rem}
.file-item .remove{cursor:pointer;color:#ef4444;margin-left:auto}
.back-btn{display:inline-flex;align-items:center;gap:6px;color:#94a3b8;cursor:pointer;font-size:.85rem;margin-bottom:12px;background:none;border:none}
.back-btn:hover{color:#e2e8f0}
@media(max-width:600px){.tools-grid{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="header">
<div class="container">
<h1>Sofia PDF Tools</h1>
<p>Open Edition — Tanpa login, tanpa batasan</p>
</div>
</div>
<div class="container">
<div id="toolsView">
<div class="tools-grid" id="toolsGrid"></div>
</div>
<div class="process-area" id="processArea">
<button class="back-btn" onclick="showTools()">&larr; Kembali</button>
<h2 id="toolTitle" style="margin-bottom:16px"></h2>
<div id="toolContent"></div>
</div>
</div>
<script>
const tools=await(await fetch('/api/tools')).json();
const g=document.getElementById('toolsGrid');
tools.forEach(t=>{
const c=document.createElement('div');
c.className='tool-card';
c.innerHTML=`<div class="cat">${t.cat}</div><h3>${t.name}</h3><p>${t.desc}</p>`;
c.onclick=()=>showTool(t);
g.appendChild(c);
});
function showTools(){document.getElementById('processArea').classList.remove('active');document.getElementById('toolsView').style.display='block';}
function showTool(t){document.getElementById('toolsView').style.display='none';document.getElementById('processArea').classList.add('active');document.getElementById('toolTitle').textContent=t.name;renderTool(t);}
function renderTool(t){
const c=document.getElementById('toolContent');
let html='';
const fl='<div class="dropzone" id="drop"><div class="icon">📄</div><div id="fileList" class="file-list"></div><p>Drag & drop file atau klik untuk pilih</div><input type="file" id="fileInput" accept=".pdf,.jpg,.jpeg,.png,.md,.html,.htm,.mp3"></div>';
const flMulti='<div class="dropzone" id="drop"><div class="icon">📄</div><div id="fileList" class="file-list"></div><p>Drag & drop file atau klik untuk pilih</div><input type="file" id="fileInput" accept=".pdf,.jpg,.jpeg,.png" multiple></div>';
const st='<div class="status" id="status"></div>';
if(t.id==='merge'){html=flMulti+'<button class="btn" id="btn" style="width:100%;margin-top:12px">Gabungkan PDF</button>'+st;}
else if(t.id==='image-to-pdf'){html=flMulti+'<button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi ke PDF</button>'+st;}
else if(t.id==='split'){html=fl+'<div class="input-group"><label>Halaman (contoh: 1-3,5,7-9) — kosongkan untuk pisah per halaman</label><input type="text" id="partsInput" placeholder="1-3,5"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Pisahkan</button>'+st;}
else if(t.id==='rotate'){html=fl+'<div class="input-group"><label>Sudut rotasi</label><select id="angleSel"><option value="90">90°</option><option value="180">180°</option><option value="270">270°</option></select></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Putar</button>'+st;}
else if(t.id==='extract-pages'||t.id==='delete-pages'){html=fl+'<div class="input-group"><label>Halaman (contoh: 1,3,5-8)</label><input type="text" id="pagesInput" placeholder="1,3,5"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Proses</button>'+st;}
else if(t.id==='reorder'){html=fl+'<div class="input-group"><label>Urutan baru (contoh: 3,1,2,4)</label><input type="text" id="orderInput" placeholder="3,1,2"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Atur Ulang</button>'+st;}
else if(t.id==='pdf-to-image'){html=fl+'<div class="input-group"><label>Format</label><select id="fmtSel"><option value="png">PNG</option><option value="jpg">JPG</option></select></div><div class="input-group"><label>DPI</label><input type="number" id="dpiInput" value="150" min="72" max="300"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi</button>'+st;}
else if(t.id==='protect'||t.id==='unlock'){html=fl+'<div class="input-group"><label>Password</label><input type="password" id="pwInput" placeholder="Masukkan password"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Proses</button>'+st;}
else if(t.id==='watermark'){html=fl+'<div class="input-group"><label>Teks Watermark</label><input type="text" id="wmInput" value="SOFIA"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Tambah Watermark</button>'+st;}
else if(t.id==='remove-watermark'){html=fl+'<div class="input-group"><label>Teks spesifik (opsional)</label><input type="text" id="wmInput" placeholder="Kosongkan untuk auto-detect"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Hapus Watermark</button>'+st;}
else if(t.id==='pdf-to-csv'){html=fl+'<div class="input-group"><label>Delimiter</label><select id="delimSel"><option value=",">Koma (,)</option><option value=";">Titik Koma (;)</option><option value="\\t">Tab</option></select></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Ekstrak CSV</button>'+st;}
else if(t.id==='pdf-to-excel'){html=fl+'<div class="input-group"><label>Mode</label><select id="modeSel"><option value="per_sheet">Per Halaman</option><option value="merge">Gabung 1 Sheet</option></select></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi ke Excel</button>'+st;}
else if(t.id==='pdf-to-excel-cam'){html=fl+'<p style="color:#94a3b8;font-size:.85rem;margin-bottom:12px">Khusus file Detail CAM Prioritisasi BSN. Watermark dihapus otomatis, semua halaman jadi 1 sheet.</p><button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi ke Excel</button>'+st;}
else if(t.id==='md-to-pdf'){html='<div class="input-group"><label>Markdown</label><textarea id="mdInput" placeholder="# Hello World"></textarea></div><div class="input-group"><label>Ukuran Kertas</label><select id="paperSel"><option value="A4">A4</option><option value="Letter">Letter</option></select></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi ke PDF</button>'+st;}
else if(t.id==='html-to-pdf'){html='<div class="input-group"><label>HTML</label><textarea id="htmlInput" placeholder="<h1>Hello</h1>"></textarea></div><div class="input-group"><label>Ukuran Kertas</label><select id="paperSel"><option value="A4">A4</option><option value="Letter">Letter</option></select></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Konversi ke PDF</button>'+st;}
else if(t.id==='mp3-trim'){html=fl.replace('accept=".pdf,.jpg,.jpeg,.png,.md,.html,.htm,.mp3"','accept=".mp3"')+'<div class="input-group"><label>Detik mulai</label><input type="number" id="startInput" value="0" min="0" step="0.1"></div><div class="input-group"><label>Detik selesai</label><input type="number" id="endInput" value="10" min="0" step="0.1"></div><button class="btn" id="btn" style="width:100%;margin-top:12px">Potong MP3</button>'+st;}
else if(t.id==='get-pdf-info'){html=fl+'<button class="btn" id="btn" style="width:100%;margin-top:12px">Lihat Info</button>'+st;}
else{html=fl+'<button class="btn" id="btn" style="width:100%;margin-top:12px">Proses</button>'+st;}
c.innerHTML=html;
setupUpload(t);
document.getElementById('btn').onclick=()=>process(t);
}
let currentFiles=[];
function setupUpload(t){
const drop=document.getElementById('drop');
const inp=document.getElementById('fileInput');
drop.onclick=()=>inp.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag');};
drop.ondragleave=()=>drop.classList.remove('drag');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');addFiles(e.dataTransfer.files);};
inp.onchange=()=>addFiles(inp.files);
}
function addFiles(files){
currentFiles=[...currentFiles,...Array.from(files)];
renderFiles();
}
function renderFiles(){
const fl=document.getElementById('fileList');
fl.innerHTML=currentFiles.map((f,i)=>`<div class="file-item"><span>${f.name}</span><span class="remove" onclick="removeFile(${i})">✕</span></div>`).join('');
}
function removeFile(i){currentFiles.splice(i,1);renderFiles();}
async function process(t){
if(t.id!=='md-to-pdf'&&t.id!=='html-to-pdf'&&currentFiles.length===0){alert('Pilih file terlebih dahulu');return;}
const btn=document.getElementById('btn');
const status=document.getElementById('status');
btn.disabled=true;status.className='status show processing';status.textContent='Memproses...';
const fd=new FormData();
fd.append('tool',t.id);
currentFiles.forEach(f=>fd.append('files',f));
if(t.id==='rotate')fd.append('angle',document.getElementById('angleSel').value);
if(t.id==='split'){const v=document.getElementById('partsInput').value.trim();if(v){const parts=v.split(',').map(s=>{const m=s.trim().split('-');return{pages:m.length===2?Array.from({length:parseInt(m[1])-parseInt(m[0])+1},(_,i)=>parseInt(m[0])+i):[parseInt(m[0])]}});fd.append('parts',JSON.stringify(parts));}}
if(t.id==='extract-pages'||t.id==='delete-pages'){const v=document.getElementById('pagesInput').value.trim();if(v){const p=v.split(',').map(s=>{const m=s.trim().split('-');return m.length===2?Array.from({length:parseInt(m[1])-parseInt(m[0])+1},(_,i)=>parseInt(m[0])+i):parseInt(m[0])}).flat();fd.append('pages',JSON.stringify(p));}}
if(t.id==='reorder'){const v=document.getElementById('orderInput').value.trim();if(v)fd.append('order',JSON.stringify(v.split(',').map(Number)));}
if(t.id==='pdf-to-image'){fd.append('fmt',document.getElementById('fmtSel').value);fd.append('dpi',document.getElementById('dpiInput').value);}
if(t.id==='protect'||t.id==='unlock')fd.append('password',document.getElementById('pwInput').value);
if(t.id==='watermark'||t.id==='remove-watermark')fd.append('text',document.getElementById('wmInput').value);
if(t.id==='pdf-to-csv')fd.append('delimiter',document.getElementById('delimSel').value);
if(t.id==='pdf-to-excel')fd.append('excel_mode',document.getElementById('modeSel').value);
if(t.id==='md-to-pdf'){fd.append('text',document.getElementById('mdInput').value);fd.append('paper',document.getElementById('paperSel').value);}
if(t.id==='html-to-pdf'){fd.append('text',document.getElementById('htmlInput').value);fd.append('paper',document.getElementById('paperSel').value);}
if(t.id==='mp3-trim'){fd.append('start',document.getElementById('startInput').value);fd.append('end',document.getElementById('endInput').value);}
try{
const r=await fetch('/api/process',{method:'POST',body:fd});
if(!r.ok){const e=await r.json();throw new Error(e.detail||'Gagal');}
const blob=await r.blob();
const url=URL.createObjectURL(blob);
const a=document.createElement('a');
a.href=url;
a.download=r.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g,'')||'result';
a.click();
URL.revokeObjectURL(url);
status.className='status show success';status.textContent='✅ Selesai! File sudah diunduh.';
}catch(e){status.className='status show error';status.textContent='❌ '+e.message;}
btn.disabled=false;
}
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"\n{'='*50}")
    print(f"  Sofia PDF Tools — Open Edition")
    print(f"  Running on: http://0.0.0.0:{port}")
    print(f"  No login, no limits")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
