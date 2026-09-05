"""MCP server module import tests."""

import asyncio

from canresearch.mcp.server import READ_ONLY_TOOL_NAMES, create_server, list_tool_names, serve


def test_mcp_server_imports() -> None:
    server = create_server()
    assert server.name == "can-research"


def test_mcp_serve_is_callable() -> None:
    assert callable(serve)


def test_read_only_tool_registry() -> None:
    assert len(list_tool_names()) == 12
    assert "analyze_session" in READ_ONLY_TOOL_NAMES
    assert "build_session_dbc_preview" in READ_ONLY_TOOL_NAMES


def test_server_exposes_registered_tools() -> None:
    server = create_server()

    async def _names() -> set[str]:
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    assert asyncio.run(_names()) == set(list_tool_names())
