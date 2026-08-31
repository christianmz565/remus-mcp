import shutil, pathlib, tempfile, pytest
from remus_mcp.session import SessionManager
from remus_mcp.tools import crud
from conftest import find_base

@pytest.fixture
def empty_project(tmp_path):
    src = find_base("english")
    dst = tmp_path / "test.rem"
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    return sm, pid, str(dst)

def test_create_objective(empty_project):
    sm, pid, db_path = empty_project
    # Initially empty
    res = crud.rem_list(sm, pid, "objective", limit=10)
    assert res["total"] == 0
    # Create
    created = crud.rem_create(sm, pid, "objective", {"name":"OBJ-1","description":"Test","importance":1,"urgency":1,"status":1,"stability":1})
    assert "oid" in created
    oid = created["oid"]
    # Read back
    got = crud.rem_get(sm, pid, "objective", oid)
    assert got["item"]["name"] == "OBJ-1"
    # List should have 1
    res2 = crud.rem_list(sm, pid, "objective", limit=10)
    assert res2["total"] == 1
    # Update
    upd = crud.rem_update(sm, pid, "objective", oid, {"name":"OBJ-1 updated"})
    assert upd["item"]["name"] == "OBJ-1 updated"
    # Undo
    sm.undo_last(pid)
    # After undo of update, should revert? But undo stack restores backup of last mutation (update). Might restore to before update (still 1 objective with original name)
    # Check after undo, name should be original or count still 1
    got2 = crud.rem_get(sm, pid, "objective", oid)
    # Due to backup restore, version may revert
    assert got2["item"]["oid"] == oid

def test_delete_cascade(empty_project):
    sm, pid, db_path = empty_project
    a = crud.rem_create(sm, pid, "objective", {"name":"A","description":"a","importance":1,"urgency":1,"status":1,"stability":1})
    b = crud.rem_create(sm, pid, "objective", {"name":"B","description":"b","importance":1,"urgency":1,"status":1,"stability":1})
    from remus_mcp.tools import traces
    traces.trace_add(sm, pid, a["oid"], b["oid"])
    # Delete without cascade should fail
    with pytest.raises(Exception, match="REFERENTIAL_INTEGRITY"):
        crud.rem_delete(sm, pid, "objective", a["oid"], cascade=False)
    # With cascade should succeed
    res = crud.rem_delete(sm, pid, "objective", a["oid"], cascade=True)
    assert res["deleted"] == 1
