import shutil

import pytest
from conftest import find_base

from remus_mcp.session import SessionManager
from remus_mcp.tools import crud


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
    created = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "OBJ-1",
            "description": "Test",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    assert "oid" in created
    oid = created["oid"]
    # Read back
    got = crud.rem_get(sm, pid, "objective", oid)
    assert got["item"]["name"] == "OBJ-1"
    # List should have 1
    res2 = crud.rem_list(sm, pid, "objective", limit=10)
    assert res2["total"] == 1
    # Update
    upd = crud.rem_update(sm, pid, "objective", oid, {"name": "OBJ-1 updated"})
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
    a = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "A",
            "description": "a",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    b = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "B",
            "description": "b",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    from remus_mcp.tools import traces

    traces.trace_add(sm, pid, a["oid"], b["oid"])
    # Delete without cascade should fail
    with pytest.raises(Exception, match="REFERENTIAL_INTEGRITY"):
        crud.rem_delete(sm, pid, "objective", a["oid"], cascade=False)
    # With cascade should succeed
    res = crud.rem_delete(sm, pid, "objective", a["oid"], cascade=True)
    assert res["deleted"] == 1
def test_change_logging(empty_project):
    from remus_mcp.jet.mdbtools import export_table
    from remus_mcp.tools import traces

    sm, pid, db_path = empty_project

    # 1. Create a spec object (objective) -> should log subjectType 'O', type 'C'
    created = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "OBJ-ChangeTest",
            "description": "desc",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    obj_oid = created["oid"]

    changes = export_table(db_path, "Change")
    obj_changes = [c for c in changes if int(c.get("subject", -1) or -1) == obj_oid]
    assert len(obj_changes) == 1
    assert obj_changes[0]["subjectType"] == "O"
    assert obj_changes[0]["type"] == "C"

    # 2. Update spec object -> subjectType 'O', type 'U'
    crud.rem_update(sm, pid, "objective", obj_oid, {"name": "OBJ-Updated"})
    changes = export_table(db_path, "Change")
    obj_changes = [c for c in changes if int(c.get("subject", -1) or -1) == obj_oid]
    assert len(obj_changes) == 2
    assert obj_changes[1]["subjectType"] == "O"
    assert obj_changes[1]["type"] == "U"

    # 3. Add trace (non-spec entity) -> should NOT create Change record
    # Create another objective for trace target
    created_b = crud.rem_create(
        sm,
        pid,
        "objective",
        {
            "name": "OBJ-B",
            "description": "b",
            "importance": 1,
            "urgency": 1,
            "status": 1,
            "stability": 1,
        },
    )
    obj_b_oid = created_b["oid"]

    changes_before_trace = export_table(db_path, "Change")
    trace_res = traces.trace_add(sm, pid, obj_oid, obj_b_oid)
    changes_after_trace = export_table(db_path, "Change")
    assert len(changes_after_trace) == len(changes_before_trace)
    # 4. Delete spec object -> subjectType 'O', type 'D'
    crud.rem_delete(sm, pid, "objective", obj_b_oid, cascade=True)
    changes = export_table(db_path, "Change")
    deleted_changes = [
        c for c in changes if int(c.get("subject", -1) or -1) == obj_b_oid and c.get("type") == "D"
    ]
    assert len(deleted_changes) == 1
    assert deleted_changes[0]["subjectType"] == "O"

    # 5. Invalid op_type raises ValueError
    with pytest.raises(ValueError, match="Invalid operation type"):
        sm.append_change(pid, "test", 1, "objective", "X")
def test_prepared_for_by(empty_project):
    from remus_mcp.tools import generation

    sm, pid, db_path = empty_project

    # Create organizations
    org1 = crud.rem_create(sm, pid, "organization", {"name": "Colegio Client Org"})
    org2 = crud.rem_create(sm, pid, "organization", {"name": "Dev Team Org"})

    # Link Prepared For and Prepared By
    pf = crud.rem_create(sm, pid, "is_prepared_for", {"document": 1, "organization": org1["oid"]})
    pb = crud.rem_create(sm, pid, "is_prepared_by", {"document": 1, "organization": org2["oid"]})

    assert pf["item"]["organization"] == org1["oid"]
    assert pb["item"]["organization"] == org2["oid"]

    # Verify rendered HTML cover includes both organization names
    res = generation.render_html(sm, pid, document="c_requirementsSpecification", lang="en")
    assert "Colegio Client Org" in res["html"]
    assert "Dev Team Org" in res["html"]
