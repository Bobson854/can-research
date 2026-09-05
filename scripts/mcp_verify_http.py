#!/usr/bin/env python3
"""Verify streamable-http MCP endpoint: initialize session and list tools."""

from __future__ import annotations

import argparse
import asyncio

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from canresearch.mcp.server import (
    LIVE_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    SIGNAL_RESEARCH_TOOL_NAMES,
    list_tool_names,
)


async def _verify(url: str) -> int:
    expected = sorted(list_tool_names())
    async with (
        streamable_http_client(url) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = sorted(tool.name for tool in tools.tools)

    print(f"url: {url}")
    print(f"tool_count: {len(names)}")
    print(f"read_only: {len([n for n in names if n in READ_ONLY_TOOL_NAMES])}")
    print(f"live: {len([n for n in names if n in LIVE_TOOL_NAMES])}")
    print(f"signal_research: {len([n for n in names if n in SIGNAL_RESEARCH_TOOL_NAMES])}")

    if names != expected:
        missing = sorted(set(expected) - set(names))
        extra = sorted(set(names) - set(expected))
        print("match: False")
        if missing:
            print("missing:", ", ".join(missing))
        if extra:
            print("extra:", ", ".join(extra))
        return 1

    print("match: True")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8765/mcp",
        help="Streamable HTTP MCP endpoint (default: %(default)s)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_verify(args.url)))


if __name__ == "__main__":
    main()
