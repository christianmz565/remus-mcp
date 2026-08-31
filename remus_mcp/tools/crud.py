"""Typed CRUD quartet."""

from __future__ import annotations

from typing import Any

from ..config import DEFAULT_LIMIT, MAX_LIMIT
from ..jet.mdbtools import JetWriteNotSupported, execute_sql, export_table, max_oid, sql_escape
from ..jet.schema import TYPE_TO_TABLE
from ..validation import validate_create, validate_update


def _ensure_type(type_name: str):
    if type_name not in TYPE_TO_TABLE:
        raise ValueError(f"INVALID_TYPE: {type_name}")


def _table_for(type_name: str) -> str:
    _ensure_type(type_name)
    return TYPE_TO_TABLE[type_name]


def rem_list(
    session_manager,
    project_id: str,
    type: str,
    document: int | None = None,
    parent: int | None = None,
    search: str | None = None,
    filters: dict | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    order_by: str = "order",
) -> dict[str, Any]:
    if limit > MAX_LIMIT:
        raise ValueError(f"LIMIT_TOO_LARGE: limit capped at {MAX_LIMIT}")
    table = _table_for(type)
    session = session_manager.get(project_id)
    rows = export_table(str(session.db_path), table)
    total = len(rows)
    # Filters
    filtered = rows
    if document is not None:
        filtered = [
            r
            for r in filtered
            if r.get("document") is not None and int(r["document"]) == int(document)
        ]
    if parent is not None:
        filtered = [
            r for r in filtered if r.get("parent") is not None and int(r["parent"]) == int(parent)
        ]
    if filters:
        for k, v in filters.items():
            filtered = [r for r in filtered if str(r.get(k, "")) == str(v) or r.get(k) == v]
    if search:
        s = search.lower()

        def matches(r):
            for f in ["name", "description", "comments"]:
                val = r.get(f)
                if val and s in str(val).lower():
                    return True
            return False

        filtered = [r for r in filtered if matches(r)]
    # Order
    if order_by:
        if filtered and order_by not in filtered[0]:
            raise ValueError(f"INVALID_ORDER_BY: {order_by}")
        if filtered:
            filtered = sorted(filtered, key=lambda r: (r.get(order_by) is None, r.get(order_by)))
    total_filtered = len(filtered)
    paged = filtered[offset : offset + limit]
    return {"items": paged, "total": total_filtered, "project_id": project_id, "type": type}


def rem_get(session_manager, project_id: str, type: str, oid: int) -> dict[str, Any]:
    table = _table_for(type)
    session = session_manager.get(project_id)
    rows = export_table(str(session.db_path), table)
    for r in rows:
        if int(r.get("oid", -1) or -1) == int(oid):
            return {"item": r, "project_id": project_id, "type": type}
    raise KeyError(f"NOT_FOUND: {type} oid {oid}")


def _build_insert_sql(table: str, row: dict[str, Any]) -> str:
    cols = ", ".join(f"[{k}]" for k in row)
    vals = ", ".join(sql_escape(v) for v in row.values())
    return f"INSERT INTO [{table}] ({cols}) VALUES ({vals})"


def _build_update_sql(table: str, oid: int, patch: dict[str, Any]) -> str:
    sets = ", ".join(f"[{k}]={sql_escape(v)}" for k, v in patch.items())
    return f"UPDATE [{table}] SET {sets} WHERE [oid]={int(oid)}"


def rem_create(session_manager, project_id: str, type: str, data: dict[str, Any]) -> dict[str, Any]:
    table = _table_for(type)
    session = session_manager.get(project_id)
    # Validation
    errors = validate_create(type, data, str(session.db_path))
    if errors:
        raise ValueError(f"VALIDATION_ERROR: {errors}")
    # Auto-assign fields
    with session_manager.mutate(project_id, "rem_create", type, None):
        # Determine oid
        new_oid = max_oid(str(session.db_path), table) + 1
        row: dict[str, Any] = {}
        row["oid"] = new_oid
        # Copy supplied data
        for k, v in data.items():
            row[k] = v
        # Auto version
        if "versionMajor" not in row or row["versionMajor"] is None:
            row["versionMajor"] = 1
        if "versionMinor" not in row or row["versionMinor"] is None:
            row["versionMinor"] = 0
        if "versionDate" not in row or row["versionDate"] is None:
            import datetime

            row["versionDate"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Auto order
        if "order" not in row or row["order"] is None:
            try:
                rows = export_table(str(session.db_path), table)
                max_order = 0
                for r in rows:
                    # filter by parent/document if applicable
                    if "parent" in data and data.get("parent") is not None:
                        if r.get("parent") != data.get("parent"):
                            continue
                    if "document" in data and data.get("document") is not None:
                        if r.get("document") != data.get("document"):
                            continue
                    try:
                        o = int(r.get("order") or 0)
                        max_order = max(max_order, o)
                    except:
                        pass
                row["order"] = max_order + 1
            except Exception:
                row["order"] = 1
        # For columns not in schema, let DB handle; but we should ensure required defaults
        # Execute
        sql = _build_insert_sql(table, row)
        try:
            execute_sql(str(session.db_path), sql)
        except JetWriteNotSupported as e:
            raise RuntimeError(f"Jet write not supported (need jackcess fallback): {e}")
        except Exception as e:
            raise RuntimeError(f"INSERT failed: {e} sql={sql[:500]}")
        session_manager.append_change(project_id, "rem_create", new_oid, type)
        # Read back
        rows2 = export_table(str(session.db_path), table)
        for r in rows2:
            if int(r.get("oid", -1)) == new_oid:
                return {"oid": new_oid, "item": r, "project_id": project_id, "type": type}
        return {"oid": new_oid, "item": row, "project_id": project_id, "type": type}


def rem_update(
    session_manager, project_id: str, type: str, oid: int, patch: dict[str, Any]
) -> dict[str, Any]:
    table = _table_for(type)
    session = session_manager.get(project_id)
    errors = validate_update(type, patch, str(session.db_path))
    if errors:
        raise ValueError(f"VALIDATION_ERROR: {errors}")
    # Verify exists
    rows = export_table(str(session.db_path), table)
    existing = None
    for r in rows:
        if int(r.get("oid", -1)) == int(oid):
            existing = r
            break
    if existing is None:
        raise KeyError(f"NOT_FOUND: {type} oid {oid}")
    with session_manager.mutate(project_id, "rem_update", type, oid):
        # Bump versionMinor + date
        import datetime

        patch2 = dict(patch)
        # If versionMinor exists, bump
        try:
            vm = int(existing.get("versionMinor") or 0)
            if "versionMinor" not in patch2:
                patch2["versionMinor"] = vm + 1
        except:
            pass
        patch2["versionDate"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = _build_update_sql(table, oid, patch2)
        try:
            execute_sql(str(session.db_path), sql)
        except JetWriteNotSupported as e:
            raise RuntimeError(f"Jet write not supported: {e}")
        except Exception as e:
            raise RuntimeError(f"UPDATE failed: {e} sql={sql[:500]}")
        session_manager.append_change(project_id, "rem_update", oid, type)
        rows2 = export_table(str(session.db_path), table)
        for r in rows2:
            if int(r.get("oid", -1)) == int(oid):
                return {"item": r, "project_id": project_id, "type": type}
        return {"item": {**existing, **patch2}, "project_id": project_id, "type": type}


def rem_delete(
    session_manager, project_id: str, type: str, oid: int, cascade: bool = False
) -> dict[str, Any]:
    table = _table_for(type)
    session = session_manager.get(project_id)
    rows = export_table(str(session.db_path), table)
    if not any(int(r.get("oid", -1)) == int(oid) for r in rows):
        raise KeyError(f"NOT_FOUND: {type} oid {oid}")
    # Check referential integrity: Trace, IsAuthorOf, etc.
    refs = []
    # Trace
    try:
        traces = export_table(str(session.db_path), "Trace")
        for t in traces:
            if int(t.get("source", -1) or -1) == int(oid) or int(t.get("target", -1) or -1) == int(
                oid
            ):
                refs.append({"table": "Trace", "oid": t.get("oid")})
    except Exception:
        pass
    # Other join tables
    for jtbl in ["IsAuthorOf", "IsPreparedFor", "IsPreparedBy", "Step"]:
        try:
            jrows = export_table(str(session.db_path), jtbl)
            for jr in jrows:
                # Step.owner maybe?
                for k in [
                    "specificationObject",
                    "owner",
                    "source",
                    "target",
                    "object",
                    "Author",
                    "Specification",
                ]:
                    if k in jr and jr[k] is not None and int(jr[k]) == int(oid):
                        refs.append({"table": jtbl, "oid": jr.get("oid")})
                # Generic check any int column equals oid
                for kk, vv in jr.items():
                    if vv is not None:
                        try:
                            if int(vv) == int(oid) and kk.lower() not in ["oid"]:
                                # already captured?
                                pass
                        except:
                            pass
        except Exception:
            pass
    if refs and not cascade:
        raise ValueError(f"REFERENTIAL_INTEGRITY: {refs}")
    with session_manager.mutate(project_id, "rem_delete", type, oid):
        # Cascade delete traces first
        if cascade and refs:
            for ref in refs:
                if ref["table"] == "Trace":
                    try:
                        execute_sql(
                            str(session.db_path),
                            f"DELETE FROM [Trace] WHERE [oid]={int(ref['oid'])}",
                        )
                    except Exception:
                        pass
        sql = f"DELETE FROM [{table}] WHERE [oid]={int(oid)}"
        try:
            execute_sql(str(session.db_path), sql)
        except JetWriteNotSupported as e:
            raise RuntimeError(f"Jet write not supported: {e}")
        except Exception as e:
            raise RuntimeError(f"DELETE failed: {e}")
        session_manager.append_change(project_id, "rem_delete", oid, type)
        return {
            "deleted": 1,
            "project_id": project_id,
            "type": type,
            "oid": oid,
            "cascade_deleted": len(refs) if cascade else 0,
        }
