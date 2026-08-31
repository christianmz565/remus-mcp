"""validate_project, undo, clone, project_create etc."""

from __future__ import annotations

import shutil
from typing import Any

from ..config import DEFAULT_LIMIT, get_base_template_path, resolve_project_path
from ..jet.mdbtools import execute_sql, export_table


def project_create(session_manager, template: str, target_path: str, name: str) -> dict[str, Any]:
    template_name = "english" if template.lower() == "empty" else template
    try:
        src = get_base_template_path(template_name)
    except FileNotFoundError as e:
        raise ValueError(f"Invalid template {template}") from e
    dst = resolve_project_path(target_path)
    if dst.exists():
        raise ValueError(f"Target already exists: {target_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    # TODO: update name in spec docs? For now set via DB update if possible
    pid = session_manager.open_project(str(dst))
    # Try to update name of first spec
    for tbl in ["C_RequirementsSpecification", "D_RequirementsSpecification"]:
        rows = export_table(str(dst), tbl)
        if rows:
            oid = rows[0].get("oid")
            if oid is not None:
                esc_name = name.replace("'", "''")
                execute_sql(str(dst), f"UPDATE [{tbl}] SET [name]='{esc_name}' WHERE [oid]={oid}")
            break
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
