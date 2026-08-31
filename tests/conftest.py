import pathlib

def find_base(template="english"):
    name = f"remus_base_empty_{template}.rem"
    candidates = [
        pathlib.Path(__file__).parent.parent / "base" / name,  # mcp/base (standalone vendored)
        pathlib.Path(__file__).parents[2] / "base" / name,      # monorepo base/ from mcp/tests -> repo/base
        pathlib.Path("base") / name,
        pathlib.Path("mcp/base") / name,
        pathlib.Path("/app/base") / name,
        pathlib.Path("/app/mcp/base") / name,
        pathlib.Path("/home/cricro/tiny-projects/remus/base") / name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Base template not found: {name} (tried {candidates})")

def find_doc():
    candidates = [
        pathlib.Path(__file__).parent / "fixtures" / "remus_doc.rem",
        pathlib.Path(__file__).parent.parent / "doc" / "remus_doc.rem",  # not expected in standalone
        pathlib.Path("doc/remus_doc.rem"),
        pathlib.Path("/home/cricro/tiny-projects/remus/doc/remus_doc.rem"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
