"""MCP Server factory - registers tools, resources, prompts."""
from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource, Prompt, GetPromptResult, PromptMessage

from .session import SessionManager
from .jet.schema import REM_TYPE_VALUES
from .tools import crud as crud_tools
from .tools import traces as trace_tools
from .tools import xml_ops as xml_tools
from .tools import generation as gen_tools
from .tools import system as sys_tools
from .resources.registry import register_resources
from .prompts.registry import register_prompts

def create_server(session_manager: SessionManager) -> Server:
    server = Server("remus-mcp")

    # ---- Tools ----
    @server.list_tools()
    async def list_tools():
        return [
            Tool(name="open_project", description="Open a .rem project file", inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
            Tool(name="close_project", description="Close a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}),
            Tool(name="list_projects", description="List open projects", inputSchema={"type": "object", "properties": {}}),
            Tool(name="rem_list", description="List entities of a type", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string", "enum": REM_TYPE_VALUES}, "document": {"type": ["integer", "null"]}, "parent": {"type": ["integer", "null"]}, "search": {"type": ["string", "null"]}, "filters": {"type": ["object", "null"]}, "limit": {"type": "integer"}, "offset": {"type": "integer"}, "order_by": {"type": "string"}}, "required": ["project_id", "type"]}),
            Tool(name="rem_get", description="Get entity by oid", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string", "enum": REM_TYPE_VALUES}, "oid": {"type": "integer"}}, "required": ["project_id", "type", "oid"]}),
            Tool(name="rem_create", description="Create entity", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string", "enum": REM_TYPE_VALUES}, "data": {"type": "object"}}, "required": ["project_id", "type", "data"]}),
            Tool(name="rem_update", description="Update entity", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string", "enum": REM_TYPE_VALUES}, "oid": {"type": "integer"}, "patch": {"type": "object"}}, "required": ["project_id", "type", "oid", "patch"]}),
            Tool(name="rem_delete", description="Delete entity", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "type": {"type": "string", "enum": REM_TYPE_VALUES}, "oid": {"type": "integer"}, "cascade": {"type": "boolean"}}, "required": ["project_id", "type", "oid"]}),
            Tool(name="trace_add", description="Add trace", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "source_oid": {"type": "integer"}, "target_oid": {"type": "integer"}, "checked": {"type": "boolean"}}, "required": ["project_id", "source_oid", "target_oid"]}),
            Tool(name="trace_remove", description="Remove trace", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "source_oid": {"type": "integer"}, "target_oid": {"type": "integer"}}, "required": ["project_id", "source_oid", "target_oid"]}),
            Tool(name="get_traces", description="Get traces for oid", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "oid": {"type": "integer"}, "direction": {"type": "string", "enum": ["incoming", "outgoing", "both"]}}, "required": ["project_id", "oid"]}),
            Tool(name="trace_matrix", description="Trace matrix", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "source_type": {"type": "string", "enum": REM_TYPE_VALUES}, "target_type": {"type": "string", "enum": REM_TYPE_VALUES}, "document": {"type": ["integer", "null"]}}, "required": ["project_id", "source_type", "target_type"]}),
            Tool(name="validate_project", description="Validate project", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}),
            Tool(name="export_xml", description="Export XML", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "document": {"type": ["string", "null"]}, "filter_type": {"type": ["string", "null"]}, "filter_ids": {"type": ["array", "null"], "items": {"type": "integer"}}}, "required": ["project_id"]}),
            Tool(name="import_xml", description="Import XML", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "xml": {"type": ["string", "null"]}, "file_path": {"type": ["string", "null"]}, "strategy": {"type": "string", "enum": ["merge", "replace"]}, "dry_run": {"type": "boolean"}, "confirm_replace": {"type": "boolean"}, "on_missing_ref": {"type": "string"}}, "required": ["project_id"]}),
            Tool(name="render_html", description="Render HTML/PDF via Wine msxml3", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "document": {"type": "string", "enum": ["c_requirementsSpecification", "d_requirementsSpecification", "defectsSpecification", "changeRequestsSpecification"]}, "lang": {"type": "string", "enum": ["en", "es", "de"]}, "output": {"type": "string", "enum": ["html", "pdf"]}}, "required": ["project_id", "document"]}),
            Tool(name="project_create", description="Create new project from template", inputSchema={"type": "object", "properties": {"template": {"type": "string", "enum": ["english", "spanish", "german", "empty"]}, "target_path": {"type": "string"}, "name": {"type": "string"}}, "required": ["template", "target_path", "name"]}),
            Tool(name="project_clone", description="Clone project", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "target_path": {"type": "string"}}, "required": ["project_id", "target_path"]}),
            Tool(name="undo_last", description="Undo last mutation", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}),
            Tool(name="get_change_log", description="Get change log", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["project_id"]}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]):
        try:
            if name == "open_project":
                pid = session_manager.open_project(arguments["path"])
                return [TextContent(type="text", text=json.dumps({"project_id": pid, "path": arguments["path"]}, indent=2))]
            elif name == "close_project":
                session_manager.close_project(arguments["project_id"])
                return [TextContent(type="text", text=json.dumps({"closed": arguments["project_id"]}))]
            elif name == "list_projects":
                return [TextContent(type="text", text=json.dumps(session_manager.list_projects(), indent=2, default=str))]
            elif name == "rem_list":
                res = crud_tools.rem_list(session_manager, arguments["project_id"], arguments["type"], arguments.get("document"), arguments.get("parent"), arguments.get("search"), arguments.get("filters"), arguments.get("limit", 50), arguments.get("offset", 0), arguments.get("order_by", "order"))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "rem_get":
                res = crud_tools.rem_get(session_manager, arguments["project_id"], arguments["type"], arguments["oid"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "rem_create":
                res = crud_tools.rem_create(session_manager, arguments["project_id"], arguments["type"], arguments["data"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "rem_update":
                res = crud_tools.rem_update(session_manager, arguments["project_id"], arguments["type"], arguments["oid"], arguments["patch"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "rem_delete":
                res = crud_tools.rem_delete(session_manager, arguments["project_id"], arguments["type"], arguments["oid"], arguments.get("cascade", False))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "trace_add":
                res = trace_tools.trace_add(session_manager, arguments["project_id"], arguments["source_oid"], arguments["target_oid"], arguments.get("checked", False))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "trace_remove":
                res = trace_tools.trace_remove(session_manager, arguments["project_id"], arguments["source_oid"], arguments["target_oid"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "get_traces":
                res = trace_tools.get_traces(session_manager, arguments["project_id"], arguments["oid"], arguments.get("direction", "both"))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "trace_matrix":
                res = trace_tools.trace_matrix(session_manager, arguments["project_id"], arguments["source_type"], arguments["target_type"], arguments.get("document"))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "validate_project":
                res = trace_tools.validate_project(session_manager, arguments["project_id"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "export_xml":
                res = xml_tools.export_xml(session_manager, arguments["project_id"], arguments.get("document"), arguments.get("filter_type"), arguments.get("filter_ids"))
                # Truncate xml for display if large > 50k? Return path + snippet
                out = {"path": res["path"], "dtd_errors": res["dtd_errors"], "xml_preview": res["xml"][:2000], "xml_length": len(res["xml"])}
                return [TextContent(type="text", text=json.dumps(out, indent=2))]
            elif name == "import_xml":
                res = xml_tools.import_xml(session_manager, arguments["project_id"], arguments.get("xml"), arguments.get("file_path"), arguments.get("strategy", "merge"), arguments.get("dry_run", False), arguments.get("confirm_replace", False), arguments.get("on_missing_ref", "error"))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "render_html":
                res = gen_tools.render_html(session_manager, arguments["project_id"], arguments["document"], arguments.get("lang", "en"), arguments.get("output", "html"))
                out = {"path": res["path"], "warnings": res["warnings"], "html_preview": res["html"][:5000], "html_length": len(res["html"])}
                return [TextContent(type="text", text=json.dumps(out, indent=2))]
            elif name == "project_create":
                res = sys_tools.project_create(session_manager, arguments["template"], arguments["target_path"], arguments["name"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "project_clone":
                res = sys_tools.project_clone(session_manager, arguments["project_id"], arguments["target_path"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "undo_last":
                res = session_manager.undo_last(arguments["project_id"])
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            elif name == "get_change_log":
                res = sys_tools.get_change_log(session_manager, arguments["project_id"], arguments.get("limit", 50))
                return [TextContent(type="text", text=json.dumps(res, indent=2, default=str))]
            else:
                raise ValueError(f"Unknown tool {name}")
        except Exception as e:
            # Return isError true via TextContent with error flag? MCP python SDK: raise? We'll return error text with isError handling outside.
            # For now return error JSON and let caller treat as error via exception
            err_code = type(e).__name__
            msg = e.args[0] if (e.args and isinstance(e.args[0], str)) else str(e)
            msg = msg.strip("'\"")
            # Map known prefixes
            if any(k in msg for k in ["INVALID_TYPE", "LIMIT_TOO_LARGE", "VALIDATION_ERROR", "REFERENTIAL_INTEGRITY", "MATRIX_TOO_LARGE", "NOT_FOUND", "PROJECT_NOT_FOUND", "DB_LOCKED", "DTD_VALIDATION_ERROR", "DUPLICATE_TRACE"]):
                code = msg.split(":")[0].strip("'\"")
                return [TextContent(type="text", text=json.dumps({"error": msg, "code": code}, indent=2))]
            # For file not found etc.
            return [TextContent(type="text", text=json.dumps({"error": msg, "code": err_code}, indent=2))]

    # Resources
    list_res_impl, read_res_impl = register_resources(server, session_manager)

    @server.list_resources()
    async def list_resources():
        impl = list_res_impl()
        return [Resource(uri=r["uri"], name=r["name"], mimeType=r.get("mimeType", "application/json"), description=r.get("name")) for r in impl]

    @server.read_resource()
    async def read_resource(uri: str):
        from mcp.types import TextResourceContents
        text = read_res_impl(uri)
        return text  # SDK expects string or list? Some versions return str; adapt

    # Prompts
    list_prompts_impl, get_prompt_impl = register_prompts(server, session_manager)

    @server.list_prompts()
    async def list_prompts():
        impl = list_prompts_impl()
        return [Prompt(name=p["name"], description=p["description"], arguments=[{"name": a["name"], "required": a.get("required", False)} for a in p.get("arguments", [])]) for p in impl]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, Any] | None):
        res = get_prompt_impl(name, arguments or {})
        msgs = res["messages"]
        return GetPromptResult(messages=[PromptMessage(role=m["role"], content=TextContent(type="text", text=m["content"]["text"])) for m in msgs])

    return server
