import csv, io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def _pdfplumber_extract(inp: Path, out_dir: Path, delimiter: str):
    import pdfplumber
    outs=[]
    # lattice-like tuning for better neatness
    t_settings={"vertical_strategy":"lines","horizontal_strategy":"lines","intersection_tolerance":5,"snap_tolerance":3,"join_tolerance":3}
    with pdfplumber.open(str(inp)) as pdf:
        def process_page(args):
            pi, page = args
            try:
                tables=page.extract_tables(table_settings=t_settings)
                if not tables:
                    tables=page.extract_tables()
            except: tables=[]
            local=[]
            if not tables:
                txt=page.extract_text() or ""
                if not txt.strip(): return local
                rows=[[line] for line in txt.splitlines() if line.strip()]
                if not rows: return local
                o=out_dir / f"page_{pi+1}.csv"
                with open(o,"w",newline="",encoding="utf-8") as f:
                    w=csv.writer(f, delimiter=delimiter)
                    w.writerows(rows)
                local.append(o)
            else:
                for ti, tbl in enumerate(tables):
                    o=out_dir / f"page_{pi+1}_table_{ti+1}.csv"
                    with open(o,"w",newline="",encoding="utf-8") as f:
                        w=csv.writer(f, delimiter=delimiter)
                        for row in tbl:
                            w.writerow([c if c is not None else "" for c in row])
                    local.append(o)
            return local
        # parallel per page
        with ThreadPoolExecutor(max_workers=4) as ex:
            results=list(ex.map(process_page, enumerate(pdf.pages)))
            for r in results: outs.extend(r)
    return outs

def _camelot_extract(inp: Path, out_dir: Path, delimiter: str):
    import shutil, time
    # fast skip if ghostscript not available (Windows dev) — avoid 5-min hang like Stirling reports
    if not shutil.which("gs") and not shutil.which("gswin64c") and not shutil.which("gswin32c"):
        return []
    import camelot
    outs=[]
    # lattice with timeout guard (Stirling lattice is <10s for 50 pages)
    def _try(flavor):
        try:
            # per-file timeout via wall time
            start=time.time()
            tables=camelot.read_pdf(str(inp), pages='all', flavor=flavor, suppress_stdout=True)
            if time.time()-start > 25: return []
            if tables and len(tables)>0 and tables[0].df.shape[0]>0:
                local=[]
                for i, t in enumerate(tables):
                    o=out_dir / f"camelot_{flavor}_{i+1}.csv"
                    t.df.to_csv(str(o), index=False, header=False, sep=delimiter)
                    if o.stat().st_size>0: local.append(o)
                return local
        except: return []
        return []
    outs=_try('lattice')
    if outs: return outs
    outs=_try('stream')
    return outs

def pdf_to_csv(inp: Path, out_dir: Path, delimiter=",", header=True):
    """Stirling-like: camelot lattice→stream → pdfplumber parallel. Fast & neat."""
    outs=[]
    # 1) try camelot (fast, neat) if available — matches Stirling Java lattice
    try:
        outs=_camelot_extract(inp, out_dir, delimiter)
        if outs: return outs
    except ImportError:
        pass
    except Exception as e:
        # camelot failed (no ghostscript/java) → fallback
        pass
    # 2) pdfplumber parallel with tuned settings
    outs=_pdfplumber_extract(inp, out_dir, delimiter)
    if not outs:
        raise ValueError("No tables or text could be extracted. Try OCR for scanned PDFs.")
    return outs

def preview_csv(path: Path, limit=20):
    import csv
    rows=[]
    with open(path, encoding="utf-8", errors="ignore") as f:
        r=csv.reader(f)
        for i,row in enumerate(r):
            if i>=limit: break
            rows.append(row)
    return rows
