"""Resources registry."""
from __future__ import annotations

from typing import Any

def register_resources(server, session_manager):
    # We'll register via MCP SDK handlers; this module provides helper functions
    # Actual @server.list_resources / @server.read_resource decorators are set up in transports
    def list_resources_impl():
        resources = []
        for pid in session_manager.projects.keys():
            resources.append({"uri": f"rem://{pid}/projects", "name": "Projects", "mimeType": "application/json"})
            resources.append({"uri": f"rem://{pid}/documents", "name": "Documents"})
            from ..jet.schema import REM_TYPE_VALUES
            for t in REM_TYPE_VALUES:
                resources.append({"uri": f"rem://{pid}/{t}", "name": f"{t} list"})
                # not enumerating per-oid here
            resources.append({"uri": f"rem://{pid}/xml", "name": "Full XML"})
        return resources

    def read_resource_impl(uri: str) -> str:
        # Parse rem://{project_id}/...
        # Format: rem://<pid>/<type> or rem://<pid>/<type>/<oid> or rem://<pid>/trace-matrix/...
        if not uri.startswith("rem://"):
            raise ValueError("Invalid URI")
        rest = uri[len("rem://"):]
        parts = rest.split("/")
        if len(parts) < 2:
            raise ValueError("Invalid resource URI")
        pid = parts[0]
        tail = parts[1:]
        import json
        from ..tools.crud import rem_list, rem_get
        from ..tools.traces import trace_matrix
        from ..tools.xml_ops import export_xml
        from ..jet.mdbtools import export_table

        if tail[0] == "projects":
            return json.dumps(session_manager.list_projects(), indent=2)
        elif tail[0] == "documents":
            # list spec docs
            docs = []
            for tbl in ["C_RequirementsSpecification", "D_RequirementsSpecification", "DefectsSpecification", "ChangeRequestsSpecification"]:
                try:
                    rows = export_table(str(session_manager.get(pid).db_path), tbl)
                    for r in rows:
                        docs.append({"type": tbl, "oid": r.get("oid"), "name": r.get("name"), "version": f"{r.get('versionMajor')}.{r.get('versionMinor')}"})
                except Exception:
                    pass
            return json.dumps(docs, indent=2)
        elif tail[0] == "xml":
            res = export_xml(session_manager, pid)
            return res["xml"]
        elif tail[0] == "trace-matrix" and len(tail) == 3:
            src, tgt = tail[1], tail[2]
            res = trace_matrix(session_manager, pid, src, tgt)
            return json.dumps(res, indent=2, default=str)
        elif len(tail) == 1:
            # type list
            typ = tail[0]
            res = rem_list(session_manager, pid, typ, limit=100)
            return json.dumps(res, indent=2, default=str)
        elif len(tail) == 2:
            typ, oid_s = tail[0], tail[1]
            try:
                oid = int(oid_s)
            except:
                raise ValueError("Invalid oid")
            res = rem_get(session_manager, pid, typ, oid)
            return json.dumps(res, indent=2, default=str)
        else:
            raise ValueError(f"Unknown resource {uri}")

    return list_resources_impl, read_resource_impl
