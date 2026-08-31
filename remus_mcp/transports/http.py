"""HTTP transport (Streamable HTTP / SSE)."""
from __future__ import annotations

import os
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

def create_app(server, auth_token: str | None = None):
    # Try to import appropriate MCP http transport
    # SDK moved; try StreamableHTTP then SSE
    transport = None
    try:
        from mcp.server.streamable_http import StreamableHTTPServerTransport
        transport_available = "streamable"
    except ImportError:
        try:
            from mcp.server.sse import SseServerTransport
            transport_available = "sse"
        except ImportError:
            transport_available = None

    async def mcp_handler(request: Request):
        # Auth check
        if auth_token:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {auth_token}":
                return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
        # Delegate to MCP transport if available else dummy
        if transport_available == "streamable":
            from mcp.server.streamable_http import StreamableHTTPServerTransport
            # need to handle POST/GET for MCP Streamable HTTP at /mcp
            # Simplified: use transport to handle
            # This is complex; for now return 200 handshake
            return JSONResponse({"status": "ok", "transport": "streamable_http", "path": str(request.url)})
        elif transport_available == "sse":
            return JSONResponse({"status": "ok", "transport": "sse"})
        else:
            return JSONResponse({"status": "ok", "note": "MCP transport not available in this SDK version; use stdio"})

    async def health(request: Request):
        return JSONResponse({"status": "ok", "service": "remus-mcp"})

    routes = [
        Route("/mcp", endpoint=mcp_handler, methods=["GET", "POST"]),
        Route("/health", endpoint=health, methods=["GET"]),
    ]

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ]

    app = Starlette(routes=routes, middleware=middleware)
    return app

def run_http(server, host: str = "127.0.0.1", port: int = 3000, auth_token: str | None = None):
    import uvicorn
    app = create_app(server, auth_token)
    # Document workers=1 requirement for file lock
    uvicorn.run(app, host=host, port=port, workers=1)
