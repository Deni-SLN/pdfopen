from pathlib import Path
import markdown

MD_CSS = """
body{font-family: 'Segoe UI', Arial, sans-serif; line-height:1.6; max-width:800px; margin:40px auto; padding:0 20px; color:#1a1a1a}
h1,h2,h3{color:#0f172a; margin-top:1.2em}
table{border-collapse:collapse; width:100%} th,td{border:1px solid #cbd5e1; padding:6px 10px; text-align:left}
code{background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:0.9em}
pre{background:#0f172a; color:#e2e8f0; padding:14px; border-radius:8px; overflow:auto}
blockquote{border-left:4px solid #6366f1; padding-left:12px; color:#475569}
"""

def _weasy_available():
    try:
        from weasyprint import HTML as _H
        return True
    except: return False

def _fallback_pdf(text: str, output: Path, title="Document"):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(str(output), pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story=[]
    for line in text.splitlines():
        if not line.strip():
            story.append(Spacer(1,8))
        else:
            # escape xml
            esc=line.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            story.append(Paragraph(esc, styles['Normal']))
            story.append(Spacer(1,4))
    doc.build(story)
    return output

def md_to_pdf(md_text: str, output: Path, paper="A4", orientation="portrait", margin="20mm"):
    try:
        if _weasy_available():
            from weasyprint import HTML
            html_body = markdown.markdown(md_text, extensions=["tables","fenced_code","toc","sane_lists"])
            html = f"<html><head><meta charset='utf-8'><style>@page{{size:{paper} {orientation}; margin:{margin}}} {MD_CSS}</style></head><body>{html_body}</body></html>"
            HTML(string=html).write_pdf(str(output))
            return output
    except Exception as e:
        print("weasy fallback md:", e)
    # fallback: plain text via reportlab
    return _fallback_pdf(md_text, output)

def html_to_pdf(html_text: str, output: Path, paper="A4", orientation="portrait", margin="15mm"):
    try:
        if _weasy_available():
            from weasyprint import HTML
            css = f"@page{{size:{paper} {orientation}; margin:{margin}}}"
            full = f"<style>{css}</style>" + html_text if "<html" not in html_text.lower() else html_text
            HTML(string=full).write_pdf(str(output))
            return output
    except Exception as e:
        print("weasy fallback html:", e)
    # strip tags for fallback
    try:
        from bs4 import BeautifulSoup
        txt=BeautifulSoup(html_text,"html.parser").get_text("\n")
    except: txt=html_text
    return _fallback_pdf(txt, output)
