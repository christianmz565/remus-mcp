"""HTTP transport (Streamable HTTP / SSE)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class StreamableMCPApp:
    """ASGI application wrapper that routes /mcp requests to StreamableHTTPSessionManager
    and delegates all other routes/lifespan events to Starlette.
    """

    def __init__(self, session_manager: Any, starlette_app: Starlette, auth_token: str | None = None):
        self.session_manager = session_manager
        self.starlette_app = starlette_app
        self.auth_token = auth_token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path in ("/mcp", "/mcp/") or path.startswith("/mcp/"):
                if self.auth_token:
                    auth_header = None
                    for raw_name, raw_value in scope.get("headers", []):
                        if raw_name.lower() == b"authorization":
                            auth_header = raw_value.decode("utf-8")
                            break
                    if auth_header != f"Bearer {self.auth_token}":
                        response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
                        await response(scope, receive, send)
                        return
                await self.session_manager.handle_request(scope, receive, send)
                return
        await self.starlette_app(scope, receive, send)


def create_app(server: Any, auth_token: str | None = None) -> Any:
    # Try to import appropriate MCP http transport
    try:
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        transport_available = "streamable"
    except ImportError:
        try:
            from mcp.server.sse import SseServerTransport

            transport_available = "sse"
        except ImportError:
            transport_available = None

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "remus-mcp"})

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ]

    if transport_available == "streamable":
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        session_manager = StreamableHTTPSessionManager(server)

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with session_manager.run():
                yield

        starlette_app = Starlette(
            routes=[Route("/health", endpoint=health, methods=["GET"])],
            middleware=middleware,
            lifespan=lifespan,
        )

        return StreamableMCPApp(session_manager, starlette_app, auth_token=auth_token)

    elif transport_available == "sse":
        from mcp.server.sse import SseServerTransport

        sse_transport = SseServerTransport("/messages")

        async def handle_sse(request: Request):
            if auth_token:
                auth = request.headers.get("authorization", "")
                if auth != f"Bearer {auth_token}":
                    return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            async with sse_transport.connect_sse(
                request.scope, request._receive, request._send
            ) as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        async def handle_messages(request: Request):
            if auth_token:
                auth = request.headers.get("authorization", "")
                if auth != f"Bearer {auth_token}":
                    return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            await sse_transport.handle_post_message(request.scope, request._receive, request._send)

        routes = [
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/health", endpoint=health, methods=["GET"]),
        ]
        return Starlette(routes=routes, middleware=middleware)

    else:
        async def unavailable(request: Request) -> JSONResponse:
            return JSONResponse(
                {"status": "ok", "note": "MCP transport not available in this SDK version; use stdio"}
            )

        routes = [
            Route("/mcp", endpoint=unavailable, methods=["GET", "POST"]),
            Route("/health", endpoint=health, methods=["GET"]),
        ]
        return Starlette(routes=routes, middleware=middleware)


def run_http(server: Any, host: str = "127.0.0.1", port: int = 3000, auth_token: str | None = None) -> None:
    import uvicorn

    app = create_app(server, auth_token)
    # Document workers=1 requirement for file lock
    uvicorn.run(app, host=host, port=port, workers=1)
