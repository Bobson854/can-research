"""MCP server exposing sessions, references, and DBC operations to AI clients."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def create_server() -> MCPServer:
    """Build the can-research MCP server with registered tools."""
    server = MCPServer("can-research")

    @server.tool(description="List stored CAN capture sessions.")
    def session_list() -> str:
        return "Session listing is not yet implemented."

    @server.tool(description="Look up a PGN in the local reference catalogue.")
    def reference_lookup_pgn(pgn: int) -> str:
        return f"PGN {pgn} lookup is not yet implemented."

    return server


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the MCP server.

    V1 scaffold uses stdio transport (typical for MCP desktop integration).
    Host/port are reserved for a future SSE/HTTP transport.
    """
    _ = host, port
    create_server().run(transport="stdio")
