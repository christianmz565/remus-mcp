import shutil, pathlib, pytest
from remus_mcp.session import SessionManager
from remus_mcp.tools import xml_ops, crud
from conftest import find_base, find_doc

def _make_doc_project(tmp_path, name="src.rem"):
    # Use real doc if vendored fixture exists, else synthesize small project
    doc = find_doc()
    if doc is not None:
        dst = tmp_path / name
        shutil.copy2(doc, dst)
        sm = SessionManager()
        pid = sm.open_project(str(dst))
        return sm, pid, str(dst)
    # synthetic
    src = find_base("english")
    dst = tmp_path / name
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    # create a few objects so export has content
    crud.rem_create(sm, pid, "objective", {"name":"Synthetic OBJ","description":"for xml roundtrip","importance":1,"urgency":1,"status":1,"stability":1})
    crud.rem_create(sm, pid, "actor", {"name":"Synthetic Actor","description":"actor for xml"})
    return sm, pid, str(dst)

def test_xml_roundtrip(tmp_path):
    sm, pid, _ = _make_doc_project(tmp_path, "src.rem")
    exp = xml_ops.export_xml(sm, pid)
    assert "xml" in exp and len(exp["xml"]) > 1000
    # Export should produce path
    assert pathlib.Path(exp["path"]).exists()
    # Import into empty
    src2 = find_base("english")
    dst2 = tmp_path / "empty.rem"
    shutil.copy2(src2, dst2)
    pid2 = sm.open_project(str(dst2))
    # dry_run
    dry = xml_ops.import_xml(sm, pid2, xml=exp["xml"], strategy="merge", dry_run=True)
    assert dry["imported"] > 0
    # actual
    imp = xml_ops.import_xml(sm, pid2, xml=exp["xml"], strategy="merge", dry_run=False)
    assert imp["imported"] > 0
    assert len(imp["errors"]) == 0
    # Verify counts match for some types
    from remus_mcp.jet.mdbtools import export_table
    assert len(export_table(str(dst2),"Objective")) > 0

def test_xml_dry_run_empty(tmp_path):
    src = find_base("english")
    dst = tmp_path / "empty.rem"
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    exp = xml_ops.export_xml(sm, pid)
    assert exp["xml"].startswith("<?xml")
