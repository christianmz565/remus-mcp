"""Jackcess/UCanAccess fallback via JPype (lazy)."""

from __future__ import annotations

import pathlib
import re
from typing import Any

from ..config import get_jars_dir

_jvm_started = False


def _ensure_jvm():
    global _jvm_started
    if _jvm_started:
        return
    import os
    import shutil

    import jpype

    if jpype.isJVMStarted():
        _jvm_started = True
        return

    if "JAVA_HOME" not in os.environ:
        java_bin = shutil.which("java")
        if java_bin:
            java_path = pathlib.Path(java_bin).resolve()
            os.environ["JAVA_HOME"] = str(java_path.parent.parent)
    jars_dir = get_jars_dir()
    jars = list(jars_dir.glob("*.jar"))
    if not jars:
        raise RuntimeError(f"No jars found in directory: {jars_dir}")

    jpype.startJVM(classpath=[str(j) for j in jars])
    _jvm_started = True


def _parse_sql_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.upper() == "NULL":
        return None
    if raw.startswith("'") and raw.endswith("'"):
        inner = raw[1:-1].replace("''", "'")
        return inner
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        try:
            return int(raw)
        except:
            return raw
    try:
        if "." in raw:
            return float(raw)
    except:
        pass
    return raw


def _sql_unescape(s: str) -> str:
    return s.replace("''", "'")


def execute_sql_via_jackcess(db_path: str, sql: str):
    _ensure_jvm()
    import jpype
    from jpype import JClass

    DBB = JClass("com.healthmarketscience.jackcess.DatabaseBuilder")
    File = JClass("java.io.File")
    HashMap = JClass("java.util.HashMap")
    # Date handling
    SimpleDateFormat = JClass("java.text.SimpleDateFormat")
    sdf1 = SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
    sdf2 = SimpleDateFormat("yyyy-MM-dd")
    sdf3 = SimpleDateFormat("dd/MM/yy HH:mm:ss")
    sdf4 = SimpleDateFormat("dd/MM/yyyy HH:mm:ss")

    def _to_date(val_str: str):
        for fmt in (sdf1, sdf2, sdf3, sdf4):
            try:
                return fmt.parse(val_str)
            except Exception:
                pass
        raise ValueError(f"Invalid date format '{val_str}'")
    # Open DB
    db = DBB.open(File(db_path))
    try:
        sql_stripped = sql.strip().rstrip(";")
        # Determine type
        upper = sql_stripped[:10].upper()
        if sql_stripped.upper().startswith("INSERT INTO"):
            # Pattern: INSERT INTO [Table] ([col], ...) VALUES (...)
            # Extract table
            m = re.match(
                r"INSERT\s+INTO\s+\[?([^\]\s]+)\]?\s*\(([^)]+)\)\s*VALUES\s*\((.+)\)",
                sql_stripped,
                re.IGNORECASE | re.DOTALL,
            )
            if not m:
                raise ValueError(f"Cannot parse INSERT: {sql}")
            table = m.group(1)
            cols_raw = m.group(2)
            vals_raw = m.group(3)
            # Split cols
            cols = [c.strip().strip("[]") for c in cols_raw.split(",")]
            # Split vals respecting quotes
            vals = _split_values(vals_raw)
            if len(cols) != len(vals):
                raise ValueError(f"cols/vals mismatch {cols} vs {vals}")
            tbl = db.getTable(table)
            if tbl is None:
                raise ValueError(f"Table {table} not found")
            hm = HashMap()
            for col, val_raw in zip(cols, vals):
                v = _parse_sql_value(val_raw)
                # Convert date columns
                if col.lower() in ("versiondate", "date") and isinstance(v, str):
                    v = _to_date(v)
                if col.lower() in ("ischecked", "checked") and isinstance(v, int):
                    v = jpype.JBoolean(bool(v))
                hm.put(col, v)
            tbl.addRowFromMap(hm)
            db.flush()
        elif sql_stripped.upper().startswith("UPDATE"):
            m = re.match(
                r"UPDATE\s+\[?([^\]\s]+)\]?\s+SET\s+(.+)\s+WHERE\s+\[?oid\]?\s*=\s*(\d+)",
                sql_stripped,
                re.IGNORECASE | re.DOTALL,
            )
            table = m.group(1)
            set_clause = m.group(2)
            oid = int(m.group(3))
            tbl = db.getTable(table)
            if tbl is None:
                raise ValueError(f"Table {table} not found")
            # Parse set_clause into dict
            patches = {}
            for part in _split_set_clause(set_clause):
                if not part.strip():
                    continue
                km = re.match(r"\[?([^\]=]+)\]?\s*=\s*(.+)", part.strip())
                if not km:
                    continue
                col = km.group(1).strip().strip("[]")
                val_raw = km.group(2).strip()
                v = _parse_sql_value(val_raw)
                if col.lower() in ("versiondate", "date") and isinstance(v, str):
                    v = _to_date(v)
                patches[col] = v
            # Find row by oid via cursor
            cursor = tbl.getDefaultCursor()
            row = cursor.getNextRow()
            found = None
            while row is not None:
                oid_val = row.get("oid")
                if oid_val is not None and int(str(oid_val)) == oid:
                    found = row
                    break
                row = cursor.getNextRow()
            if found is None:
                raise KeyError(f"Row oid {oid} not found in {table}")
            for col, v in patches.items():
                found.put(col, v)
            tbl.updateRow(found)
            db.flush()
        elif sql_stripped.upper().startswith("DELETE FROM"):
            m = re.match(
                r"DELETE\s+FROM\s+\[?([^\]\s]+)\]?\s+WHERE\s+\[?oid\]?\s*=\s*(\d+)",
                sql_stripped,
                re.IGNORECASE,
            )
            if not m:
                # Also try DELETE without WHERE? but plan only uses where oid
                mf = re.match(r"DELETE\s+FROM\s+\[?([^\]\s]+)\]?", sql_stripped, re.IGNORECASE)
                if mf:
                    table = mf.group(1)
                    tbl = db.getTable(table)
                    if tbl is None:
                        raise ValueError(f"Table {table} not found")
                    # Delete all rows: iterate and delete
                    # Use cursor to delete each
                    cursor = tbl.getDefaultCursor()
                    row = cursor.getNextRow()
                    to_delete = []
                    while row is not None:
                        to_delete.append(row)
                        row = cursor.getNextRow()
                    for r in to_delete:
                        tbl.deleteRow(r)
                    db.flush()
                    return
                raise ValueError(f"Cannot parse DELETE: {sql}")
            table = m.group(1)
            oid = int(m.group(2))
            tbl = db.getTable(table)
            if tbl is None:
                raise ValueError(f"Table {table} not found")
            cursor = tbl.getDefaultCursor()
            row = cursor.getNextRow()
            found = None
            while row is not None:
                oid_val = row.get("oid")
                if oid_val is not None and int(str(oid_val)) == oid:
                    found = row
                    break
                row = cursor.getNextRow()
            if found is not None:
                tbl.deleteRow(found)
                db.flush()
        else:
            raise ValueError(f"Unsupported SQL via jackcess: {sql[:100]}")
    finally:
        db.close()


def _split_values(s: str):
    """Split CSV respecting single quotes."""
    res = []
    cur = ""
    in_quote = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "'":
            if in_quote and i + 1 < len(s) and s[i + 1] == "'":
                cur += "''"
                i += 2
                continue
            in_quote = not in_quote
            cur += c
        elif c == "," and not in_quote:
            res.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip() != "":
        res.append(cur.strip())
    return res


def _split_set_clause(s: str):
    # Split by comma outside quotes
    return _split_values(s)


class JackcessEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def insert(self, table: str, row: dict[str, Any]):
        _ensure_jvm()
        from jpype import JClass

        DBB = JClass("com.healthmarketscience.jackcess.DatabaseBuilder")
        File = JClass("java.io.File")
        HashMap = JClass("java.util.HashMap")
        db = DBB.open(File(self.db_path))
        try:
            tbl = db.getTable(table)
            hm = HashMap()
            for k, v in row.items():
                hm.put(k, v)
            tbl.addRowFromMap(hm)
            db.flush()
        finally:
            db.close()

    def update(self, table: str, oid: int, patch: dict[str, Any]):
        _ensure_jvm()
        from jpype import JClass

        DBB = JClass("com.healthmarketscience.jackcess.DatabaseBuilder")
        File = JClass("java.io.File")
        db = DBB.open(File(self.db_path))
        try:
            tbl = db.getTable(table)
            cursor = tbl.getDefaultCursor()
            row = cursor.getNextRow()
            found = None
            while row is not None:
                if int(str(row.get("oid"))) == int(oid):
                    found = row
                    break
                row = cursor.getNextRow()
            if found is None:
                raise KeyError(f"Not found {oid}")
            for k, v in patch.items():
                found.put(k, v)
            tbl.updateRow(found)
            db.flush()
        finally:
            db.close()

    def delete(self, table: str, oid: int):
        _ensure_jvm()
        from jpype import JClass

        DBB = JClass("com.healthmarketscience.jackcess.DatabaseBuilder")
        File = JClass("java.io.File")
        db = DBB.open(File(self.db_path))
        try:
            tbl = db.getTable(table)
            cursor = tbl.getDefaultCursor()
            row = cursor.getNextRow()
            while row is not None:
                if int(str(row.get("oid"))) == int(oid):
                    tbl.deleteRow(row)
                    break
                row = cursor.getNextRow()
            db.flush()
        finally:
            db.close()


def get_jackcess_engine(db_path: str) -> JackcessEngine:
    return JackcessEngine(db_path)
