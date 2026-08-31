"""Subprocess wrapper for mdbtools."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import re
from pathlib import Path
from typing import Any

class JetWriteNotSupported(RuntimeError):
    pass

def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def sql_escape(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"

def list_tables(db_path: str) -> list[str]:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(db_path)
    cmd = ["mdb-tables", "-1", str(p)]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"mdb-tables failed: {r.stderr.strip()}")
    tables = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    return tables

def get_schema(db_path: str) -> str:
    r = _run(["mdb-schema", db_path])
    if r.returncode != 0:
        raise RuntimeError(f"mdb-schema failed: {r.stderr.strip()}")
    return r.stdout

def export_table(db_path: str, table: str, fmt: str = "json") -> list[dict[str, Any]]:
    p = Path(db_path)
    # Early check: if table not in list_tables, return []
    try:
        tables = list_tables(str(p))
        if table not in tables:
            return []
    except Exception:
        pass
    if shutil.which("mdb-json"):
        r = _run(["mdb-json", str(p), table])
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout) if r.stdout.strip() else []
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [data]
                return []
            except json.JSONDecodeError:
                pass
    # Try json via mdb-export if supported
    r = _run(["mdb-export", "--help"])
    has_json = "--json" in r.stdout or "--json" in r.stderr
    if has_json and shutil.which("mdb-export"):
        r2 = _run(["mdb-export", "--json", str(p), table])
        if r2.returncode == 0 and r2.stdout.strip():
            try:
                data = json.loads(r2.stdout)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [data]
            except json.JSONDecodeError:
                pass
    r3 = _run(["mdb-export", str(p), table])
    if r3.returncode != 0:
        msg = (r3.stderr or "").lower()
        if "not found" in msg or "does not exist" in msg or "no such" in msg:
            return []
        raise RuntimeError(f"mdb-export failed for {table}: {r3.stderr.strip()}")
    if not r3.stdout.strip():
        return []
    # Parse CSV
    lines = r3.stdout.splitlines()
    reader = csv.DictReader(lines)
    out = []
    for row in reader:
        # Normalize None for empty strings? keep as-is but convert empty to None for optional?
        clean = {k: (v if v != "" else None) for k, v in row.items()}
        # Try to coerce oid numeric
        for k in list(clean.keys()):
            v = clean[k]
            if v is not None and re.fullmatch(r"-?\d+", str(v)):
                # Keep as int if column known numeric; but generic: try int
                try:
                    clean[k] = int(v)
                except:  # noqa: E722
                    pass
        out.append(clean)
    return out

def query_sql(db_path: str, sql: str) -> list[dict[str, Any]]:
    """Run SELECT via mdb-sql if available. Fallback to export_table filtering."""
    if shutil.which("mdb-sql"):
        # mdb-sql interactive: echo sql | mdb-sql db_path
        # Try batch mode
        proc = subprocess.run(
            ["mdb-sql", "-p", str(db_path)],
            input=sql + "\n",
            capture_output=True,
            text=True,
        )
        # Some versions require: mdb-sql db_path < query
        if proc.returncode != 0 or not proc.stdout.strip():
            proc2 = subprocess.run(
                ["mdb-sql", str(db_path)],
                input=sql + "\ngo\n",
                capture_output=True,
                text=True,
            )
            if proc2.returncode == 0 and proc2.stdout.strip():
                # Parse tabular output? For now return raw if JSON-like
                # mdb-sql output is not JSON, difficult to parse. Raise fallback signal.
                raise JetWriteNotSupported(f"mdb-sql tabular parse not implemented: {proc2.stdout[:500]}")
        # If succeeded with parsable output, attempt parse
        if proc.returncode == 0 and proc.stdout.strip():
            # Try to detect JSON? Usually mdb-sql -p prints CSV-ish
            pass
        raise JetWriteNotSupported("query_sql via mdb-sql not reliably parsable; use export_table filter")
    raise JetWriteNotSupported("mdb-sql not available")

def execute_sql(db_path: str, sql: str) -> None:
    # Try mdb-sql first; on failure fallback to jackcess
    if shutil.which("mdb-sql"):
        sql_norm = sql.strip()
        if not sql_norm.endswith(";"):
            sql_norm += ";"
        proc = subprocess.run(
            ["mdb-sql", str(db_path)],
            input=sql_norm + "\ngo\n",
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            if "error" not in proc.stdout.lower() and "error" not in proc.stderr.lower():
                return
            if "syntax error" in proc.stdout.lower() or "syntax error" in proc.stderr.lower():
                pass  # fallback to jackcess
            else:
                raise RuntimeError(f"mdb-sql error: stdout={proc.stdout[:1000]} stderr={proc.stderr[:1000]}")
        else:
            if "syntax error" not in (proc.stderr + proc.stdout).lower():
                raise RuntimeError(f"mdb-sql failed: {proc.stderr.strip() or proc.stdout.strip()}")
    # Fallback to jackcess
    try:
        from .jackcess import execute_sql_via_jackcess
        execute_sql_via_jackcess(db_path, sql)
        return
    except ImportError as e:
        raise JetWriteNotSupported(f"Jackcess fallback not available: {e}")
    except Exception as e:
        raise RuntimeError(f"Jackcess execute failed for sql={sql[:300]}: {e}") from e

def max_oid(db_path: str, table: str) -> int:
    rows = export_table(db_path, table)
    maxv = 0
    for r in rows:
        oid = r.get("oid") or r.get("OID") or 0
        try:
            oid_i = int(oid) if oid is not None else 0
            if oid_i > maxv:
                maxv = oid_i
        except Exception:
            pass
    return maxv
