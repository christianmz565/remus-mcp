#!/bin/bash
set -e

# Ensure WINEPREFIX points to a directory owned by the current running user
if [ -z "$WINEPREFIX" ] || [ ! -d "$WINEPREFIX" ] || [ "$(stat -c '%u' "$WINEPREFIX" 2>/dev/null)" != "$(id -u)" ]; then
  export WINEPREFIX="/tmp/wine-$(id -u)"
fi
mkdir -p "$WINEPREFIX"

# Lazy Wine prefix init for msxml3 (used by render_html). No network at build time
# is okay — fallback to lxml is supported and warning is returned to MCP client.
if [ ! -f "$WINEPREFIX/drive_c/windows/system32/msxml3.dll" ]; then
  echo "[remus-mcp] Wine prefix not initialized at $WINEPREFIX, initializing..." >&2
  # wineboot needs a display; xvfb-run provides :99
  if command -v xvfb-run >/dev/null 2>&1; then
    xvfb-run -a wineboot --init >/dev/null 2>&1 || true
    # try msxml3 via winetricks only if network available; ignore failure
    timeout 120 xvfb-run -a winetricks -q msxml3 >/dev/null 2>&1 || echo "[remus-mcp] winetricks msxml3 failed (offline or timeout) — will use lxml fallback" >&2
  else
    wineboot --init >/dev/null 2>&1 || true
  fi
  # verify
  if [ -f "$WINEPREFIX/drive_c/windows/system32/msxml3.dll" ]; then
    echo "[remus-mcp] Wine msxml3 ready" >&2
  else
    echo "[remus-mcp] Wine msxml3 not available — render_html will use lxml fallback" >&2
  fi
fi
exec "$@"
