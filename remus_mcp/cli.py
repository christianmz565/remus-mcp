"""CLI entry point."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import typer

from .config import DEFAULT_HTTP_HOST, DEFAULT_HTTP_PORT, ENV_AUTH_TOKEN, ENV_WINEPREFIX
from .session import SessionManager

app = typer.Typer(add_completion=False)

@app.command()
def main(
    rem: str = typer.Option(None, "--rem", help="Default .rem to open on startup"),
    http: bool = typer.Option(False, "--http", help="Start Streamable HTTP server instead of stdio"),
    port: int = typer.Option(DEFAULT_HTTP_PORT, "--port", help="HTTP port"),
    host: str = typer.Option(DEFAULT_HTTP_HOST, "--host", help="HTTP host"),
    auth_token: str = typer.Option(None, "--auth-token", envvar=ENV_AUTH_TOKEN, help="Bearer token for HTTP"),
    wine_prefix: str = typer.Option(None, "--wine-prefix", envvar=ENV_WINEPREFIX, help="Wine prefix"),
):
    if wine_prefix:
        os.environ["WINEPREFIX"] = wine_prefix
    session_manager = SessionManager()
    if rem:
        try:
            pid = session_manager.open_project(rem)
            typer.echo(f"Opened project {pid} at {rem}", err=True)
        except Exception as e:
            typer.echo(f"Failed to open {rem}: {e}", err=True)
            sys.exit(1)
    server = create_server(session_manager)
    if http:
        from .transports.http import run_http
        typer.echo(f"Starting HTTP server on {host}:{port} auth={'enabled' if auth_token else 'disabled'}", err=True)
        run_http(server, host=host, port=port, auth_token=auth_token)
    else:
        from .transports.stdio import run_stdio
        import asyncio
        asyncio.run(run_stdio(server))

if __name__ == "__main__":
    app()
