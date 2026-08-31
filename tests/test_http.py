"""Tests for MCP HTTP transport (Streamable HTTP / SSE)."""

from starlette.testclient import TestClient

from remus_mcp.server import create_server
from remus_mcp.session import SessionManager
from remus_mcp.transports.http import create_app


def test_health_endpoint():
    sm = SessionManager()
    server = create_server(sm)
    app = create_app(server)
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "service": "remus-mcp"}


def test_auth_unauthorized():
    sm = SessionManager()
    server = create_server(sm)
    app = create_app(server, auth_token="test-secret")
    with TestClient(app) as client:
        # Request without Auth header
        res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert res.status_code == 401
        assert res.json() == {"error": "UNAUTHORIZED"}

        # Request with wrong token
        res_wrong = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert res_wrong.status_code == 401
        assert res_wrong.json() == {"error": "UNAUTHORIZED"}


def test_mcp_initialize_session():
    sm = SessionManager()
    server = create_server(sm)
    app = create_app(server, auth_token="test-secret")
    with TestClient(app) as client:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        res = client.post(
            "/mcp",
            json=init_payload,
            headers={
                "Authorization": "Bearer test-secret",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert res.status_code == 200
        session_id = res.headers.get("mcp-session-id")
        assert session_id is not None and len(session_id) > 0
        assert "serverInfo" in res.text
        assert '"name":"remus-mcp"' in res.text or '"name": "remus-mcp"' in res.text


def test_mcp_jsonrpc_flow():
    sm = SessionManager()
    server = create_server(sm)
    app = create_app(server, auth_token="test-secret")
    with TestClient(app) as client:
        # 1. Initialize session
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        res = client.post(
            "/mcp",
            json=init_payload,
            headers={
                "Authorization": "Bearer test-secret",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert res.status_code == 200
        session_id = res.headers.get("mcp-session-id")
        assert session_id is not None

        headers = {
            "Authorization": "Bearer test-secret",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
        }

        # 2. Send initialized notification
        res_notif = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )
        assert res_notif.status_code in (200, 202)

        # 3. List tools
        res_tools = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
        assert res_tools.status_code == 200
        assert "open_project" in res_tools.text

        # 4. List prompts
        res_prompts = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "prompts/list"},
            headers=headers,
        )
        assert res_prompts.status_code == 200
        assert "create-requirement" in res_prompts.text

        # 5. List resources
        res_resources = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
            headers=headers,
        )
        assert res_resources.status_code == 200
        assert "resources" in res_resources.text


def test_unauthenticated_app():
    sm = SessionManager()
    server = create_server(sm)
    app = create_app(server, auth_token=None)
    with TestClient(app) as client:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        res = client.post(
            "/mcp",
            json=init_payload,
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert res.status_code == 200
        assert "mcp-session-id" in res.headers
