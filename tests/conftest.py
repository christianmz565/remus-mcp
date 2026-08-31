import pathlib


def find_base(template="english"):
    name = f"remus_base_empty_{template}.rem"
    base_file = pathlib.Path(__file__).parent.parent / "base" / name
    if base_file.exists():
        return base_file
    raise FileNotFoundError(f"Base template not found: {base_file}")


def find_doc():
    doc_file = pathlib.Path(__file__).parent / "fixtures" / "remus_doc.rem"
    if doc_file.exists():
        return doc_file
    return None
