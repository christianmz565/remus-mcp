import shutil, pathlib, pytest
from remus_mcp.session import SessionManager
from remus_mcp.tools import generation, crud
from conftest import find_base, find_doc

def test_render_html(tmp_path):
    doc = find_doc()
    if doc is not None:
        src = doc
    else:
        src = find_base("english")
    dst = tmp_path / "doc.rem"
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    if doc is None:
        # synthesize content so HTML is non-empty
        crud.rem_create(sm, pid, "objective", {"name":"Synthetic OBJ","description":"for html render","importance":1,"urgency":1,"status":1,"stability":1})
    res = generation.render_html(sm, pid, document="c_requirementsSpecification", lang="en")
    assert "html" in res and "path" in res
    assert pathlib.Path(res["path"]).exists()
    assert "<!doctype html>" in res["html"].lower() or "<html" in res["html"].lower()
    # Should contain project name or title
    assert "test" in res["html"].lower() or "remus" in res["html"].lower() or len(res["html"]) > 100
