"""HTML generation via Wine msxml3."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import (
    ENV_WINEPREFIX,
    MCP_RESPONSE_MAX_HTML,
    SUBPROCESS_TIMEOUT_SECONDS,
    get_xsl_path,
)

_lxml_ns_initialized = False


def _init_lxml_namespaces():
    global _lxml_ns_initialized
    if _lxml_ns_initialized:
        return
    try:
        from lxml import etree
    except ImportError:
        return

    msxsl_ns = etree.FunctionNamespace("urn:schemas-microsoft-com:xslt")

    def _node_set(context, x):
        if isinstance(x, list):
            return x
        if not x:
            return []
        if isinstance(x, str):
            if not x.strip():
                return []
            try:
                return etree.fromstring(f"<root>{x}</root>").getchildren()
            except Exception:
                el = etree.Element("text")
                el.text = x
                return [el]
        return []

    msxsl_ns["node-set"] = _node_set

    rem_ns = etree.FunctionNamespace("http://rem.lsi.us.es")

    def _bool2space(context, b):
        if isinstance(b, list):
            val = "".join(str(x) for x in b).strip()
        else:
            val = b
        if val in (True, 1, "true", "1", "True") or (isinstance(b, list) and len(b) > 0):
            return " "
        return ""

    madeja_regex = re.compile(r"^\[((FOR|DEB|ANA|PNA|ANI|PNI|HU)-\d+)\]\s*((.)*)")

    def _is_madeja(context, s):
        val = "".join(str(x) for x in s) if isinstance(s, list) else str(s or "")
        m = madeja_regex.search(val)
        return m.group(1) if m else False

    def _get_madeja_prefix(context, s):
        val = "".join(str(x) for x in s) if isinstance(s, list) else str(s or "")
        m = madeja_regex.search(val)
        return m.group(2) if m else "?"

    def _get_madeja_name(context, s):
        val = "".join(str(x) for x in s) if isinstance(s, list) else str(s or "")
        m = madeja_regex.search(val)
        return m.group(3) if m else "?"

    def _make_html(context, md_text, inline=False):
        val = "".join(str(x) for x in md_text) if isinstance(md_text, list) else str(md_text or "")
        if inline:
            return val.replace("\n", "<br/>")
        paragraphs = val.split("\n\n")
        return "".join(f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs if p.strip())

    rem_ns["bool2space"] = _bool2space
    rem_ns["toLowerCase"] = lambda context, s: (
        "".join(str(x) for x in s).lower() if isinstance(s, list) else str(s or "").lower()
    )
    rem_ns["toUpperCase"] = lambda context, s: (
        "".join(str(x) for x in s).upper() if isinstance(s, list) else str(s or "").upper()
    )
    rem_ns["isMadejaObject"] = _is_madeja
    rem_ns["getMadejaPrefix"] = _get_madeja_prefix
    rem_ns["getMadejaName"] = _get_madeja_name
    rem_ns["makeHtml"] = _make_html

    _lxml_ns_initialized = True


_init_lxml_namespaces()


def render_html(
    session_manager,
    project_id: str,
    document: str,
    lang: str = "en",
    output: str = "html",
    offline: bool = False,
    use_wine: bool = False,
) -> dict:
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

    xsl_abs = get_xsl_path(lang)

    # Export XML to temp
    export_res = export_xml(session_manager, project_id, document=document)
    xml_path = export_res["path"]
    if not Path(xml_path).exists():
        tmp = tempfile.mktemp(suffix=".xml")
        Path(tmp).write_text(export_res["xml"], encoding="utf-8")
        xml_path = tmp

    out_html = tempfile.mktemp(suffix=".html", prefix=f"remus_out_{project_id}_")
    warnings = []
    html_content = None

    wine_requested = use_wine or os.getenv("REMUS_USE_WINE", "").lower() in ("1", "true", "yes")

    if wine_requested:
        vbs_path = Path(__file__).parent.parent / "assets" / "transform.vbs"
        if not vbs_path.exists():
            raise RuntimeError(f"WINE_TRANSFORM_FAILED: VBS script not found at {vbs_path}")
        if not shutil.which("wine"):
            raise RuntimeError("WINE_NOT_CONFIGURED: Wine executable not found in PATH")

        wine_prefix = os.getenv(ENV_WINEPREFIX)
        if wine_prefix:
            msxml_path = Path(wine_prefix) / "drive_c" / "windows" / "system32" / "msxml3.dll"
        else:
            msxml_path = Path.home() / ".wine" / "drive_c" / "windows" / "system32" / "msxml3.dll"

        if not msxml_path.exists():
            raise RuntimeError(f"WINE_NOT_CONFIGURED: msxml3.dll not found at {msxml_path}")

        cmd = ["wine", "cscript", "//NoLogo", str(vbs_path), str(xml_path), str(xsl_abs)]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS
            )
            if r.returncode == 0 and r.stdout.strip():
                html_content = r.stdout
                Path(out_html).write_text(html_content, encoding="utf-8")
            else:
                raise RuntimeError(f"WINE_TRANSFORM_FAILED: {r.stderr.strip() or r.stdout.strip()}")
        except Exception as e:
            raise RuntimeError(f"WINE_TRANSFORM_FAILED: {e}") from e
    else:
        # Standard deterministic lxml renderer
        try:
            _init_lxml_namespaces()
            from lxml import etree

            xml_parser = etree.XMLParser(
                resolve_entities=False, load_dtd=True, attribute_defaults=True
            )
            try:
                xml_doc = etree.parse(str(xml_path), xml_parser)
            except Exception:
                xml_doc = etree.parse(str(xml_path))
            parser = etree.XMLParser(resolve_entities=False)
            xsl_doc = etree.parse(str(xsl_abs), parser)

            transform = etree.XSLT(xsl_doc)
            result = transform(xml_doc)
            html_content = str(result)
            Path(out_html).write_text(html_content, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"LXML_RENDER_FAILED: {e}") from e

    # Handle pdf
    if output == "pdf":
        pdf_path = out_html.replace(".html", ".pdf")
        if shutil.which("wkhtmltopdf"):
            try:
                subprocess.run(
                    ["wkhtmltopdf", out_html, pdf_path],
                    capture_output=True,
                    timeout=SUBPROCESS_TIMEOUT_SECONDS,
                    check=True,
                )
                return {
                    "html": html_content[:MCP_RESPONSE_MAX_HTML] if html_content else "",
                    "path": pdf_path,
                    "warnings": warnings,
                    "project_id": project_id,
                }
            except Exception as e:
                raise RuntimeError(f"PDF_GENERATION_FAILED: wkhtmltopdf failed: {e}") from e
        elif shutil.which("chromium"):
            try:
                subprocess.run(
                    [
                        "chromium",
                        "--headless",
                        "--disable-gpu",
                        f"--print-to-pdf={pdf_path}",
                        out_html,
                    ],
                    capture_output=True,
                    timeout=SUBPROCESS_TIMEOUT_SECONDS,
                    check=True,
                )
                return {
                    "html": html_content[:MCP_RESPONSE_MAX_HTML] if html_content else "",
                    "path": pdf_path,
                    "warnings": warnings,
                    "project_id": project_id,
                }
            except Exception as e:
                raise RuntimeError(f"PDF_GENERATION_FAILED: chromium failed: {e}") from e
        else:
            raise RuntimeError(
                "PDF_CONVERTER_NOT_FOUND: Neither wkhtmltopdf nor chromium is available"
            )

    html_trunc = html_content[:MCP_RESPONSE_MAX_HTML] if html_content else ""
    return {"html": html_trunc, "path": out_html, "warnings": warnings, "project_id": project_id}
