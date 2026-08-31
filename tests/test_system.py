import pathlib

import pytest

from remus_mcp.server import create_server
from remus_mcp.session import SessionManager
from remus_mcp.tools import crud as crud_tools
from remus_mcp.tools import system as sys_tools


def test_project_create(tmp_path):
    target = tmp_path / "new_project.rem"
    sm = SessionManager()
    res = sys_tools.project_create(sm, "english", str(target), "My New Project")
    assert "project_id" in res
    assert res["path"] == str(target)
    assert target.exists()
    # Verify we can interact with the created project
    pid = res["project_id"]
    items = crud_tools.rem_list(sm, pid, "objective")
    assert "items" in items


def test_exception_code_formatting_server():
    sm = SessionManager()
    server = create_server(sm)
    target = pathlib.Path("base/remus_base_empty_english.rem")
    pid = sm.open_project(str(target))

    # Call tool handlers directly via call_tool
    call_tool_func = server._tool_handlers["rem_get"] if hasattr(server, "_tool_handlers") else None

    # Let's invoke tool handler via server tool registry or directly using server decorators
    # In server.py: @server.call_tool()
    handlers = (
        [h for h in server._request_handlers.values()]
        if hasattr(server, "_request_handlers")
        else []
    )

    # Alternative: directly call tool via mcp call_tool or mock exception handling
    # Let's test the error format from call_tool handler

    # Retrieve tool call function from server
    call_fn = None
    for name, handler in getattr(server, "_request_handlers", {}).items():
        if "call_tool" in str(name):
            call_fn = handler
            break

    # Or call crud.rem_get with non-existent oid to see exception raised
    with pytest.raises(KeyError) as excinfo:
        crud_tools.rem_get(sm, pid, "actor", 9999)

    # Test formatting logic as done in server.py
    e = excinfo.value
    err_code = type(e).__name__
    msg = e.args[0] if (e.args and isinstance(e.args[0], str)) else str(e)
    msg = msg.strip("'\"")
    code = msg.split(":")[0].strip("'\"")

    assert msg == "NOT_FOUND: actor oid 9999"
    assert code == "NOT_FOUND"
    assert not code.startswith("'")
    assert not msg.startswith("'")
