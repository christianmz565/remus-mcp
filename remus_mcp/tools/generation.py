"""HTML generation via Wine msxml3."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

def render_html(session_manager, project_id: str, document: str, lang: str = "en", output: str = "html", offline: bool = False) -> dict:
    from .xml_ops import export_xml
    # Validate document
    doc_map = {
        "c_requirementsSpecification": "C_RequirementsSpecification",
        "d_requirementsSpecification": "D_RequirementsSpecification",
        "defectsSpecification": "DefectsSpecification",
        "changeRequestsSpecification": "ChangeRequestsSpecification",
    }
    if document not in doc_map:
        raise ValueError(f"DOCUMENT_NOT_FOUND: {document}")
    lang_map = {"en": "xslt/remus/REMUS_English.xsl", "es": "xslt/remus/REMUS_Spanish.xsl", "de": "xslt/remus/REMUS_German.xsl"}
    if lang not in lang_map:
        raise ValueError(f"Invalid lang {lang}")
    xsl_path = Path(lang_map[lang])
    # Resolve relative to repo root — supports monorepo (/app/xslt), standalone (mcp/xslt), and Docker
    candidates = [
        Path("/home/cricro/tiny-projects/remus") / xsl_path,
        Path.cwd() / xsl_path,
        Path.cwd() / "mcp" / xsl_path,
        Path(__file__).parents[3] / xsl_path,  # monorepo: /app/xslt
        Path(__file__).parents[2] / xsl_path,  # standalone: mcp/xslt
        Path(__file__).parents[2] / ".." / xsl_path,
        Path("/app") / xsl_path,
    ]
    xsl_abs = None
    for c in candidates:
        if c.exists():
            xsl_abs = c
            break
    if xsl_abs is None:
        raise FileNotFoundError(f"XSL not found: {xsl_path}")
    # Export XML to temp
    export_res = export_xml(session_manager, project_id, document=document)
    xml_path = export_res["path"]
    # Also ensure we have xml file
    if not Path(xml_path).exists():
        tmp = tempfile.mktemp(suffix=".xml")
        Path(tmp).write_text(export_res["xml"], encoding="iso-8859-1")
        xml_path = tmp

    out_html = tempfile.mktemp(suffix=".html", prefix=f"remus_out_{project_id}_")
    warnings = []

    # Try Wine msxml3 via cscript transform.vbs
    vbs_path = Path(__file__).parent.parent / "assets" / "transform.vbs"
    wine_prefix = os.getenv("WINEPREFIX", str(Path.cwd() / ".wine"))
    # Alternative: try msxsl if available
    html_content = None
    wine_available = shutil.which("wine") is not None
    msxml_dll = Path(wine_prefix) / "drive_c/windows/system32/msxml3.dll"
    if not msxml_dll.exists():
        warnings.append("WINE_NOT_CONFIGURED: msxml3.dll not found, using lxml fallback")

    if wine_available and msxml_dll.exists() and vbs_path.exists():
        try:
            cmd = ["wine", "cscript", "//NoLogo", str(vbs_path), str(xml_path), str(xsl_abs)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                html_content = r.stdout
                Path(out_html).write_text(html_content, encoding="utf-8")
            else:
                warnings.append(f"Wine transform failed: {r.stderr[:500] or r.stdout[:500]}; using lxml fallback")
        except Exception as e:
            warnings.append(f"Wine exception {e}; using lxml fallback")

    if html_content is None:
        # lxml fallback with patched XSL (strip msxsl:script)
        try:
            from lxml import etree
            xml_doc = etree.parse(str(xml_path))
            parser = etree.XMLParser(resolve_entities=False)
            xsl_doc = etree.parse(str(xsl_abs), parser)
            for el in xsl_doc.xpath("//*[local-name()='script']"):
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
            transform = etree.XSLT(xsl_doc)
            result = transform(xml_doc)
            html_content = str(result)
            Path(out_html).write_text(html_content, encoding="utf-8")
        except Exception as e:
            warnings.append(f"lxml fallback failed: {e}; returning minimal HTML")
            html_content = f"<!doctype html><html><head><meta charset='utf-8'><title>{project_id}</title></head><body><h1>REMUS Project {project_id}</h1><pre>{Path(xml_path).read_text(encoding='iso-8859-1', errors='ignore')[:5000]}</pre></body></html>"
            Path(out_html).write_text(html_content, encoding="utf-8")
    # Handle pdf
    if output == "pdf":
        pdf_path = out_html.replace(".html", ".pdf")
        # Try wkhtmltopdf or chromium
        if shutil.which("wkhtmltopdf"):
            try:
                subprocess.run(["wkhtmltopdf", out_html, pdf_path], capture_output=True, timeout=30)
                return {"html": html_content[:100000] if html_content else "", "path": pdf_path, "warnings": warnings, "project_id": project_id}
            except Exception as e:
                warnings.append(f"wkhtmltopdf failed: {e}")
        if shutil.which("chromium"):
            try:
                subprocess.run(["chromium", "--headless", "--disable-gpu", "--print-to-pdf=" + pdf_path, out_html], capture_output=True, timeout=30)
                return {"html": html_content[:100000] if html_content else "", "path": pdf_path, "warnings": warnings, "project_id": project_id}
            except Exception as e:
                warnings.append(f"chromium pdf failed: {e}")
        warnings.append("PDF generation requested but no converter available; returned HTML")

    # Truncate html for MCP response
    html_trunc = html_content[:100000] if html_content else ""
    return {"html": html_trunc, "path": out_html, "warnings": warnings, "project_id": project_id}
