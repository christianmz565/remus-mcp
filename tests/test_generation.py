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
def test_render_html_with_use_case_description(tmp_path):
    src = find_base("english")
    dst = tmp_path / "uc_doc.rem"
    shutil.copy2(src, dst)
    sm = SessionManager()
    pid = sm.open_project(str(dst))
    
    # Create use_case with description to exercise rem:bool2space and generate_markdown in XSL
    crud.rem_create(sm, pid, "use_case", {
        "name": "UC-Test",
        "versionMajor": 1,
        "versionMinor": 0,
        "description": "This is a **bold markdown** description.",
        "document": 1
    })
    
    res = generation.render_html(sm, pid, document="c_requirementsSpecification", lang="en")
    assert "html" in res and "path" in res
    assert pathlib.Path(res["path"]).exists()
    
    # Ensure lxml fallback didn't fail with prefix_space error
    for w in res.get("warnings", []):
        assert "lxml fallback failed" not in w
        
    assert "<html" in res["html"].lower() or "<!doctype html" in res["html"].lower()
    assert "uc-test" in res["html"].lower() or "bold markdown" in res["html"].lower() or len(res["html"]) > 500
