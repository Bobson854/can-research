"""MCP server module import tests."""

from canresearch.mcp.server import create_server, serve


def test_mcp_server_imports() -> None:
    server = create_server()
    assert server.name == "can-research"


def test_mcp_serve_is_callable() -> None:
    assert callable(serve)
