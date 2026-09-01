"""validate_project, undo, clone, project_create etc."""

from __future__ import annotations

import shutil
from typing import Any

import datetime

from ..config import DEFAULT_LIMIT, get_base_template_path, resolve_project_path
from ..jet.mdbtools import execute_sql, export_table, sql_escape


DEFAULT_DOC_SPECS = [
    ("C_RequirementsSpecification", "c_requirements_specification"),
    ("D_RequirementsSpecification", "d_requirements_specification"),
    ("DefectsSpecification", "defects_specification"),
    ("ChangeRequestsSpecification", "change_requests_specification"),
]


def project_create(session_manager, template: str, target_path: str, name: str) -> dict[str, Any]:
    try:
        src = get_base_template_path(template)
    except FileNotFoundError as e:
        raise ValueError(f"Invalid template {template}") from e
    dst = resolve_project_path(target_path)
    if dst.exists():
        raise ValueError(f"Target already exists: {target_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    pid = session_manager.open_project(str(dst))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for tbl, entity_type in DEFAULT_DOC_SPECS:
        rows = export_table(str(dst), tbl)
        if not rows:
            next_oid = 1
            sql_ins = (
                f"INSERT INTO [{tbl}] "
                f"([oid], [name], [versionMajor], [versionMinor], [versionDate]) "
                f"VALUES ({next_oid}, {sql_escape(name)}, 1, 0, {sql_escape(now_str)})"
            )
            execute_sql(str(dst), sql_ins)
            session_manager.append_change(pid, "project_create", next_oid, entity_type, "C")
        elif tbl == "C_RequirementsSpecification":
            c_oid = int(rows[0]["oid"])
            execute_sql(str(dst), f"UPDATE [{tbl}] SET [name]={sql_escape(name)} WHERE [oid]={c_oid}")
    return {"project_id": pid, "path": str(dst), "name": name}

def project_clone(session_manager, project_id: str, target_path: str) -> dict[str, Any]:
    session = session_manager.get(project_id)
    dst = resolve_project_path(target_path)
    if dst.exists():
        raise ValueError(f"Target exists: {target_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(session.db_path, dst)
    new_pid = session_manager.open_project(str(dst))
    return {"new_project_id": new_pid, "path": str(dst)}


def get_change_log(session_manager, project_id: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    session = session_manager.get(project_id)
    rows = export_table(str(session.db_path), "Change")
    rows_sorted = sorted(rows, key=lambda r: str(r.get("date", "")), reverse=True)
    return {"changes": rows_sorted[:limit], "project_id": project_id}
