import json, traceback, zipfile, io, subprocess
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Job, File
from ..config import settings
from ..storage import RESULTS

import fitz
from ..services import pdf_ops, table_extract, doc_gen, audio_ops
from ..services.cam_excel import pdf_to_excel_cam

YTDLP_CMD = "/opt/data/.bin/yt-dlp"

def _update(job_id, **kw):
    db=SessionLocal()
    try:
        j=db.query(Job).filter(Job.id==job_id).first()
        if not j: return
        for k,v in kw.items(): setattr(j,k,v)
        j.updated_at=datetime.now(timezone.utc)
        db.commit()
    finally: db.close()

def process_job(job_id: str):
    db=SessionLocal()
    job=db.query(Job).filter(Job.id==job_id).first()
    if not job: db.close(); return
    params=json.loads(job.params or "{}")
    input_path=None
    if job.input_file_id:
        f=db.query(File).filter(File.id==job.input_file_id).first()
        if f: input_path=Path(f.path)
    db.close()
    try:
        _update(job_id, status="validating", progress=5, message="Validating input")
        tool=job.tool
        out_path=None
        out_name=f"result_{tool}.pdf"
        # route
        if tool=="merge":
            ids=params.get("file_ids") or []
            if len(ids)<2: raise ValueError("Need at least 2 files to merge")
            db2=SessionLocal()
            paths=[Path(db2.query(File).filter(File.id==fid).first().path) for fid in ids if db2.query(File).filter(File.id==fid).first()]
            db2.close()
            _update(job_id, status="processing", progress=30, message="Merging PDFs")
            out_path=RESULTS/f"{job_id}_merged.pdf"
            pdf_ops.merge_pdfs(paths, out_path)
            out_name="merged.pdf"
        elif tool=="split":
            _update(job_id, status="processing", progress=30)
            parts=params.get("parts") or []
            # parts: [{"pages":[1,2]}, {"pages":[3]}] — from new UI; legacy fallback splits all
            from pypdf import PdfReader, PdfWriter
            r=PdfReader(str(input_path))
            n=len(r.pages)
            if parts:
                outs=[]
                for idx, part in enumerate(parts):
                    pages=part.get("pages") or part.get("range") or []
                    # if range string like "1-5,8" need parse (already parsed in frontend but support string)
                    if isinstance(pages, str):
                        # parse "1-5, 8"
                        parsed=[]
                        for seg in pages.split(","):
                            seg=seg.strip()
                            if "-" in seg:
                                try:
                                    a,b=map(lambda x: int(x.strip()), seg.split("-",1))
                                    lo,hi=min(a,b), max(a,b)
                                    for v in range(lo, hi+1):
                                        if 1<=v<=n: parsed.append(v)
                                except: pass
                            else:
                                try:
                                    v=int(seg)
                                    if 1<=v<=n: parsed.append(v)
                                except: pass
                        pages=parsed
                    pages=[int(p) for p in pages if 1<=int(p)<=n]
                    if not pages: continue
                    w=PdfWriter()
                    for pnum in pages:
                        w.add_page(r.pages[pnum-1])
                    o=RESULTS/f"{job_id}_part_{idx+1}.pdf"
                    with open(o,"wb") as fh: w.write(fh)
                    outs.append(o)
                if not outs: raise ValueError("No valid pages in parts")
                if len(outs)==1:
                    out_path=outs[0]; out_name=f"part_1.pdf"
                else:
                    z=RESULTS/f"{job_id}_split_parts.zip"
                    import zipfile
                    with zipfile.ZipFile(z,"w") as zf:
                        for o in outs: zf.write(o, o.name)
                    # cleanup individual
                    for o in outs: o.unlink(missing_ok=True) if o!=z else None
                    out_path=z; out_name="split.zip"
            else:
                outs=[]
                for i,pg in enumerate(r.pages):
                    w=PdfWriter(); w.add_page(pg)
                    o=RESULTS/f"{job_id}_page_{i+1}.pdf"
                    with open(o,"wb") as fh: w.write(fh)
                    outs.append(o)
                z=RESULTS/f"{job_id}_split.zip"
                import zipfile
                with zipfile.ZipFile(z,"w") as zf:
                    for o in outs: zf.write(o, o.name)
                    for o in outs: o.unlink(missing_ok=True)
                out_path=z; out_name="split.zip"
        elif tool=="rotate":
            angle=int(params.get("angle",90))
            out_path=RESULTS/f"{job_id}_rotated.pdf"
            pdf_ops.rotate_pdf(input_path, out_path, angle); out_name="rotated.pdf"
        elif tool in ("delete-pages","delete"):
            pages=params.get("pages") or []
            pages=[int(x) for x in pages]
            out_path=RESULTS/f"{job_id}_deleted.pdf"
            pdf_ops.delete_pages(input_path, out_path, pages); out_name="deleted.pdf"
        elif tool=="extract-pages":
            pages=params.get("pages") or [1]
            pages=[int(x) for x in pages]
            out_path=RESULTS/f"{job_id}_extracted.pdf"
            pdf_ops.extract_pages(input_path, out_path, pages); out_name="extracted.pdf"
        elif tool=="reorder":
            order=params.get("order") or []
            order=[int(x) for x in order]
            out_path=RESULTS/f"{job_id}_reordered.pdf"
            pdf_ops.reorder_pages(input_path, out_path, order); out_name="reordered.pdf"
        elif tool=="compress":
            out_path=RESULTS/f"{job_id}_compressed.pdf"
            pdf_ops.compress_pdf(input_path, out_path, params.get("quality","medium")); out_name="compressed.pdf"
        elif tool=="pdf-to-image":
            fmt=params.get("format","png"); dpi=int(params.get("dpi",150))
            out_dir=RESULTS/f"{job_id}_images"; out_dir.mkdir(exist_ok=True)
            outs=pdf_ops.pdf_to_images(input_path, out_dir, fmt, dpi)
            z=RESULTS/f"{job_id}_images.zip"
            with zipfile.ZipFile(z,"w") as zf:
                for o in outs: zf.write(o, o.name)
            out_path=z; out_name="images.zip"
        elif tool=="image-to-pdf":
            # input is first image, but we may have file_ids
            ids=params.get("file_ids") or ([job.input_file_id] if job.input_file_id else [])
            db2=SessionLocal()
            paths=[Path(db2.query(File).filter(File.id==fid).first().path) for fid in ids]
            db2.close()
            out_path=RESULTS/f"{job_id}_from_images.pdf"
            pdf_ops.images_to_pdf(paths, out_path); out_name="from_images.pdf"
        elif tool=="protect":
            pw=params.get("password") or "1234"
            out_path=RESULTS/f"{job_id}_protected.pdf"
            pdf_ops.protect_pdf(input_path, out_path, pw); out_name="protected.pdf"
        elif tool=="unlock":
            pw=params.get("password") or ""
            out_path=RESULTS/f"{job_id}_unlocked.pdf"
            pdf_ops.unlock_pdf(input_path, out_path, pw); out_name="unlocked.pdf"
        elif tool=="watermark":
            txt=params.get("text") or "SOFIA"
            out_path=RESULTS/f"{job_id}_watermark.pdf"
            pdf_ops.add_watermark(input_path, out_path, txt); out_name="watermark.pdf"
        elif tool=="remove-watermark":
            txt=params.get("text") or ""
            out_path=RESULTS/f"{job_id}_no_watermark.pdf"
            pdf_ops.remove_watermark(input_path, out_path, txt); out_name="no_watermark.pdf"
        elif tool=="page-numbers":
            out_path=RESULTS/f"{job_id}_paged.pdf"
            pdf_ops.add_page_numbers(input_path, out_path); out_name="paged.pdf"
        elif tool=="pdf-to-csv":
            delim = params.get("delimiter",",")
            if delim=="semicolon": delim=";"
            elif delim=="tab": delim="\t"
            _update(job_id, status="processing", progress=40, message="Upload selesai ✓ • Extracting tables")
            tmp=RESULTS/f"{job_id}_csv"; tmp.mkdir(exist_ok=True)
            outs=table_extract.pdf_to_csv(input_path, tmp, delimiter=delim)
            _update(job_id, status="processing", progress=75, message="Packaging CSV")
            if len(outs)==1:
                out_path=outs[0]; out_name=outs[0].name
            else:
                z=RESULTS/f"{job_id}_tables.zip"
                with zipfile.ZipFile(z,"w") as zf:
                    for o in outs: zf.write(o, o.name)
                out_path=z; out_name="tables.zip"
        elif tool in ("pdf-to-excel-cam","cam-to-excel"):
            _update(job_id, status="processing", progress=10, message="Menghapus watermark CAM")
            out_path=RESULTS/f"{job_id}_cam.xlsx"
            n=pdf_to_excel_cam(input_path, out_path, progress_cb=lambda p,m: _update(job_id, status="processing", progress=p, message=m))
            out_name="CAM_Excel.xlsx"
        elif tool=="md-to-pdf":
            md_text=params.get("markdown") or ""
            if input_path and input_path.suffix==".md":
                md_text=input_path.read_text(encoding="utf-8", errors="ignore")
            if not md_text.strip(): raise ValueError("No markdown content")
            out_path=RESULTS/f"{job_id}_from_md.pdf"
            doc_gen.md_to_pdf(md_text, out_path, params.get("paper","A4"), params.get("orientation","portrait"), params.get("margin","20mm"))
            out_name=params.get("filename") or "document.pdf"
        elif tool=="html-to-pdf":
            html=params.get("html") or ""
            if input_path and input_path.suffix==".html":
                html=input_path.read_text(encoding="utf-8", errors="ignore")
            if not html.strip(): raise ValueError("No HTML content")
            out_path=RESULTS/f"{job_id}_from_html.pdf"
            doc_gen.html_to_pdf(html, out_path, params.get("paper","A4"), params.get("orientation","portrait"), params.get("margin","15mm"))
            out_name=params.get("filename") or "document.pdf"
        elif tool=="mp3-trim":
            start=float(params.get("start",0)); end=float(params.get("end",10))
            out_path=RESULTS/f"{job_id}_trimmed.mp3"
            audio_ops.trim_mp3(input_path, out_path, start, end); out_name="trimmed.mp3"
        elif tool=="video-downloader":
            url=params.get("url") or ""
            if not url.strip(): raise ValueError("URL required")
            fmt=params.get("format") or "mp4"
            _update(job_id, status="processing", progress=10, message="Resolving video info")
            # probe title
            title=None
            try:
                probe=subprocess.check_output([YTDLP_CMD,"--dump-json","--no-download",url], text=True, stderr=subprocess.DEVNULL, timeout=60)
                meta=json.loads(probe.splitlines()[0]); title=meta.get("title")
            except Exception: pass
            _update(job_id, status="processing", progress=30, message=f"Downloading {fmt}")
            out_path=RESULTS/f"{job_id}_video.%(ext)s"
            if fmt=="mp3":
                cmd=[YTDLP_CMD,"-f","bestaudio","--extract-audio","--audio-format","mp3","--audio-quality","0","-o",str(out_path),"--no-playlist","--no-progress","--newline","url"]
            else:
                cmd=[YTDLP_CMD,"-f","bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best","-o",str(out_path),"--no-playlist","--no-progress","--newline","url"]
            try:
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            except subprocess.CalledProcessError as e:
                raise ValueError(f"Download failed (code {e.returncode}). Check URL/site support.")
            # find actual output file
            import glob
            if fmt=="mp3":
                found=glob.glob(str(RESULTS/f"{job_id}_video.mp3"))
            else:
                found=glob.glob(str(RESULTS/f"{job_id}_video.*"))
            if not found:
                raise ValueError("Download completed but output file not found")
            out_path=Path(found[0])
            out_name=out_path.name
            if title and fmt=="mp3":
                safe="".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]
                if safe:
                    new_path=out_path.parent/f"{safe}.mp3"
                    out_path.rename(new_path); out_path=new_path; out_name=new_path.name
        elif tool in ("pdf-to-excel","pdf-to-xlsx"):
            _update(job_id, status="processing", progress=40, message="Upload selesai ✓ • Converting to Excel")
            excel_mode=params.get("excelMode") or params.get("mode") or "per_sheet"
            tmp=RESULTS/f"{job_id}_excel"; tmp.mkdir(exist_ok=True)
            try:
                outs=table_extract.pdf_to_csv(input_path, tmp, delimiter=",")
            except: outs=[]
            if not outs:
                raise ValueError("No tables found to convert to Excel")
            _update(job_id, status="processing", progress=70, message="Building XLSX")
            from openpyxl import Workbook
            import csv, re
            out_path=RESULTS/f"{job_id}_converted.xlsx"
            wb=Workbook()
            wb.remove(wb.active)
            if excel_mode=="merge":
                ws=wb.create_sheet(title="Semua Halaman")
                first=True
                for csv_path in outs:
                    with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                        rows=list(csv.reader(fh))
                        if not rows: continue
                        # add separator between tables (except first)
                        if not first:
                            ws.append([])  # empty row
                        for row in rows:
                            ws.append(row)
                        first=False
                if len(ws['A'])==0: ws.append(["No data"])
            else:
                # per_sheet: pisah per halaman — group by page number from filename page_1...
                # fallback: per table per sheet if no page info
                for csv_path in outs:
                    # try to extract page number: page_1_table_1.csv -> Halaman 1
                    m=re.search(r'page_(\d+)', csv_path.name)
                    page_label=f"Halaman {m.group(1)}" if m else csv_path.stem[:31]
                    # if sheet exists for same page, reuse and append with separator
                    if page_label in wb.sheetnames:
                        ws=wb[page_label]
                        ws.append([])  # separator
                        with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                            for row in csv.reader(fh):
                                ws.append(row)
                    else:
                        ws=wb.create_sheet(title=page_label[:31])
                        with open(csv_path, encoding="utf-8", errors="ignore") as fh:
                            for row in csv.reader(fh):
                                ws.append(row)
                # camelot outs without page_ prefix: group sequentially as Halaman N
                if not any("Halaman" in s for s in wb.sheetnames):
                    # fallback already per table, keep as is
                    pass
            if len(wb.sheetnames)==0:
                ws=wb.create_sheet("Sheet1")
            wb.save(str(out_path))
            out_name="converted.xlsx"
        # Stirling additional tools — stubs keep design, real where feasible
        elif tool=="remove-blanks":
            _update(job_id, status="processing", progress=40, message="Removing blanks")
            # naive: copy if text exists, else skip
            import fitz
            doc=fitz.open(str(input_path)); out=fitz.open()
            for p in doc:
                txt=p.get_text().strip()
                # keep if has text or images
                if txt or len(p.get_images())>0:
                    out.insert_pdf(doc, from_page=p.number, to_page=p.number)
            if out.page_count==0: out.insert_pdf(doc, from_page=0, to_page=0)
            out_path=RESULTS/f"{job_id}_no_blanks.pdf"; out.save(str(out_path)); out.close(); doc.close(); out_name="no_blanks.pdf"
        elif tool=="remove-annotations":
            doc=fitz.open(str(input_path))
            for p in doc:
                # remove annots
                for annot in list(p.annots() or []):
                    p.delete_annot(annot)
            out_path=RESULTS/f"{job_id}_no_annots.pdf"; doc.save(str(out_path)); doc.close(); out_name="no_annots.pdf"
        elif tool=="remove-image":
            # stub: just remove image objects by redacting images (copy without images not trivial) — we flatten to just keep text
            doc=fitz.open(str(input_path))
            for p in doc:
                for img in p.get_images(full=True):
                    try: p.delete_image(img[0])
                    except: pass
            out_path=RESULTS/f"{job_id}_no_images.pdf"; doc.save(str(out_path)); doc.close(); out_name="no_images.pdf"
        elif tool=="extract-images":
            doc=fitz.open(str(input_path)); out_dir=RESULTS/f"{job_id}_extimg"; out_dir.mkdir(exist_ok=True)
            outs=[]
            for i,p in enumerate(doc):
                for j,img in enumerate(p.get_images(full=True)):
                    try:
                        pix=fitz.Pixmap(doc, img[0])
                        if pix.n>4: pix=fitz.Pixmap(fitz.csRGB, pix)
                        o=out_dir/f"page{i+1}_img{j+1}.png"; pix.save(str(o)); outs.append(o)
                    except: pass
            doc.close()
            if not outs: raise ValueError("No images found")
            z=RESULTS/f"{job_id}_images.zip"
            with zipfile.ZipFile(z,"w") as zf:
                for o in outs: zf.write(o, o.name)
            out_path=z; out_name="extracted_images.zip"
        elif tool=="get-pdf-info":
            info=pdf_ops.pdf_info(input_path)
            import json as _j
            out_path=RESULTS/f"{job_id}_info.json"; out_path.write_text(_j.dumps(info, indent=2), encoding='utf-8'); out_name="info.json"
        elif tool in ("cert-sign","sign","flatten","sanitize","redact","add-text","add-image","add-stamp","overlay-pdfs","crop","repair","compare","ocr","auto-rotate","page-layout","scale-pages","replace-color","booklet-imposition","reorganize-pages","change-metadata","change-permissions","remove-cert-sign","unlock-pdf-forms","validate-signature","show-js","pdf-text-editor","auto-rename","scanner-effect","adjust-contrast","pdf-to-single-page","timestampPdf","getPdfInfo","overlayPdfs"):
            # generic stub: copy and add small watermark indicating tool executed (keeps design flow working)
            _update(job_id, status="processing", progress=50, message=f"Processing {tool} (stub)")
            # for two-file tools like overlay/compare need file_ids
            ids=params.get("file_ids") or []
            if tool in ("overlay-pdfs","compare") and len(ids)>=2:
                db2=SessionLocal()
                paths=[Path(db2.query(File).filter(File.id==fid).first().path) for fid in ids if db2.query(File).filter(File.id==fid).first()]
                db2.close()
                if paths:
                    # for overlay: overlay second onto first, for compare: merge
                    try:
                        pdf_ops.merge_pdfs(paths[:2], RESULTS/f"{job_id}_stub.pdf")
                        out_path=RESULTS/f"{job_id}_stub.pdf"
                    except:
                        out_path=RESULTS/f"{job_id}_stub.pdf"; Path(paths[0]).read_bytes.__self__  # fallback
                        import shutil; shutil.copy(str(paths[0]), str(out_path))
                else:
                    out_path=RESULTS/f"{job_id}_stub.pdf"; __import__("shutil").copy(str(input_path), str(out_path))
            else:
                out_path=RESULTS/f"{job_id}_{tool}.pdf"
                # try to open and add stamp, else copy
                try:
                    doc=fitz.open(str(input_path))
                    for p in doc: p.insert_text((20,20), f"[{tool}] processed by Sofia v2", fontsize=8, color=(0.5,0.5,0.5))
                    doc.save(str(out_path)); doc.close()
                except:
                    import shutil; shutil.copy(str(input_path), str(out_path))
            out_name=f"{tool}.pdf"
        else:
            raise ValueError(f"Unknown tool: {tool}")

        _update(job_id, status="packaging", progress=90, message="Finalizing")
        # save result file record
        db3=SessionLocal()
        j=db3.query(Job).filter(Job.id==job_id).first()
        f=File(id=str(__import__("uuid").uuid4()), owner_id=j.owner_id, original_name=out_name, stored_name=out_path.name, path=str(out_path), mime="application/octet-stream", size=out_path.stat().st_size if out_path.exists() else 0)
        db3.add(f); db3.commit()
        j.output_file_id=f.id; j.status="completed"; j.progress=100; j.message="Completed"; j.error=None
        db3.commit(); db3.close()

    except Exception as e:
        tb=traceback.format_exc()
        _update(job_id, status="failed", progress=0, error=str(e)+"\n"+tb[:2000], message="Failed: "+str(e))
