"""Centralized configuration module for remus-mcp."""

import os
from pathlib import Path

# Numerical & Operational Constants
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_NAME_LENGTH = 255
DEFAULT_HTTP_PORT = 3000
DEFAULT_HTTP_HOST = "127.0.0.1"
LOCK_TIMEOUT_SECONDS = 5.0
SUBPROCESS_TIMEOUT_SECONDS = 30.0
PREVIEW_XML_LENGTH = 2000
PREVIEW_HTML_LENGTH = 5000
MCP_RESPONSE_MAX_HTML = 100000

# Environment Variable Names
ENV_WINEPREFIX = "WINEPREFIX"
ENV_DTD_PATH = "REMUS_DTD_PATH"
ENV_JARS_DIR = "REMUS_JARS_DIR"
ENV_AUTH_TOKEN = "MCP_AUTH_TOKEN"
ENV_BASE_DIR = "REMUS_BASE_DIR"
ENV_XSL_DIR = "REMUS_XSL_DIR"
ENV_DATA_DIR = "REMUS_DATA_DIR"
# Root Paths
PACKAGE_ROOT = Path(__file__).parent.resolve()
REPO_ROOT = PACKAGE_ROOT.parent.resolve()


def get_dtd_path() -> Path:
    """Return deterministic path to remus.dtd."""
    if os.environ.get(ENV_DTD_PATH):
        path = Path(os.environ[ENV_DTD_PATH])
    else:
        path = REPO_ROOT / "xml" / "remus.dtd"
    if not path.exists():
        raise FileNotFoundError(f"DTD file not found: {path}")
    return path


def get_jars_dir() -> Path:
    """Return deterministic path to jars directory."""
    jars_env = os.environ.get(ENV_JARS_DIR) or os.environ.get("JACKCESS_JARS_DIR")
    if jars_env:
        path = Path(jars_env)
    else:
        path = REPO_ROOT / "jars"
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Jars directory not found: {path}")
    return path


def get_base_template_path(template: str) -> Path:
    """Return deterministic path to base template file."""
    template_clean = template.lower().strip()
    filename = f"remus_base_empty_{template_clean}.rem"
    if os.environ.get(ENV_BASE_DIR):
        path = Path(os.environ[ENV_BASE_DIR]) / filename
    else:
        path = REPO_ROOT / "base" / filename
    if not path.exists():
        raise FileNotFoundError(f"Base template not found: {path}")
    return path


def get_xsl_path(lang: str) -> Path:
    """Return deterministic path to language-specific XSL stylesheet."""
    lang_map = {
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "english": "English",
        "spanish": "Spanish",
        "german": "German",
    }
    lang_key = lang.lower().strip()
    if lang_key not in lang_map:
        raise ValueError(f"Invalid or unsupported XSL language: {lang}")
    filename = f"REMUS_{lang_map[lang_key]}.xsl"
    if os.environ.get(ENV_XSL_DIR):
        path = Path(os.environ[ENV_XSL_DIR]) / filename
    else:
        path = REPO_ROOT / "xslt" / "remus" / filename
    if not path.exists():
        raise FileNotFoundError(f"XSL stylesheet not found: {path}")


def get_data_dir() -> Path:
    """Return path to data directory for storing projects."""
    if os.environ.get(ENV_DATA_DIR):
        path = Path(os.environ[ENV_DATA_DIR])
    elif Path("/data").exists() and Path("/data").is_dir():
        path = Path("/data")
    else:
        path = REPO_ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_path(target_path: str) -> Path:
    """Resolve project path: if relative, resolve relative to data directory."""
    path = Path(target_path)
    if not path.is_absolute():
        path = get_data_dir() / path
    return path
    return path
