"""Trace & matrix & validation tools."""
from __future__ import annotations

from typing import Any

from ..jet.mdbtools import export_table, execute_sql, max_oid, sql_escape
from ..jet.schema import TYPE_TO_TABLE

def _ensure_exists(session_manager, project_id: str, oid: int) -> bool:
    # Search all entity tables for oid existence
    session = session_manager.get(project_id)
    for table in TYPE_TO_TABLE.values():
        try:
            rows = export_table(str(session.db_path), table)
            for r in rows:
                if int(r.get("oid", -1) or -1) == int(oid):
                    return True
        except Exception:
            continue
    return False

def trace_add(session_manager, project_id: str, source_oid: int, target_oid: int, checked: bool = False) -> dict[str, Any]:
    if int(source_oid) == int(target_oid):
        sess = session_manager.get(project_id)
        tables_for_oid = []
        for tbl in TYPE_TO_TABLE.values():
            try:
                rows = export_table(str(sess.db_path), tbl)
                for r in rows:
                    if int(r.get("oid", -1) or -1) == int(source_oid):
                        tables_for_oid.append(tbl)
                        break
            except Exception:
                pass
            if len(tables_for_oid) > 1:
                break
        if len(tables_for_oid) == 1:
            raise ValueError("Self-trace not allowed")
    # Validate both exist
    if not _ensure_exists(session_manager, project_id, source_oid):
        raise KeyError(f"NOT_FOUND source oid {source_oid}")
    if not _ensure_exists(session_manager, project_id, target_oid):
        raise KeyError(f"NOT_FOUND target oid {target_oid}")
    # Duplicate check
    sess2 = session_manager.get(project_id)
    traces = export_table(str(sess2.db_path), "Trace")
    for t in traces:
        if int(t.get("source", -1) or -1) == int(source_oid) and int(t.get("target", -1) or -1) == int(target_oid):
            raise ValueError("DUPLICATE_TRACE")
    with session_manager.mutate(project_id, "trace_add", "trace", None):
        sess3 = session_manager.get(project_id)
        new_oid = max_oid(str(sess3.db_path), "Trace") + 1
        row = {"oid": new_oid, "source": int(source_oid), "target": int(target_oid)}
        if traces and len(traces) > 0:
            sample = traces[0]
            if "isChecked" in sample:
                row["isChecked"] = 1 if checked else 0
            elif "checked" in sample:
                row["checked"] = 1 if checked else 0
        else:
            row["isChecked"] = 1 if checked else 0
        cols = ", ".join(f"[{k}]" for k in row.keys())
        vals = ", ".join(sql_escape(v) for v in row.values())
        sql = f"INSERT INTO [Trace] ({cols}) VALUES ({vals})"
        execute_sql(str(sess3.db_path), sql)
        session_manager.append_change(project_id, "trace_add", new_oid, "trace")
        return {"trace_oid": new_oid, "project_id": project_id}
def trace_remove(session_manager, project_id: str, source_oid: int, target_oid: int) -> dict[str, Any]:
    session = session_manager.get(project_id)
    traces = export_table(str(session.db_path), "Trace")
    found = None
    for t in traces:
        if int(t.get("source", -1) or -1) == int(source_oid) and int(t.get("target", -1) or -1) == int(target_oid):
            found = t
            break
    if found is None:
        raise KeyError("NOT_FOUND trace")
    with session_manager.mutate(project_id, "trace_remove", "trace", None):
        oid = int(found.get("oid"))
        execute_sql(str(session.db_path), f"DELETE FROM [Trace] WHERE [oid]={oid}")
        session_manager.append_change(project_id, "trace_remove", oid, "trace")
        return {"deleted": True, "project_id": project_id, "oid": oid}

def get_traces(session_manager, project_id: str, oid: int, direction: str = "both") -> dict[str, Any]:
    session = session_manager.get(project_id)
    traces = export_table(str(session.db_path), "Trace")
    out = []
    for t in traces:
        src = int(t.get("source", -1) or -1)
        tgt = int(t.get("target", -1) or -1)
        if direction == "outgoing" and src == int(oid):
            out.append(t)
        elif direction == "incoming" and tgt == int(oid):
            out.append(t)
        elif direction == "both" and (src == int(oid) or tgt == int(oid)):
            out.append(t)
    return {"traces": out, "project_id": project_id, "oid": oid, "direction": direction}

def trace_matrix(session_manager, project_id: str, source_type: str, target_type: str, document: int | None = None) -> dict[str, Any]:
    from .crud import _table_for
    from ..jet.mdbtools import export_table
    session = session_manager.get(project_id)
    src_table = _table_for(source_type)
    tgt_table = _table_for(target_type)
    src_rows = export_table(str(session.db_path), src_table)
    tgt_rows = export_table(str(session.db_path), tgt_table)
    if document is not None:
        src_rows = [r for r in src_rows if int(r.get("document", -1) or -1) == int(document)]
        tgt_rows = [r for r in tgt_rows if int(r.get("document", -1) or -1) == int(document)]
    if len(src_rows) * len(tgt_rows) > 2500:
        raise ValueError(f"MATRIX_TOO_LARGE: {len(src_rows)}x{len(tgt_rows)}={len(src_rows)*len(tgt_rows)} cells >2500; filter by document")
    traces = export_table(str(session.db_path), "Trace")
    trace_set = {(int(t.get("source", -1) or -1), int(t.get("target", -1) or -1)) for t in traces}
    matrix: list[list[bool]] = []
    for s in src_rows:
        row = []
        s_oid = int(s.get("oid", -1) or -1)
        for t in tgt_rows:
            t_oid = int(t.get("oid", -1) or -1)
            row.append((s_oid, t_oid) in trace_set)
        matrix.append(row)
    return {"matrix": matrix, "sources": src_rows, "targets": tgt_rows, "project_id": project_id}

def validate_project(session_manager, project_id: str) -> dict[str, Any]:
    from ..jet.mdbtools import export_table
    session = session_manager.get(project_id)
    errors: list[dict] = []
    warnings: list[dict] = []
    stats: dict[str, int] = {}
    # Iterate all writable types
    from ..jet.schema import WRITABLE_TYPES, TYPE_TO_TABLE
    for typ, tbl in TYPE_TO_TABLE.items():
        if typ in ["trace", "change"] or tbl.startswith("Is"):
            continue
        try:
            rows = export_table(str(session.db_path), tbl)
            stats[typ] = len(rows)
            for r in rows:
                oid = r.get("oid")
                name = r.get("name")
                if not name or not str(name).strip():
                    errors.append({"type": typ, "oid": oid, "code": "MISSING_NAME", "message": "name required"})
                # Check document FK if column exists
                if "document" in r and r["document"] is not None:
                    try:
                        doc_oid = int(r["document"])
                        found = False
                        for dtbl in ["C_RequirementsSpecification", "D_RequirementsSpecification"]:
                            try:
                                drows = export_table(str(session.db_path), dtbl)
                                if any(int(dr.get("oid", -1)) == doc_oid for dr in drows):
                                    found = True
                                    break
                            except:  # noqa
                                pass
                        if not found:
                            warnings.append({"type": typ, "oid": oid, "code": "ORPHAN_DOCUMENT", "message": f"document {doc_oid} not found"})
                    except:
                        pass
                # Check duplicate number within document
        except Exception as e:
            warnings.append({"type": typ, "code": "EXPORT_FAILED", "message": str(e)})
    # Trace FKs
    try:
        traces = export_table(str(session.db_path), "Trace")
        stats["trace"] = len(traces)
        all_oids = set()
        for typ, tbl in TYPE_TO_TABLE.items():
            try:
                rows = export_table(str(session.db_path), tbl)
                for r in rows:
                    all_oids.add(int(r.get("oid", -1)))
            except:
                pass
        for t in traces:
            src = t.get("source")
            tgt = t.get("target")
            try:
                if src is not None and int(src) not in all_oids:
                    errors.append({"type": "trace", "oid": t.get("oid"), "code": "DANGLING_SOURCE", "message": f"source {src} not found"})
                if tgt is not None and int(tgt) not in all_oids:
                    errors.append({"type": "trace", "oid": t.get("oid"), "code": "DANGLING_TARGET", "message": f"target {tgt} not found"})
            except:
                pass
    except Exception as e:
        warnings.append({"code": "TRACE_VALIDATION_FAILED", "message": str(e)})
    return {"errors": errors, "warnings": warnings, "stats": stats, "project_id": project_id}
