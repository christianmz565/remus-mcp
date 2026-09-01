"""Multi-file session manager + file locking + backup."""

from __future__ import annotations

import fcntl
import hashlib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .jet.schema import DOC_SPEC_TYPES, SPEC_OBJECT_TYPES, VALID_CHANGE_OP_TYPES
from .config import resolve_project_path
from .jet.mdbtools import (
    JetWriteNotSupported,
    execute_sql,
    export_table,
    list_tables,
    max_oid,
    sql_escape,
)


@dataclass
class ProjectSession:
    db_path: Path
    project_id: str
    lock_fd: Any = None
    backup_path: Path | None = None
    undo_stack: list[tuple[str, Path, int]] = field(
        default_factory=list
    )  # (project_id, backup_path, change_oid)


class SessionManager:
    def __init__(self):
        self.projects: dict[str, ProjectSession] = {}

    def _project_id_for(self, path: Path) -> str:
        # Use stem + first 6 of sha1 absolute path
        h = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:8]
        return f"{path.stem}_{h}"

    def open_project(self, path: str) -> str:
        p = resolve_project_path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not p.suffix.lower() == ".rem":
            raise ValueError(f"Not a .rem file: {path}")
        # Validate it's a REMUS DB by listing tables
        tables = list_tables(str(p))
        if "Objective" not in tables and "C_RequirementsSpecification" not in tables:
            raise ValueError(
                f"Not a REMUS database (missing Objective/C_RequirementsSpecification): tables={tables[:10]}"
            )
        pid = self._project_id_for(p)
        if pid in self.projects:
            # Update path if same id but path changed? Just return
            return pid
        session = ProjectSession(db_path=p, project_id=pid)
        self.projects[pid] = session
        return pid

    def close_project(self, project_id: str) -> None:
        if project_id not in self.projects:
            raise KeyError(project_id)
        del self.projects[project_id]

    def get(self, project_id: str) -> ProjectSession:
        if project_id not in self.projects:
            raise KeyError(f"PROJECT_NOT_FOUND: {project_id}")
        return self.projects[project_id]

    def list_projects(self) -> list[dict[str, Any]]:
        out = []
        for pid, sess in self.projects.items():
            try:
                tables = list_tables(str(sess.db_path))
            except Exception:
                tables = []
            # Try to get doc counts
            docs = {}
            for dtbl in [
                "C_RequirementsSpecification",
                "D_RequirementsSpecification",
                "DefectsSpecification",
                "ChangeRequestsSpecification",
            ]:
                try:
                    rows = export_table(str(sess.db_path), dtbl)
                    docs[dtbl] = len(rows)
                except Exception:
                    docs[dtbl] = 0
            out.append(
                {
                    "project_id": pid,
                    "path": str(sess.db_path),
                    "name": sess.db_path.stem,
                    "tables": tables[:5],
                    "documents": docs,
                }
            )
        return out

    def _acquire_lock(self, session: ProjectSession, timeout: float = 5.0):
        start = time.time()
        fd = open(session.db_path, "rb")
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                session.lock_fd = fd
                return
            except BlockingIOError:
                if time.time() - start > timeout:
                    fd.close()
                    raise RuntimeError("DB_LOCKED: Project is locked by another operation")
                time.sleep(0.1)

    def _release_lock(self, session: ProjectSession):
        if session.lock_fd is not None:
            try:
                fcntl.flock(session.lock_fd, fcntl.LOCK_UN)
                session.lock_fd.close()
            except Exception:
                pass
            session.lock_fd = None

    def _backup(self, session: ProjectSession) -> Path:
        ts = int(time.time())
        backup_path = Path(str(session.db_path) + f".bak.{ts}")
        shutil.copy2(session.db_path, backup_path)
        # Rotate keep last 5
        pattern = f"{session.db_path.name}.bak.*"
        backups = sorted(
            session.db_path.parent.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for old in backups[5:]:
            try:
                old.unlink()
            except Exception:
                pass
        session.backup_path = backup_path
        return backup_path

    def mutate(
        self, project_id: str, tool_name: str, type_name: str | None = None, oid: int | None = None
    ):
        """Context manager for mutations: lock + backup + Change log + unlock."""
        session = self.get(project_id)

        class Ctx:
            def __enter__(inner_self):
                self._acquire_lock(session)
                backup = self._backup(session)
                inner_self.backup = backup
                return inner_self

            def __exit__(inner_self, exc_type, exc, tb):
                if exc_type is not None:
                    # On error, restore backup
                    shutil.copy2(inner_self.backup, session.db_path)
                self._release_lock(session)
                return False

        return Ctx()

    def append_change(
        self,
        project_id: str,
        tool_name: str,
        subject_oid: int | None,
        entity_type: str | None,
        op_type: str = "U",
    ) -> None:
        if op_type not in VALID_CHANGE_OP_TYPES:
            raise ValueError(f"Invalid operation type: {op_type}")

        if subject_oid is None or subject_oid <= 0:
            raise ValueError(f"Invalid subject_oid: {subject_oid}")

        if not entity_type:
            raise ValueError("entity_type is required")

        if entity_type in DOC_SPEC_TYPES:
            subject_type_code = "D"
        elif entity_type in SPEC_OBJECT_TYPES:
            subject_type_code = "O"
        else:
            # Non-specification entities (traces, join tables) are not logged in Change table
            return

        session = self.get(project_id)
        oid = max_oid(str(session.db_path), "Change") + 1

        import datetime

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        desc = f"MCP: {tool_name} by agent"

        sql = (
            f"INSERT INTO [Change] ([oid], [date], [type], [subject], [subjectType], [description]) "
            f"VALUES ({oid}, {sql_escape(date_str)}, {sql_escape(op_type)}, {subject_oid}, {sql_escape(subject_type_code)}, {sql_escape(desc)})"
        )
        execute_sql(str(session.db_path), sql)

        if session.backup_path is not None:
            session.undo_stack.append((project_id, session.backup_path, oid))
    def undo_last(self, project_id: str) -> dict[str, Any]:
        session = self.get(project_id)
        if not session.undo_stack:
            raise RuntimeError("No undo available")
        pid, backup_path, change_oid = session.undo_stack.pop()
        # Restore backup
        if not backup_path.exists():
            raise RuntimeError(f"Backup not found: {backup_path}")
        self._acquire_lock(session)
        try:
            shutil.copy2(backup_path, session.db_path)
            # Delete Change row if exists
            execute_sql(str(session.db_path), f"DELETE FROM [Change] WHERE [oid]={change_oid}")
        finally:
            self._release_lock(session)
        return {"restored": True, "backup": str(backup_path), "change_oid": change_oid}
