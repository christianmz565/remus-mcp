"""HTTP Transport for MCP using StreamableHTTPSessionManager."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..config import DEFAULT_HTTP_HOST, DEFAULT_HTTP_PORT


class StreamableMCPApp:
    """ASGI application wrapper that routes /mcp requests to StreamableHTTPSessionManager
    and delegates all other routes/lifespan events to Starlette.
    """

    def __init__(
        self, session_manager: Any, starlette_app: Starlette, auth_token: str | None = None
    ):
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
    session_manager = StreamableHTTPSessionManager(server)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "remus-mcp"})

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ]

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


def run_http(
    server: Any,
    host: str = DEFAULT_HTTP_HOST,
    port: int = DEFAULT_HTTP_PORT,
    auth_token: str | None = None,
) -> None:
    import uvicorn

    app = create_app(server, auth_token)
    # Document workers=1 requirement for file lock
    uvicorn.run(app, host=host, port=port, workers=1)
