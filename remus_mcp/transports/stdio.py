"""Stdio transport."""
from __future__ import annotations

import asyncio

async def run_stdio(server):
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
