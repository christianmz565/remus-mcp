"""Bidirectional XML import/export DTD-aware, ISO-8859-1."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from lxml import etree

from ..config import get_dtd_path
from ..jet.mdbtools import execute_sql, export_table, sql_escape
from ..jet.schema import TYPE_TO_TABLE

NS = "http://rem.lsi.us.es"
NSMAP = {"rem": NS}

# Map type to XML tag local name (without prefix)
TYPE_TO_XMLTAG = {
    "section": "section",
    "appendix": "appendix",
    "paragraph": "paragraph",
    "graphic_file": "graphicFile",
    "glossary_item": "glossaryItem",
    "organization": "organization",
    "stakeholder": "stakeholder",
    "meeting": "meeting",
    "objective": "objective",
    "actor": "actor",
    "information_requirement": "informationRequirement",
    "constraint_requirement": "constraintRequirement",
    "use_case": "useCase",
    "functional_requirement": "functionalRequirement",
    "non_functional_requirement": "nonFunctionalRequirement",
    "object_type": "objectType",
    "user_defined_value_type": "userDefinedValueType",
    "association_type": "associationType",
    "system_operation": "systemOperation",
    "conflict": "conflict",
    "defect": "defect",
    "change_request": "changeRequest",
    "traceability_matrix": "traceabilityMatrix",
    "attribute": "attribute",
    "component": "component",
    "role": "role",
    "parameter": "parameter",
    "trace": "trace",
}

XMLTAG_TO_TYPE = {v: k for k, v in TYPE_TO_XMLTAG.items()}

TYPE_PREFIX = {
    "c_requirementsSpecification": "crs",
    "d_requirementsSpecification": "drs",
    "defectsSpecification": "dfs",
    "changeRequestsSpecification": "crs_spec",
    "section": "sec",
    "appendix": "app",
    "paragraph": "par",
    "graphic_file": "gfx",
    "glossary_item": "glo",
    "organization": "org",
    "stakeholder": "stk",
    "meeting": "mtg",
    "objective": "obj",
    "actor": "act",
    "information_requirement": "irq",
    "constraint_requirement": "crq",
    "use_case": "uc",
    "functional_requirement": "frq",
    "non_functional_requirement": "nfr",
    "object_type": "obt",
    "user_defined_value_type": "udt",
    "association_type": "ast",
    "system_operation": "sys",
    "alternative": "alt",
    "conflict": "cnf",
    "defect": "def",
    "change_request": "cr",
    "traceability_matrix": "mtx",
    "trace": "trc",
    "attribute": "att",
    "component": "cmp",
    "role": "rol",
    "parameter": "prm",
    "step": "stp",
}


def _make_xml_id(type_name: str, oid_int: int) -> str:
    prefix = TYPE_PREFIX.get(type_name, "id")
    return f"{prefix}_{oid_int}"
def _dtd_path() -> str:
    return str(get_dtd_path())


def _create_text_element(parent, tag: str, text: str | None):
    if text is None:
        return
    el = etree.SubElement(parent, f"{{{NS}}}{tag}")
    # Handle REM_TEXT with possible refs? Simplified as plain text
    el.text = str(text)


def _parse_oid(oid_s: Any) -> int:
    if oid_s is None:
        raise ValueError("INVALID_OID: None")
    s = str(oid_s).strip()
    if not s:
        raise ValueError("INVALID_OID: Empty string")
    if "_" in s:
        s = s.rsplit("_", 1)[-1]
    try:
        return int(s)
    except ValueError as e:
        raise ValueError(f"INVALID_OID: {oid_s}") from e


import datetime

SPEC_TAG_DEFAULT_OIDS = {
    "c_requirementsSpecification": 1,
    "d_requirementsSpecification": 2,
    "defectsSpecification": 3,
    "changeRequestsSpecification": 4,
}


def _append_date_element(parent_ver, version_date_val: str | None):
    now = datetime.datetime.now()
    y_val, m_val, d_val = now.year, now.month, now.day
    if version_date_val:
        v_str = str(version_date_val).split()[0]
        try:
            dt = datetime.datetime.strptime(v_str, "%Y-%m-%d")
            y_val, m_val, d_val = dt.year, dt.month, dt.day
        except ValueError:
            try:
                dt = datetime.datetime.strptime(v_str, "%d/%m/%Y")
                y_val, m_val, d_val = dt.year, dt.month, dt.day
            except ValueError:
                pass
    date_el = etree.SubElement(parent_ver, f"{{{NS}}}date")
    y = etree.SubElement(date_el, f"{{{NS}}}year")
    y.text = str(y_val)
    m = etree.SubElement(date_el, f"{{{NS}}}month")
    m.text = str(m_val)
    d = etree.SubElement(date_el, f"{{{NS}}}day")
    d.text = str(d_val)

def export_xml(
    session_manager,
    project_id: str,
    document: str | None = None,
    filter_type: str | None = None,
    filter_ids: list[int] | None = None,
) -> dict[str, Any]:
    session = session_manager.get(project_id)
    db_path = str(session.db_path)
    # Build tree
    root = etree.Element(f"{{{NS}}}requirementsProject", nsmap=NSMAP)
    # Add name
    name_el = etree.SubElement(root, f"{{{NS}}}name")
    name_el.text = session.db_path.stem

    # Spec docs: need to read C_RequirementsSpecification etc. Create minimal structure
    for spec_tag, table in [
        ("c_requirementsSpecification", "C_RequirementsSpecification"),
        ("d_requirementsSpecification", "D_RequirementsSpecification"),
        ("defectsSpecification", "DefectsSpecification"),
        ("changeRequestsSpecification", "ChangeRequestsSpecification"),
    ]:
        spec_el = etree.SubElement(root, f"{{{NS}}}{spec_tag}")
        try:
            rows = export_table(db_path, table)
        except Exception:
            rows = []
        if rows:
            first = rows[0]
            oid_val = first.get("oid", 1)
            spec_el.set("oid", _make_xml_id(spec_tag, int(oid_val)))
            _create_text_element(spec_el, "name", str(first.get("name", spec_tag)))
            # version
            ver_el = etree.SubElement(spec_el, f"{{{NS}}}version")
            major = etree.SubElement(ver_el, f"{{{NS}}}major")
            major.text = str(first.get("versionMajor", 1) or 1)
            minor = etree.SubElement(ver_el, f"{{{NS}}}minor")
            minor.text = str(first.get("versionMinor", 0) or 0)
            _append_date_element(ver_el, first.get("versionDate"))
            _create_text_element(
                spec_el, "comments", str(first.get("comments", "Ninguno") or "Ninguno")
            )
        else:
            # Generate valid ID
            spec_doc_oid = SPEC_TAG_DEFAULT_OIDS.get(spec_tag, 1)
            spec_el.set("oid", _make_xml_id(spec_tag, spec_doc_oid))
            _create_text_element(spec_el, "name", spec_tag)
            ver_el = etree.SubElement(spec_el, f"{{{NS}}}version")
            major = etree.SubElement(ver_el, f"{{{NS}}}major")
            major.text = "1"
            minor = etree.SubElement(ver_el, f"{{{NS}}}minor")
            minor.text = "0"
            _append_date_element(ver_el, None)
            _create_text_element(spec_el, "comments", "Ninguno")
        # Export preparedFor / preparedBy for this spec doc
        doc_oid_int = int(oid_val) if rows else spec_doc_oid
        pf_rows = export_table(db_path, "IsPreparedFor")
        pf_org_ids = []
        for r in pf_rows:
            if int(r.get("document", -1) or -1) == doc_oid_int:
                org_id = int(r.get("organization", -1) or -1)
                if org_id > 0:
                    pf_org_ids.append(_make_xml_id("organization", org_id))
        if pf_org_ids:
            pf_el = etree.SubElement(spec_el, f"{{{NS}}}preparedFor")
            pf_el.set("organizations", " ".join(pf_org_ids))
        pb_rows = export_table(db_path, "IsPreparedBy")
        pb_org_ids = []
        for r in pb_rows:
            if int(r.get("document", -1) or -1) == doc_oid_int:
                org_id = int(r.get("organization", -1) or -1)
                if org_id > 0:
                    pb_org_ids.append(_make_xml_id("organization", org_id))
        if pb_org_ids:
            pb_el = etree.SubElement(spec_el, f"{{{NS}}}preparedBy")
            pb_el.set("organizations", " ".join(pb_org_ids))
        # Add entities for this spec if document filter not mismatched - for simplicity add all
        # Determine which types belong? We'll dump all types into first spec? Actually distribute: first spec gets all non-defect/change objects,
        # but for export simplicity we dump all objects into c_requirementsSpecification unless filter.
        if spec_tag == "c_requirementsSpecification":
            types_to_export = list(TYPE_TO_XMLTAG.keys())
            oid_to_xml_id = {}
            if filter_type:
                types_to_export = [filter_type] if filter_type in types_to_export else []
            for typ in types_to_export:
                if typ in [
                    "trace",
                    "attribute",
                    "component",
                    "role",
                    "parameter",
                    "traceability_matrix",
                ]:
                    continue
                table2 = TYPE_TO_TABLE.get(typ)
                if not table2:
                    continue
                try:
                    rows2 = export_table(db_path, table2)
                except Exception:
                    continue
                for r in rows2:
                    if filter_ids and int(r.get("oid", -1)) not in filter_ids:
                        continue
                    # Create element
                    xml_tag = TYPE_TO_XMLTAG[typ]
                    el = etree.SubElement(spec_el, f"{{{NS}}}{xml_tag}")
                    oid_raw = r.get("oid")
                    try:
                        oid_int = int(oid_raw) if oid_raw is not None else 0
                    except:
                        oid_int = 0
                    xml_id = _make_xml_id(typ, oid_int)
                    el.set("oid", xml_id)
                    oid_to_xml_id[oid_int] = xml_id
                    _create_text_element(el, "name", str(r.get("name", "")))
                    # version
                    ver2 = etree.SubElement(el, f"{{{NS}}}version")
                    ma = etree.SubElement(ver2, f"{{{NS}}}major")
                    ma.text = str(r.get("versionMajor", 1) or 1)
                    mi = etree.SubElement(ver2, f"{{{NS}}}minor")
                    mi.text = str(r.get("versionMinor", 0) or 0)
                    _append_date_element(ver2, r.get("versionDate"))
                    # Add comments if present or default for SpecificationObject
                    if r.get("comments") is not None:
                        _create_text_element(el, "comments", str(r.get("comments")))
                    # Section needs level/number
                    if typ in ["section", "appendix"]:
                        lvl = etree.SubElement(el, f"{{{NS}}}level")
                        lvl.text = str(r.get("level", "1") or "1")
                        num = etree.SubElement(el, f"{{{NS}}}number")
                        num.text = str(r.get("number", "1") or "1")
                    # description if exists
                    if r.get("description"):
                        _create_text_element(el, "description", str(r.get("description")))
                    # For C-requirements need importance etc.
                    if typ in ["constraint_requirement", "objective"] or typ.endswith(
                        "_requirement"
                    ):
                        # importance, urgency etc. if present
                        for val_tag, col in [
                            ("importance", "importance"),
                            ("urgency", "urgency"),
                            ("status", "status"),
                            ("stability", "stability"),
                        ]:
                            if r.get(col) is not None:
                                imp_el = etree.SubElement(el, f"{{{NS}}}{val_tag}")
                                imp_el.set("value", f"VAL-{r.get(col)}")
                            else:
                                # Add empty with tbd to satisfy DTD if missing? Add placeholder
                                imp_el = etree.SubElement(el, f"{{{NS}}}{val_tag}")
                                tbd = etree.SubElement(imp_el, f"{{{NS}}}tbd")

    # Traces
    try:
        traces = export_table(db_path, "Trace")
        for t in traces:
            src_raw = t.get("source")
            tgt_raw = t.get("target")
            try:
                src_int = int(src_raw) if src_raw is not None else 0
                tgt_int = int(tgt_raw) if tgt_raw is not None else 0
            except Exception:
                continue
            if not src_int or not tgt_int:
                continue
            tr_el = etree.SubElement(root, f"{{{NS}}}trace")
            src_id = oid_to_xml_id.get(src_int, f"ref_{src_int}")
            tgt_id = oid_to_xml_id.get(tgt_int, f"ref_{tgt_int}")
            tr_el.set("source", src_id)
            tr_el.set("target", tgt_id)
            if t.get("isChecked") or t.get("checked"):
                etree.SubElement(tr_el, f"{{{NS}}}isChecked")
    except Exception:
        pass

    # predefinedValueTypes / predefinedValues minimal empty
    pvt_el = etree.SubElement(root, f"{{{NS}}}predefinedValueTypes")
    pv_el = etree.SubElement(root, f"{{{NS}}}predefinedValues")

    # Serialize
    xml_bytes = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
    xml_str = xml_bytes.decode("utf-8")

    # Validate against DTD if available
    dtd_errors = []
    try:
        dtd_p = _dtd_path()
        if Path(dtd_p).exists():
            dtd = etree.DTD(dtd_p)
            # Need to parse our xml for validation
            doc = etree.fromstring(xml_bytes)
            if not dtd.validate(doc):
                dtd_errors = [str(e) for e in dtd.error_log.filter_from_errors()]
                # Don't fail, just include warnings; for now return but warn
    except Exception as e:
        dtd_errors.append(str(e))

    # Write temp file
    tmp = tempfile.mktemp(suffix=".xml", prefix=f"remus_export_{project_id}_")
    Path(tmp).write_bytes(xml_bytes)

    return {"xml": xml_str, "path": tmp, "dtd_errors": dtd_errors, "project_id": project_id}


def import_xml(
    session_manager,
    project_id: str,
    xml: str | None = None,
    file_path: str | None = None,
    strategy: str = "merge",
    dry_run: bool = False,
    confirm_replace: bool = False,
    on_missing_ref: str = "error",
) -> dict[str, Any]:
    if (xml is None and file_path is None) or (xml is not None and file_path is not None):
        raise ValueError("Exactly one of xml or file_path required")
    content = xml
    if file_path:
        content = Path(file_path).read_text(encoding="utf-8")
    assert content is not None
    try:
        doc = etree.fromstring(content.encode("utf-8") if isinstance(content, str) else content)
    except Exception as e:
        raise ValueError(f"XML parse error: {e}") from e
    # DTD validation (non-fatal: collect warnings)
    dtd_warnings = []
    try:
        dtd_p = _dtd_path()
        if Path(dtd_p).exists():
            dtd = etree.DTD(dtd_p)
            if not dtd.validate(doc):
                dtd_warnings = [
                    f"line {err.line}: {err.message}" for err in dtd.error_log.filter_from_errors()
                ]
    except Exception as e:
        dtd_warnings.append(str(e))

    session = session_manager.get(project_id)
    db_path = str(session.db_path)

    # Count objects to import: walk children
    imported = 0
    updated = 0
    errors = []

    # Strategy replace: delete existing if confirm_replace
    if strategy == "replace" and not confirm_replace:
        raise ValueError("confirm_replace required for replace strategy")
    if strategy == "replace" and confirm_replace and not dry_run:
        with session_manager.mutate(project_id, "import_xml_replace"):
            for typ, xml_tag in TYPE_TO_XMLTAG.items():
                if typ == "trace":
                    continue
                table = TYPE_TO_TABLE.get(typ)
                if not table:
                    continue
                try:
                    # Find all elements of this tag in doc
                    elems = doc.findall(f".//{{{NS}}}{xml_tag}")
                    if elems:
                        # Delete all existing rows? For safety, only if elements present
                        try:
                            execute_sql(db_path, f"DELETE FROM [{table}]")
                        except Exception:
                            pass
                except Exception:
                    pass

    # Merge: upsert by oid
    # We will iterate over each xml_tag and create/update
    if not dry_run:
        # Need lock + backup
        ctx = session_manager.mutate(project_id, "import_xml", None, None)
        ctx.__enter__()
        try:
            for xml_tag, typ in XMLTAG_TO_TYPE.items():
                if typ == "trace":
                    # Traces handled separately
                    continue
                table = TYPE_TO_TABLE.get(typ)
                if not table:
                    continue
                elems = doc.findall(f".//{{{NS}}}{xml_tag}")
                for el in elems:
                    oid_s = el.get("oid")
                    if not oid_s:
                        errors.append({"tag": xml_tag, "error": "missing oid"})
                        continue
                    try:
                        oid = _parse_oid(oid_s)
                    except ValueError:
                        errors.append({"tag": xml_tag, "oid": oid_s, "error": "invalid oid"})
                        continue
                    name_el = el.find(f"{{{NS}}}name")
                    name = name_el.text if name_el is not None and name_el.text else ""
                    # description
                    desc_el = el.find(f"{{{NS}}}description")
                    desc = desc_el.text if desc_el is not None else None
                    # Build row
                    row = {"oid": oid, "name": name}
                    if desc is not None:
                        row["description"] = desc
                    try:
                        existing_rows = export_table(db_path, table)
                        exists = any(int(r.get("oid", -1)) == oid for r in existing_rows)
                    except Exception:
                        exists = False
                    if exists:
                        # UPDATE
                        patch = {k: v for k, v in row.items() if k != "oid"}
                        if not patch:
                            updated += 1
                            continue
                        cols_set = ", ".join(f"[{k}]={sql_escape(v)}" for k, v in patch.items())
                        sql = f"UPDATE [{table}] SET {cols_set} WHERE [oid]={oid}"
                        try:
                            execute_sql(db_path, sql)
                            updated += 1
                        except Exception as e:
                            errors.append({"oid": oid, "table": table, "error": str(e)})
                    else:
                        # INSERT
                        # Ensure document etc. We need to add document fallback 1 if required?
                        # Try to infer document from parent spec doc
                        # Find parent spec
                        parent = el.getparent()
                        # Walk up to find spec id? Simplified: use first doc oid
                        if "document" not in row:
                            # try to set document to first spec's oid
                            try:
                                drows = export_table(db_path, "D_RequirementsSpecification")
                                if drows:
                                    row["document"] = int(drows[0].get("oid"))
                            except:
                                pass
                        # Add version defaults if not present
                        if "versionMajor" not in row:
                            row["versionMajor"] = 1
                        if "versionMinor" not in row:
                            row["versionMinor"] = 0
                        cols = ", ".join(f"[{k}]" for k in row)
                        vals = ", ".join(sql_escape(v) for v in row.values())
                        sql = f"INSERT INTO [{table}] ({cols}) VALUES ({vals})"
                        try:
                            execute_sql(db_path, sql)
                            imported += 1
                        except Exception as e:
                            errors.append({"oid": oid, "table": table, "error": str(e)})
            # Traces: also import
            trace_elems = doc.findall(f".//{{{NS}}}trace")
            for te in trace_elems:
                oid_s = te.get("oid")
                src_el = te.find(f"{{{NS}}}source")
                tgt_el = te.find(f"{{{NS}}}target")
                # But export uses source/target elements with oid attr; parse accordingly
                src = src_el.get("oid") if src_el is not None else te.get("source")
                tgt = tgt_el.get("oid") if tgt_el is not None else te.get("target")
                if not oid_s or not src or not tgt:
                    continue
                try:
                    oid_i = _parse_oid(oid_s)
                    src_i = _parse_oid(src)
                    tgt_i = _parse_oid(tgt)
                except:
                    continue
                try:
                    traces = export_table(db_path, "Trace")
                    exists = any(int(t.get("oid", -1)) == oid_i for t in traces)
                except:
                    exists = False
                if not exists:
                    try:
                        execute_sql(
                            db_path,
                            f"INSERT INTO [Trace] ([oid],[source],[target]) VALUES ({oid_i},{src_i},{tgt_i})",
                        )
                        imported += 1
                    except Exception as e:
                        errors.append({"trace_oid": oid_i, "error": str(e)})
            # PreparedFor / PreparedBy
            for tag_name, jtable in [("preparedFor", "IsPreparedFor"), ("preparedBy", "IsPreparedBy")]:
                elems = doc.findall(f".//{{{NS}}}{tag_name}")
                for el in elems:
                    parent_doc = el.getparent()
                    doc_oid_s = parent_doc.get("oid") if parent_doc is not None else "1"
                    try:
                        doc_oid = _parse_oid(doc_oid_s)
                    except Exception:
                        doc_oid = 1
                    orgs_attr = el.get("organizations", "")
                    org_ids = orgs_attr.split()
                    for org_s in org_ids:
                        try:
                            org_oid = _parse_oid(org_s)
                        except Exception:
                            continue
                        try:
                            existing_j = export_table(db_path, jtable)
                            already = any(
                                int(r.get("document", -1) or -1) == doc_oid and int(r.get("organization", -1) or -1) == org_oid
                                for r in existing_j
                            )
                        except Exception:
                            already = False
                        if not already:
                            new_j_oid = max_oid(db_path, jtable) + 1
                            sql_j = f"INSERT INTO [{jtable}] ([oid], [document], [organization]) VALUES ({new_j_oid}, {doc_oid}, {org_oid})"
                            try:
                                execute_sql(db_path, sql_j)
                                imported += 1
                            except Exception as e:
                                errors.append({"table": jtable, "error": str(e)})
        except Exception as e:
            # Rollback
            raise
        else:
            ctx.__exit__(None, None, None)
    else:
        # dry_run count only
        for xml_tag, typ in XMLTAG_TO_TYPE.items():
            elems = doc.findall(f".//{{{NS}}}{xml_tag}")
            imported += len(elems)

    return {
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "project_id": project_id,
        "dry_run": dry_run,
    }
