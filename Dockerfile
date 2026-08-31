# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app/mcp

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Runner
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    WINEPREFIX=/opt/wine \
    WINEARCH=win32 \
    JAVA_HOME=/usr/lib/jvm/default-java \
    REMUS_DTD_PATH=/app/mcp/xml/remus.dtd \
    PATH="/app/mcp/.venv/bin:$PATH"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    openjdk-17-jre-headless \
    wine \
    xvfb \
    xauth \
    curl \
    ca-certificates \
    wkhtmltopdf \
    cabextract \
    unzip \
    p7zip-full \
    && curl -fsSL -o /usr/local/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks \
    && chmod +x /usr/local/bin/winetricks \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/doc/* /usr/share/man/* /usr/share/locale/*

RUN useradd -m -u 1000 remus && \
    mkdir -p /data /opt/wine /app/mcp && \
    chown -R remus:remus /data /opt/wine /app/mcp
RUN su remus -s /bin/sh -c "WINEPREFIX=/opt/wine WINEARCH=win32 xvfb-run -a wineboot --init" || true && \
    chown -R remus:remus /opt/wine

COPY --from=builder --chown=remus:remus /app/mcp /app/mcp

RUN printf '#!/bin/sh\nif [ "$1" = "run" ]; then\n  shift\nfi\nif [ $# -eq 0 ]; then\n  echo "uv shim: no command provided" >&2\n  exit 1\nfi\nexec "$@"\n' > /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER remus

EXPOSE 3000
WORKDIR /app/mcp

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["remus-mcp", "--http", "--host", "0.0.0.0", "--port", "3000"]
