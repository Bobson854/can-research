"""MCP server exposing read-only CAN Research session tools to AI clients."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer

from canresearch.mcp import handlers
from canresearch.mcp.errors import McpToolError


@dataclass(frozen=True, slots=True)
class _ToolBinding:
    name: str
    description: str
    handler: Callable[..., dict[str, Any]]


def _invoke(handler: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    try:
        return handler(**kwargs)
    except McpToolError as exc:
        return exc.to_dict()


TOOL_BINDINGS: tuple[_ToolBinding, ...] = (
    _ToolBinding(
        name="list_sessions",
        description=(
            "List stored CAN capture sessions (metadata only). "
            "Use this first to discover session IDs. Does not return raw frames."
        ),
        handler=handlers.handle_list_sessions,
    ),
    _ToolBinding(
        name="get_session",
        description=(
            "Return metadata and linked assets for one stored session. "
            "Does not return raw frame payloads."
        ),
        handler=handlers.handle_get_session,
    ),
    _ToolBinding(
        name="analyze_session",
        description=(
            "Summarize a stored CAN session at frame/PGN/transport/node level. "
            "Use before decode or PGN-specific investigation. "
            "Observed traffic rows are bounded; no raw frame payloads."
        ),
        handler=handlers.handle_analyze_session,
    ),
    _ToolBinding(
        name="decode_session",
        description=(
            "Decode reference-backed J1939 SPN engineering values from a stored session. "
            "Supports optional PGN/SPN/source-address filters and a row limit."
        ),
        handler=handlers.handle_decode_session,
    ),
    _ToolBinding(
        name="inspect_transport",
        description=(
            "Inspect J1939 transport-protocol (BAM/RTS-CTS) reassembly for a stored session. "
            "Payload bytes are omitted unless show_payload=true."
        ),
        handler=handlers.handle_inspect_transport,
    ),
    _ToolBinding(
        name="list_session_nodes",
        description=(
            "List J1939 Address Claim node identities observed in a session, "
            "including NAME fields and optional asset links."
        ),
        handler=handlers.handle_list_session_nodes,
    ),
    _ToolBinding(
        name="list_assets",
        description="List registered tractor/implement/controller assets (read-only).",
        handler=handlers.handle_list_assets,
    ),
    _ToolBinding(
        name="get_asset",
        description=(
            "Return asset metadata, linked J1939 NAMEs, and sessions associated with an asset."
        ),
        handler=handlers.handle_get_asset,
    ),
    _ToolBinding(
        name="list_asset_nodes",
        description="List J1939 NAME identities linked to an asset (read-only).",
        handler=handlers.handle_list_asset_nodes,
    ),
    _ToolBinding(
        name="lookup_pgn",
        description=(
            "Look up a PGN in the local reference catalogue, including known SPN mappings."
        ),
        handler=handlers.handle_lookup_pgn,
    ),
    _ToolBinding(
        name="lookup_spn",
        description=(
            "Look up an SPN in the local reference catalogue across origins and PGN mappings."
        ),
        handler=handlers.handle_lookup_spn,
    ),
    _ToolBinding(
        name="build_session_dbc_preview",
        description=(
            "Build an in-memory asset-specific DBC preview from a stored session. "
            "Does not write files or persist DBC revisions. "
            "Uses automatic source-address resolution from linked J1939 nodes when "
            "source_addresses are omitted."
        ),
        handler=handlers.handle_build_session_dbc_preview,
    ),
)

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(binding.name for binding in TOOL_BINDINGS)


def list_tool_names() -> list[str]:
    """Return registered read-only MCP tool names."""
    return [binding.name for binding in TOOL_BINDINGS]


def create_server() -> MCPServer:
    """Build the can-research MCP server with read-only tools registered."""
    server = MCPServer(
        "can-research",
        instructions=(
            "Read-only CAN Research tools for stored capture sessions, J1939 reference "
            "lookups, transport inspection, node identity, and DBC preview. "
            "Suggested flow: list_sessions → get_session → analyze_session → "
            "list_session_nodes → lookup_pgn/lookup_spn → decode_session → "
            "inspect_transport → get_asset/list_asset_nodes → build_session_dbc_preview."
        ),
    )

    @server.tool(description=TOOL_BINDINGS[0].description)
    def list_sessions(limit: int | None = None) -> dict[str, Any]:
        return _invoke(handlers.handle_list_sessions, limit=limit)

    @server.tool(description=TOOL_BINDINGS[1].description)
    def get_session(session_id: str) -> dict[str, Any]:
        return _invoke(handlers.handle_get_session, session_id=session_id)

    @server.tool(description=TOOL_BINDINGS[2].description)
    def analyze_session(
        session_id: str,
        pgn: int | None = None,
        source_address: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_analyze_session,
            session_id=session_id,
            pgn=pgn,
            source_address=source_address,
            limit=limit,
        )

    @server.tool(description=TOOL_BINDINGS[3].description)
    def decode_session(
        session_id: str,
        pgn: int | None = None,
        spn: int | None = None,
        source_address: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_decode_session,
            session_id=session_id,
            pgn=pgn,
            spn=spn,
            source_address=source_address,
            limit=limit,
        )

    @server.tool(description=TOOL_BINDINGS[4].description)
    def inspect_transport(
        session_id: str,
        pgn: int | None = None,
        source_address: int | None = None,
        show_payload: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_inspect_transport,
            session_id=session_id,
            pgn=pgn,
            source_address=source_address,
            show_payload=show_payload,
            limit=limit,
        )

    @server.tool(description=TOOL_BINDINGS[5].description)
    def list_session_nodes(
        session_id: str,
        source_address: int | None = None,
        manufacturer_code: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_list_session_nodes,
            session_id=session_id,
            source_address=source_address,
            manufacturer_code=manufacturer_code,
        )

    @server.tool(description=TOOL_BINDINGS[6].description)
    def list_assets(limit: int | None = None) -> dict[str, Any]:
        return _invoke(handlers.handle_list_assets, limit=limit)

    @server.tool(description=TOOL_BINDINGS[7].description)
    def get_asset(asset_key: str) -> dict[str, Any]:
        return _invoke(handlers.handle_get_asset, asset_key=asset_key)

    @server.tool(description=TOOL_BINDINGS[8].description)
    def list_asset_nodes(asset_key: str) -> dict[str, Any]:
        return _invoke(handlers.handle_list_asset_nodes, asset_key=asset_key)

    @server.tool(description=TOOL_BINDINGS[9].description)
    def lookup_pgn(pgn: int) -> dict[str, Any]:
        return _invoke(handlers.handle_lookup_pgn, pgn=pgn)

    @server.tool(description=TOOL_BINDINGS[10].description)
    def lookup_spn(spn: int) -> dict[str, Any]:
        return _invoke(handlers.handle_lookup_spn, spn=spn)

    @server.tool(description=TOOL_BINDINGS[11].description)
    def build_session_dbc_preview(
        session_id: str,
        asset_key: str,
        source_addresses: list[int] | None = None,
        preview_lines: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_build_session_dbc_preview,
            session_id=session_id,
            asset_key=asset_key,
            source_addresses=source_addresses,
            preview_lines=preview_lines,
        )

    return server


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the MCP server (stdio transport for desktop MCP clients)."""
    _ = host, port
    create_server().run(transport="stdio")
