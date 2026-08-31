import shutil

import pytest
from conftest import find_base

from remus_mcp.session import SessionManager
from remus_mcp.tools import crud, traces


@pytest.fixture
def project(tmp_path):
    src = find_base("english")
    dst = tmp_path / "test.rem"
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    return sm, pid


def test_trace_add_remove_matrix(project):
    sm, pid = project
    o1 = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "O1",
            "description": "o1",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    o2 = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "O2",
            "description": "o2",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    # Add trace
    tr = traces.trace_add(sm, pid, o1["oid"], o2["oid"])
    assert "trace_oid" in tr
    # Matrix should have 1 true cell
    mat = traces.trace_matrix(sm, pid, "objective", "objective")
    # Find indices
    assert mat["matrix"][0][1] is True
    # Remove
    traces.trace_remove(sm, pid, o1["oid"], o2["oid"])
    mat2 = traces.trace_matrix(sm, pid, "objective", "objective")
    assert mat2["matrix"][0][1] is False


def test_validate_project(project):
    sm, pid = project
    crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "O1",
            "description": "o1",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    res = traces.validate_project(sm, pid)
    assert "errors" in res and "stats" in res
    assert res["stats"]["objective"] == 1
    assert len(res["errors"]) == 0
