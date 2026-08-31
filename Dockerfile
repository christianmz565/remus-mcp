# REMUS MCP — Dockerfile (standalone, context = mcp/)
# Build from mcp:        docker build -t remus-mcp mcp
# Build from repo root:  docker build -f mcp/Dockerfile -t remus-mcp mcp
# GH workflow uses the root Dockerfile (context .) for monorepo; this one is for publishing mcp/ as its own repo.
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    default-jre-headless \
    wine64 \
    xvfb \
    curl \
    ca-certificates \
    wkhtmltopdf \
    cabextract \
    unzip \
    p7zip-full \
  && curl -fsSL -o /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks \
  && chmod +x /usr/local/bin/winetricks \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_SYSTEM_PYTHON=1 \
    PYTHONUNBUFFERED=1 \
    WINEPREFIX=/opt/wine \
    WINEARCH=win32 \
    JAVA_HOME=/usr/lib/jvm/default-java \
    REMUS_DTD_PATH=/app/mcp/xml/remus.dtd

WORKDIR /app/mcp

# deps layer — context is mcp/ (cache deps without project build)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# source + vendored assets (xml/xslt/base already inside mcp/ if vendored)
COPY . ./
RUN uv sync --frozen --no-dev

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN useradd -m -u 1000 remus && \
    mkdir -p /data /opt/wine && chown -R remus:remus /app /opt/wine /data
USER remus

EXPOSE 3000

WORKDIR /app/mcp
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "remus-mcp", "--http", "--host", "0.0.0.0", "--port", "3000"]
