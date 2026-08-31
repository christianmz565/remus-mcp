"""Prompts registry."""

def register_prompts(server, session_manager):
    # Provide list_prompts impl
    def list_prompts_impl():
        return [
            {"name": "create-requirement", "description": "Guide to create a requirement", "arguments": [{"name": "project_id", "required": True}, {"name": "type", "required": True}, {"name": "parent_section", "required": False}]},
            {"name": "analyze-traces", "description": "Analyze trace coverage", "arguments": [{"name": "project_id", "required": True}, {"name": "source_type", "required": True}, {"name": "target_type", "required": True}]},
            {"name": "generate-documentation", "description": "Generate HTML/PDF", "arguments": [{"name": "project_id", "required": True}, {"name": "document", "required": True}, {"name": "lang", "required": False}]},
            {"name": "bulk-import", "description": "Bulk import XML", "arguments": [{"name": "project_id", "required": True}, {"name": "xml_path", "required": True}, {"name": "strategy", "required": False}]},
        ]

    def get_prompt_impl(name: str, arguments: dict):
        if name == "create-requirement":
            pid = arguments.get("project_id", "<project_id>")
            typ = arguments.get("type", "<type>")
            parent = arguments.get("parent_section", "")
            text = f"""You are to create a requirement of type {typ} in project {pid}.
Steps:
1. Gather name, description, importance, urgency, status, stability as needed.
2. Call rem_create with project_id={pid}, type={typ}, data={{name, description, ...}}.
3. If parent_section {parent} provided, include parent: <section oid>.
4. Validate with validate_project.
Return the created oid."""
            return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        elif name == "analyze-traces":
            pid = arguments.get("project_id")
            src = arguments.get("source_type")
            tgt = arguments.get("target_type")
            text = f"""Analyze traces from {src} to {tgt} in {pid}:
1. Call trace_matrix(project_id={pid}, source_type={src}, target_type={tgt})
2. Call validate_project(project_id={pid})
3. Summarize coverage gaps (rows with 0 true, columns with 0 true) and dangling traces."""
            return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        elif name == "generate-documentation":
            pid = arguments.get("project_id")
            doc = arguments.get("document")
            lang = arguments.get("lang", "en")
            text = f"""Generate documentation for {doc} ({lang}) in {pid}:
1. Call render_html(project_id={pid}, document={doc}, lang={lang})
2. Return the html path and preview."""
            return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        elif name == "bulk-import":
            pid = arguments.get("project_id")
            path = arguments.get("xml_path")
            strat = arguments.get("strategy", "merge")
            text = f"""Bulk import XML into {pid} from {path} strategy {strat}:
1. Call import_xml(project_id={pid}, file_path={path}, strategy={strat}, dry_run=true)
2. Review imported/updated counts and errors.
3. If ok, call again with dry_run=false."""
            return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        else:
            raise ValueError(f"Unknown prompt {name}")

    return list_prompts_impl, get_prompt_impl
