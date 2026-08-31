"""validate_project, undo, clone, project_create etc."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..jet.mdbtools import export_table, execute_sql

def project_create(session_manager, template: str, target_path: str, name: str) -> dict[str, Any]:
    base_map = {
        "english": "base/remus_base_empty_english.rem",
        "spanish": "base/remus_base_empty_spanish.rem",
        "german": "base/remus_base_empty_german.rem",
        "empty": "base/remus_base_empty_english.rem",
    }
    if template not in base_map:
        raise ValueError(f"Invalid template {template}")
    rel = base_map[template]
    # candidates: monorepo, standalone, Docker, absolute dev path
    candidates = [
        Path("/home/cricro/tiny-projects/remus") / rel,
        Path(__file__).parents[3] / rel,  # monorepo /app/base
        Path(__file__).parents[2] / rel,  # standalone mcp/base
        Path(__file__).parents[2] / ".." / rel,
        Path("/app") / rel,
        Path.cwd() / rel,
        Path.cwd() / "mcp" / rel,
        Path(rel),
    ]
    src = next((c for c in candidates if c.exists()), None)
    if src is None:
        raise FileNotFoundError(f"Template not found: {rel} (tried {candidates})")
    dst = Path(target_path)
    if dst.exists():
        raise ValueError(f"Target already exists: {target_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    # TODO: update name in spec docs? For now set via DB update if possible
    pid = session_manager.open_project(str(dst))
    # Try to update name of first spec
    try:
        from ..jet.mdbtools import export_table, execute_sql
        for tbl in ["C_RequirementsSpecification", "D_RequirementsSpecification"]:
            rows = export_table(str(dst), tbl)
            if rows:
                oid = rows[0].get("oid")
                esc_name = name.replace("'", "''")
                execute_sql(str(dst), f"UPDATE [{tbl}] SET [name]='{esc_name}' WHERE [oid]={oid}")
                break
    except Exception:
        pass
    return {"project_id": pid, "path": str(dst), "name": name}

def project_clone(session_manager, project_id: str, target_path: str) -> dict[str, Any]:
    session = session_manager.get(project_id)
    dst = Path(target_path)
    if dst.exists():
        raise ValueError(f"Target exists: {target_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(session.db_path, dst)
    new_pid = session_manager.open_project(str(dst))
    return {"new_project_id": new_pid, "path": str(dst)}

def get_change_log(session_manager, project_id: str, limit: int = 50) -> dict[str, Any]:
    session = session_manager.get(project_id)
    try:
        rows = export_table(str(session.db_path), "Change")
        # Sort by date descending if possible
        try:
            rows_sorted = sorted(rows, key=lambda r: str(r.get("date", "")), reverse=True)
        except Exception:
            rows_sorted = rows
        return {"changes": rows_sorted[:limit], "project_id": project_id}
    except Exception as e:
        return {"changes": [], "project_id": project_id, "error": str(e)}
