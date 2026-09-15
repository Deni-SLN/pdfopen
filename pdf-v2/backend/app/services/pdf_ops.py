import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter
from pathlib import Path
from PIL import Image
import io, os

def merge_pdfs(inputs: list[Path], output: Path):
    doc = fitz.open()
    for p in inputs:
        src = fitz.open(str(p))
        doc.insert_pdf(src)
        src.close()
    doc.save(str(output)); doc.close()
    return output

def split_pdf(inp: Path, out_dir: Path, ranges: str = None):
    # ranges like "1-3,5"
    reader = PdfReader(str(inp))
    n = len(reader.pages)
    out_files = []
    if not ranges:
        for i, pg in enumerate(reader.pages):
            w = PdfWriter(); w.add_page(pg)
            o = out_dir / f"page_{i+1}.pdf"
            with open(o,"wb") as f: w.write(f)
            out_files.append(o)
        return out_files[0] if out_files else None
    # simple split by ranges param "1-2"
    # for now return first range as single pdf
    return None

def rotate_pdf(inp: Path, output: Path, angle: int = 90):
    doc = fitz.open(str(inp))
    for page in doc:
        page.set_rotation((page.rotation + angle) % 360)
    doc.save(str(output)); doc.close()
    return output

def delete_pages(inp: Path, output: Path, pages: list[int]):
    # pages 1-indexed to delete
    reader = PdfReader(str(inp))
    writer = PdfWriter()
    for i, pg in enumerate(reader.pages, 1):
        if i not in pages:
            writer.add_page(pg)
    with open(output,"wb") as f: writer.write(f)
    return output

def extract_pages(inp: Path, output: Path, pages: list[int]):
    reader = PdfReader(str(inp))
    writer = PdfWriter()
    for i in pages:
        if 1 <= i <= len(reader.pages):
            writer.add_page(reader.pages[i-1])
    with open(output,"wb") as f: writer.write(f)
    return output

def reorder_pages(inp: Path, output: Path, order: list[int]):
    return extract_pages(inp, output, order)

def compress_pdf(inp: Path, output: Path, quality: str="medium"):
    # use PyMuPDF garbage + deflate
    doc = fitz.open(str(inp))
    doc.save(str(output), garbage=4, deflate=True, clean=True)
    doc.close()
    return output

def pdf_to_images(inp: Path, out_dir: Path, fmt="png", dpi=150):
    doc = fitz.open(str(inp))
    out = []
    zoom = dpi/72
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        o = out_dir / f"page_{i+1}.{fmt}"
        pix.save(str(o))
        out.append(o)
    doc.close()
    return out

def images_to_pdf(images: list[Path], output: Path):
    imgs = [Image.open(str(p)).convert("RGB") for p in images]
    if not imgs: raise ValueError("No images")
    imgs[0].save(str(output), save_all=True, append_images=imgs[1:])
    return output

def protect_pdf(inp: Path, output: Path, password: str):
    reader = PdfReader(str(inp)); writer = PdfWriter()
    for pg in reader.pages: writer.add_page(pg)
    writer.encrypt(password)
    with open(output,"wb") as f: writer.write(f)
    return output

def unlock_pdf(inp: Path, output: Path, password: str):
    reader = PdfReader(str(inp))
    if reader.is_encrypted:
        reader.decrypt(password)
    writer = PdfWriter()
    for pg in reader.pages: writer.add_page(pg)
    with open(output,"wb") as f: writer.write(f)
    return output

def add_watermark(inp: Path, output: Path, text: str):
    doc = fitz.open(str(inp))
    for page in doc:
        page.insert_text((50,50), text, fontsize=40, color=(0.8,0.8,0.8), rotate=45)
    doc.save(str(output)); doc.close()
    return output

def remove_watermark(inp: Path, output: Path, text: str = ""):
    """Remove watermark: hapus text watermark (cari text light-gray/rotated) dan image watermark. Jika text spesifik diberi, hapus yang mengandung text tersebut."""
    doc = fitz.open(str(inp))
    target = text.strip().lower() if text else ""
    for page in doc:
        # 1. hapus annots watermark (jika ada)
        try:
            for annot in list(page.annots() or []):
                # annot watermark biasanya FreeText dengan opacity rendah
                try:
                    # coba hapus semua annot yang terlihat seperti watermark
                    page.delete_annot(annot)
                except: pass
        except: pass
        # 2. hapus drawings dengan warna terang (watermark vector)
        try:
            drawings = page.get_drawings()
            for d in drawings:
                col = d.get("color") or [0,0,0]
                # warna terang abu-abu 0.7-0.9
                if isinstance(col, (list,tuple)) and len(col)>=3 and all(0.65 <= c <= 0.95 for c in col[:3]):
                    # hapus dengan overlay putih (tidak ada API delete drawing, jadi redact)
                    try:
                        rect = fitz.Rect(d["rect"])
                        page.add_redact_annot(rect, fill=(1,1,1))
                    except: pass
            # apply redacts untuk drawings
            try: page.apply_redactions()
            except: pass
        except: pass
        # 3. hapus text watermark via redaction: cari instance text
        try:
            # jika target spesifik, hanya hapus itu
            if target:
                insts = page.search_for(target)
                for r in insts:
                    page.add_redact_annot(r, fill=(1,1,1))
                if insts:
                    page.apply_redactions()
                    continue
            # else: hapus text yang terlihat seperti watermark (size besar, warna terang, atau diagonal)
            d = page.get_text("dict")
            for block in d.get("blocks", []):
                if block.get("type")!=0: continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span.get("text","").strip()
                        if not txt: continue
                        size = span.get("size", 0)
                        color = span.get("color", 0)
                        # color int -> rgb
                        r = (color >> 16) & 255
                        g = (color >> 8) & 255
                        b = color & 255
                        is_light = r>150 and g>150 and b>150
                        is_large = size>=18
                        # jika spesifik target, hanya hapus yang mengandung target
                        if target and target not in txt.lower():
                            continue
                        # jika tidak ada target, hapus yang light+large (khas watermark)
                        if (is_light and is_large) or (target and target in txt.lower()):
                            try:
                                # cari bbox span
                                rect = fitz.Rect(span["bbox"])
                                page.add_redact_annot(rect, fill=(1,1,1))
                            except: pass
            page.apply_redactions()
        except: pass
        # 4. fallback: jika masih ada image watermark, hapus image (opsional)
        # kita tidak hapus semua image, hanya jika target spesifik tidak ditemukan
    doc.save(str(output), garbage=4, deflate=True, clean=True)
    doc.close()
    return output

def add_page_numbers(inp: Path, output: Path):
    doc = fitz.open(str(inp))
    for i, page in enumerate(doc):
        page.insert_text((page.rect.width/2 -20, page.rect.height-20), str(i+1), fontsize=10)
    doc.save(str(output)); doc.close()
    return output

def pdf_info(inp: Path):
    doc = fitz.open(str(inp))
    return {"pages": doc.page_count, "metadata": doc.metadata}
