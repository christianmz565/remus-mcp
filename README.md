# remus-mcp

MCP server for REMUS Jet databases — stdio + Streamable HTTP/SSE, 100% Jet-compatible (mdbtools + Jackcess fallback).

## Quick start (native)

```sh
cd mcp && uv sync
uv run remus-mcp --rem ../base/remus_base_empty_english.rem        # stdio (Claude Desktop)
uv run remus-mcp --http --port 3000 --auth-token secret            # HTTP  http://127.0.0.1:3000/mcp
curl -H "Authorization: Bearer secret" http://127.0.0.1:3000/health
```

## Docker

### Images / compose

- `Dockerfile` at repo root (and `mcp/Dockerfile` — same content, repo-root context):
  `python:3.11-slim-bookworm` + `mdbtools + default-jre-headless + wine64 + winetricks + xvfb + wkhtmltopdf` + `uv`.
  Bakes `mcp/`, `xml/remus.dtd`, `xslt/`, `base/*.rem`, `jars/`, `assets/transform.vbs`.
  Wine prefix at `/opt/wine` (`WINEARCH=win32`) lazy-initializes at container start (`docker-entrypoint.sh` → `xvfb-run wineboot` + `winetricks -q msxml3`, falls back to lxml if offline).
  Containers run as the host user (`user: "${UID:-1000}:${GID:-1000}"` in compose) so files written to `/data` remain owned by the user, enabling direct editing with the original desktop app.

- `docker-compose.yml` (repo root) — two services, one image, different transports:

  | Service | Transport | How to run | Port | Auth |
  |---------|-----------|------------|------|------|
  | `remus-mcp-stdio` | **stdio** (local) | `docker compose run --rm remus-mcp-stdio` (attaches stdin) | — | no auth |
  | `remus-mcp-http` | **Streamable HTTP** (remote, SSE fallback via SDK) | `docker compose up remus-mcp-http` | `3000:3000` (`${REMUS_HTTP_PORT:-3000}`) | `Bearer ${MCP_AUTH_TOKEN:-secret}` |
  | `remus-mcp-sse` | alias to http | `docker compose --profile sse up remus-mcp-sse` | 3000 | same |
```sh
# Build & run HTTP (recommended for Inspector / remote agents)
docker compose up --build remus-mcp-http
curl -H "Authorization: Bearer secret" http://127.0.0.1:3000/health      # {"status":"ok"}
curl -H "Authorization: Bearer secret" http://127.0.0.1:3000/mcp | head  # MCP handshake
curl http://127.0.0.1:3000/mcp | head                                   # 401 {"error":"UNAUTHORIZED"} (when token set)

# stdio — attaches your terminal's stdin to the MCP stdio transport
mkdir -p data && cp base/remus_base_empty_english.rem data/project.rem
docker compose run --rm remus-mcp-stdio
# or manual:
docker build -t remus-mcp .                         # from repo root
docker run --rm -i --user $(id -u):$(id -g) -v ./data:/data remus-mcp uv run remus-mcp --rem /data/project.rem
# or from mcp/  (repo-root context required):
docker build -f mcp/Dockerfile -t remus-mcp .
```

Data mounts: `./data:/data` (your `.rem` files), `./base:/app/base:ro` etc. are optional — the image already bakes `base/` for `project_create`.

### Claude Desktop

stdio via docker:
```json
{"mcpServers":{"remus":{"command":"docker","args":["run","--rm","-i","--user","1000:1000","-v","/abs/path/to/data:/data","remus-mcp","uv","run","remus-mcp","--rem","/data/project.rem"]}}}
```
HTTP (remote):
```json
{"mcpServers":{"remus-http":{"url":"http://127.0.0.1:3000/mcp","headers":{"Authorization":"Bearer secret"}}}}
```
SSE alias is identical (SDK negotiates streamable_http → SSE fallback automatically).

### mcp/ compose (from mcp dir)

```sh
cd mcp && docker compose up --build remus-mcp-http   # uses context: .. dockerfile: mcp/Dockerfile
```

