"""MCP server exposing CAN Research session and live CANsub tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer

from canresearch.mcp import (
    dbc_handlers,
    handlers,
    live_handlers,
    reference_handlers,
    research_candidate_handlers,
    signal_research_handlers,
)
from canresearch.mcp.errors import McpToolError


@dataclass(frozen=True, slots=True)
class _ToolBinding:
    name: str
    description: str
    handler: Callable[..., dict[str, Any]]
    live: bool = False


def _invoke(handler: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    try:
        return handler(**kwargs)
    except McpToolError as exc:
        return exc.to_dict()


READ_ONLY_TOOL_BINDINGS: tuple[_ToolBinding, ...] = (
    _ToolBinding(
        name="get_instance_info",
        description=(
            "Return this CAN Research installation identity and MCP capability summary. "
            "Use when multiple connectors/backends exist to confirm which backend is active."
        ),
        handler=handlers.handle_get_instance_info,
    ),
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
    _ToolBinding(
        name="list_research_candidates",
        description=(
            "List persisted research signal candidates for an asset (read-only). "
            "Candidates are not confirmed signals — use CLI to review/confirm."
        ),
        handler=research_candidate_handlers.handle_list_research_candidates,
    ),
    _ToolBinding(
        name="get_research_candidate",
        description=(
            "Return one persisted research candidate including review status (read-only)."
        ),
        handler=research_candidate_handlers.handle_get_research_candidate,
    ),
    _ToolBinding(
        name="list_candidate_evidence",
        description=(
            "List append-only evidence rows attached to a research candidate (read-only)."
        ),
        handler=research_candidate_handlers.handle_list_candidate_evidence,
    ),
    _ToolBinding(
        name="preview_research_dbc",
        description=(
            "Preview an in-memory asset research DBC from confirmed candidates only. "
            "Does not write files. Confirmation remains a CLI-only human action."
        ),
        handler=research_candidate_handlers.handle_preview_research_dbc,
    ),
    _ToolBinding(
        name="list_session_events",
        description=(
            "List experiment event markers for a stored session (read-only). "
            "Use to recover baseline/action labels after reconnecting."
        ),
        handler=handlers.handle_list_session_events,
    ),
    _ToolBinding(
        name="preview_candidate_values",
        description=(
            "Preview raw and optional scaled values for a proposed signal field in a "
            "stored session. Analysis only — does not persist or confirm candidates."
        ),
        handler=handlers.handle_preview_candidate_values,
    ),
    _ToolBinding(
        name="list_dbc_sources",
        description=(
            "List registered DBC knowledge sources (read-only). "
            "Optional asset_key includes asset standard/research DBC files when present."
        ),
        handler=dbc_handlers.handle_list_dbc_sources,
    ),
    _ToolBinding(
        name="inspect_dbc",
        description=(
            "Inspect one registered DBC source: messages, signals, counts (read-only). "
            "Bounded output; does not mutate DBC files."
        ),
        handler=dbc_handlers.handle_inspect_dbc,
    ),
    _ToolBinding(
        name="lookup_dbc_message",
        description=(
            "Look up DBC message definitions by CAN ID or message name across registered sources."
        ),
        handler=dbc_handlers.handle_lookup_dbc_message,
    ),
    _ToolBinding(
        name="lookup_dbc_signal",
        description=(
            "Look up DBC signal definitions by signal name or CAN ID across registered sources."
        ),
        handler=dbc_handlers.handle_lookup_dbc_signal,
    ),
    _ToolBinding(
        name="analyze_dbc_coverage",
        description=(
            "Analyze stored session traffic coverage against registered DBC knowledge sources. "
            "Returns covered/partially_covered/unknown IDs and known-first summary."
        ),
        handler=dbc_handlers.handle_analyze_dbc_coverage,
    ),
    _ToolBinding(
        name="list_reference_sources",
        description=(
            "List registered original reference source documents (metadata only, read-only). "
            "Does not expose raw private file contents."
        ),
        handler=reference_handlers.handle_list_reference_sources,
    ),
    _ToolBinding(
        name="inspect_reference_source",
        description=(
            "Inspect one registered reference source: metadata and imported knowledge counts."
        ),
        handler=reference_handlers.handle_inspect_reference_source,
    ),
    _ToolBinding(
        name="search_reference_knowledge",
        description=(
            "Deterministic text search over imported normalized reference knowledge "
            "(messages, signals, families, registers, faults, notes)."
        ),
        handler=reference_handlers.handle_search_reference_knowledge,
    ),
    _ToolBinding(
        name="lookup_reference_message",
        description=(
            "Look up imported reference messages by exact CAN ID or PGN, including "
            "message-family pattern matches."
        ),
        handler=reference_handlers.handle_lookup_reference_message,
    ),
)

LIVE_TOOL_BINDINGS: tuple[_ToolBinding, ...] = (
    _ToolBinding(
        name="get_cansub_device_status",
        description=(
            "Return read-only CANsub.2 device status (host, firmware, API version, channels). "
            "Passive observation only; no CAN transmission."
        ),
        handler=live_handlers.handle_get_cansub_device_status,
        live=True,
    ),
    _ToolBinding(
        name="get_cansub_channel_status",
        description=(
            "Return read-only status for one CANsub.2 channel (bus state, counters, PHY). "
            "Passive observation only."
        ),
        handler=live_handlers.handle_get_cansub_channel_status,
        live=True,
    ),
    _ToolBinding(
        name="start_live_capture",
        description=(
            "Start a background live capture on a CANsub channel. "
            "Creates a session and JSONL frame store. One active capture per channel."
        ),
        handler=live_handlers.handle_start_live_capture,
        live=True,
    ),
    _ToolBinding(
        name="stop_live_capture",
        description="Stop an active background live capture by session_id.",
        handler=live_handlers.handle_stop_live_capture,
        live=True,
    ),
    _ToolBinding(
        name="observe_live_traffic",
        description=(
            "Observe live CAN traffic for a bounded duration (default 3s, max 15s). "
            "Returns aggregated traffic summary, not a raw frame stream. "
            "Fails if the channel RX is in use by an active capture."
        ),
        handler=live_handlers.handle_observe_live_traffic,
        live=True,
    ),
    _ToolBinding(
        name="mark_experiment_event",
        description=(
            "Mark a physical experiment event (annotation only) during a capture session. "
            "Examples: baseline_start, scv2_extend, pto_on."
        ),
        handler=live_handlers.handle_mark_experiment_event,
        live=True,
    ),
    _ToolBinding(
        name="compare_experiment_windows",
        description=(
            "Compare two bounded time windows in a session using experiment event markers. "
            "Returns deterministic frequency and payload change metrics for CAN IDs."
        ),
        handler=live_handlers.handle_compare_experiment_windows,
        live=True,
    ),
)

SIGNAL_RESEARCH_TOOL_BINDINGS: tuple[_ToolBinding, ...] = (
    _ToolBinding(
        name="rank_signal_candidates",
        description=(
            "Rank CAN IDs and changing bytes that differ between baseline and action windows. "
            "Use after marking a repeatable physical action. Returns evidence only; "
            "does not infer signal meaning or modify a DBC."
        ),
        handler=signal_research_handlers.handle_rank_signal_candidates,
    ),
    _ToolBinding(
        name="analyze_can_id_activity",
        description=(
            "Inspect byte/bit activity and bounded field candidates for one CAN ID "
            "across baseline and action windows. Evidence only; no DBC changes."
        ),
        handler=signal_research_handlers.handle_analyze_can_id_activity,
    ),
    _ToolBinding(
        name="analyze_repeated_action",
        description=(
            "Compare repeated baseline/action experiment pairs for bit/byte consistency evidence. "
            "Use when the operator repeated the same action multiple times."
        ),
        handler=signal_research_handlers.handle_analyze_repeated_action,
    ),
    _ToolBinding(
        name="detect_counters",
        description=(
            "Detect bounded counter patterns (8-bit, nibble, 2-bit) in one CAN ID payload series. "
            "Returns candidate evidence, not confirmed counters."
        ),
        handler=signal_research_handlers.handle_detect_counters,
    ),
    _ToolBinding(
        name="detect_checksums",
        description=(
            "Detect bounded checksum patterns (xor8, sum8, twos-complement) for one CAN ID. "
            "Returns candidate evidence only."
        ),
        handler=signal_research_handlers.handle_detect_checksums,
    ),
    _ToolBinding(
        name="correlate_candidate_field",
        description=(
            "Correlate a candidate bitfield against a timestamped reference value series. "
            "Returns Pearson correlation and linear scale/offset fit. Evidence only."
        ),
        handler=signal_research_handlers.handle_correlate_candidate_field,
    ),
)

TOOL_BINDINGS: tuple[_ToolBinding, ...] = (
    READ_ONLY_TOOL_BINDINGS + LIVE_TOOL_BINDINGS + SIGNAL_RESEARCH_TOOL_BINDINGS
)

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    binding.name for binding in READ_ONLY_TOOL_BINDINGS
)
LIVE_TOOL_NAMES: frozenset[str] = frozenset(binding.name for binding in LIVE_TOOL_BINDINGS)
SIGNAL_RESEARCH_TOOL_NAMES: frozenset[str] = frozenset(
    binding.name for binding in SIGNAL_RESEARCH_TOOL_BINDINGS
)


def list_tool_names() -> list[str]:
    """Return all registered MCP tool names."""
    return [binding.name for binding in TOOL_BINDINGS]


def create_server() -> MCPServer:
    """Build the can-research MCP server with read-only and live research tools."""
    server = MCPServer(
        "can-research",
        instructions=(
            "CAN Research tools for stored sessions and passive live CANsub.2 research. "
            "Use get_instance_info when multiple backends/connectors may be active. "
            "Read-only offline flow: list_sessions → get_session → analyze_session → "
            "list_session_nodes → lookup_pgn/lookup_spn → decode_session → "
            "inspect_transport → build_session_dbc_preview. "
            "Live passive experiment flow: get_cansub_device_status → "
            "get_cansub_channel_status → start_live_capture → mark_experiment_event → "
            "stop_live_capture → compare_experiment_windows → rank_signal_candidates → "
            "analyze_can_id_activity → detect_counters/detect_checksums → "
            "analyze_repeated_action → correlate_candidate_field → "
            "list_research_candidates / preview_research_dbc / list_session_events / "
            "preview_candidate_values (read-only). "
            "Signal research tools return candidate evidence only — no DBC modification. "
            "Candidate confirmation/rejection is CLI-only (human approval boundary). "
            "No CAN transmission tools are available."
        ),
    )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[0].description)
    def get_instance_info() -> dict[str, Any]:
        return _invoke(handlers.handle_get_instance_info)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[1].description)
    def list_sessions(limit: int | None = None) -> dict[str, Any]:
        return _invoke(handlers.handle_list_sessions, limit=limit)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[2].description)
    def get_session(session_id: str) -> dict[str, Any]:
        return _invoke(handlers.handle_get_session, session_id=session_id)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[3].description)
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

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[4].description)
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

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[5].description)
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

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[6].description)
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

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[7].description)
    def list_assets(limit: int | None = None) -> dict[str, Any]:
        return _invoke(handlers.handle_list_assets, limit=limit)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[8].description)
    def get_asset(asset_key: str) -> dict[str, Any]:
        return _invoke(handlers.handle_get_asset, asset_key=asset_key)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[9].description)
    def list_asset_nodes(asset_key: str) -> dict[str, Any]:
        return _invoke(handlers.handle_list_asset_nodes, asset_key=asset_key)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[10].description)
    def lookup_pgn(pgn: int) -> dict[str, Any]:
        return _invoke(handlers.handle_lookup_pgn, pgn=pgn)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[11].description)
    def lookup_spn(spn: int) -> dict[str, Any]:
        return _invoke(handlers.handle_lookup_spn, spn=spn)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[12].description)
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

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[13].description)
    def list_research_candidates(
        asset_key: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            research_candidate_handlers.handle_list_research_candidates,
            asset_key=asset_key,
            status=status,
            session_id=session_id,
            limit=limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[14].description)
    def get_research_candidate(candidate_id: str) -> dict[str, Any]:
        return _invoke(
            research_candidate_handlers.handle_get_research_candidate,
            candidate_id=candidate_id,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[15].description)
    def list_candidate_evidence(
        candidate_id: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            research_candidate_handlers.handle_list_candidate_evidence,
            candidate_id=candidate_id,
            limit=limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[16].description)
    def preview_research_dbc(
        asset_key: str,
        preview_lines: int | None = None,
        include_protocol_fields: bool = False,
    ) -> dict[str, Any]:
        return _invoke(
            research_candidate_handlers.handle_preview_research_dbc,
            asset_key=asset_key,
            preview_lines=preview_lines,
            include_protocol_fields=include_protocol_fields,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[17].description)
    def list_session_events(
        session_id: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_list_session_events,
            session_id=session_id,
            limit=limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[18].description)
    def preview_candidate_values(
        session_id: str,
        can_id: int,
        is_extended: bool,
        start_bit: int,
        bit_length: int,
        byte_order: str,
        signedness: str,
        factor: float | None = None,
        offset: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            handlers.handle_preview_candidate_values,
            session_id=session_id,
            can_id=can_id,
            is_extended=is_extended,
            start_bit=start_bit,
            bit_length=bit_length,
            byte_order=byte_order,
            signedness=signedness,
            factor=factor,
            offset=offset,
            limit=limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[19].description)
    def list_dbc_sources(asset_key: str | None = None) -> dict[str, Any]:
        return _invoke(dbc_handlers.handle_list_dbc_sources, asset_key=asset_key)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[20].description)
    def inspect_dbc(
        source_key: str,
        message_limit: int | None = None,
        signals_per_message: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            dbc_handlers.handle_inspect_dbc,
            source_key=source_key,
            message_limit=message_limit,
            signals_per_message=signals_per_message,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[21].description)
    def lookup_dbc_message(
        source_keys: list[str] | None = None,
        asset_key: str | None = None,
        can_id: int | None = None,
        is_extended: bool | None = None,
        message_name: str | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            dbc_handlers.handle_lookup_dbc_message,
            source_keys=source_keys,
            asset_key=asset_key,
            can_id=can_id,
            is_extended=is_extended,
            message_name=message_name,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[22].description)
    def lookup_dbc_signal(
        source_keys: list[str] | None = None,
        asset_key: str | None = None,
        signal_name: str | None = None,
        can_id: int | None = None,
        is_extended: bool | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            dbc_handlers.handle_lookup_dbc_signal,
            source_keys=source_keys,
            asset_key=asset_key,
            signal_name=signal_name,
            can_id=can_id,
            is_extended=is_extended,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[23].description)
    def analyze_dbc_coverage(
        session_id: str,
        source_keys: list[str] | None = None,
        asset_key: str | None = None,
        row_limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            dbc_handlers.handle_analyze_dbc_coverage,
            session_id=session_id,
            source_keys=source_keys,
            asset_key=asset_key,
            row_limit=row_limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[24].description)
    def list_reference_sources() -> dict[str, Any]:
        return _invoke(reference_handlers.handle_list_reference_sources)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[25].description)
    def inspect_reference_source(source_key: str) -> dict[str, Any]:
        return _invoke(reference_handlers.handle_inspect_reference_source, source_key=source_key)

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[26].description)
    def search_reference_knowledge(
        query: str,
        source_key: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            reference_handlers.handle_search_reference_knowledge,
            query=query,
            source_key=source_key,
            limit=limit,
        )

    @server.tool(description=READ_ONLY_TOOL_BINDINGS[27].description)
    def lookup_reference_message(
        can_id: int | None = None,
        is_extended: bool | None = None,
        pgn: int | None = None,
        source_key: str | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            reference_handlers.handle_lookup_reference_message,
            can_id=can_id,
            is_extended=is_extended,
            pgn=pgn,
            source_key=source_key,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[0].description)
    def get_cansub_device_status(
        host: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_get_cansub_device_status,
            host=host,
            timeout=timeout,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[1].description)
    def get_cansub_channel_status(
        channel: int,
        host: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_get_cansub_channel_status,
            channel=channel,
            host=host,
            timeout=timeout,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[2].description)
    def start_live_capture(
        channel: int,
        session_name: str | None = None,
        asset_keys: list[str] | None = None,
        notes: str | None = None,
        host: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_start_live_capture,
            channel=channel,
            session_name=session_name,
            asset_keys=asset_keys,
            notes=notes,
            host=host,
            timeout=timeout,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[3].description)
    def stop_live_capture(session_id: str) -> dict[str, Any]:
        return _invoke(live_handlers.handle_stop_live_capture, session_id=session_id)

    @server.tool(description=LIVE_TOOL_BINDINGS[4].description)
    def observe_live_traffic(
        channel: int,
        duration_seconds: float | None = None,
        pgn: int | None = None,
        source_address: int | None = None,
        can_id: int | None = None,
        limit: int | None = None,
        host: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_observe_live_traffic,
            channel=channel,
            duration_seconds=duration_seconds,
            pgn=pgn,
            source_address=source_address,
            can_id=can_id,
            limit=limit,
            host=host,
            timeout=timeout,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[5].description)
    def mark_experiment_event(
        session_id: str,
        label: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_mark_experiment_event,
            session_id=session_id,
            label=label,
            notes=notes,
        )

    @server.tool(description=LIVE_TOOL_BINDINGS[6].description)
    def compare_experiment_windows(
        session_id: str,
        baseline_event: str,
        action_event: str,
        window_seconds: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            live_handlers.handle_compare_experiment_windows,
            session_id=session_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[0].description)
    def rank_signal_candidates(
        session_id: str,
        baseline_event: str,
        action_event: str,
        window_seconds: float | None = None,
        source_address: int | None = None,
        asset_key: str | None = None,
        can_id: int | None = None,
        pgn: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_rank_signal_candidates,
            session_id=session_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
            source_address=source_address,
            asset_key=asset_key,
            can_id=can_id,
            pgn=pgn,
            limit=limit,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[1].description)
    def analyze_can_id_activity(
        session_id: str,
        can_id: int,
        baseline_event: str | None = None,
        action_event: str | None = None,
        window_seconds: float | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_analyze_can_id_activity,
            session_id=session_id,
            can_id=can_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window_seconds,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[2].description)
    def analyze_repeated_action(
        session_id: str,
        baseline_events: list[str],
        action_events: list[str],
        window_seconds: float | None = None,
        can_id: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_analyze_repeated_action,
            session_id=session_id,
            baseline_events=baseline_events,
            action_events=action_events,
            window_seconds=window_seconds,
            can_id=can_id,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[3].description)
    def detect_counters(session_id: str, can_id: int) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_detect_counters,
            session_id=session_id,
            can_id=can_id,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[4].description)
    def detect_checksums(session_id: str, can_id: int) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_detect_checksums,
            session_id=session_id,
            can_id=can_id,
        )

    @server.tool(description=SIGNAL_RESEARCH_TOOL_BINDINGS[5].description)
    def correlate_candidate_field(
        session_id: str,
        can_id: int,
        start_bit: int,
        length: int,
        reference_series: list[dict[str, Any]],
        signed: bool = False,
        tolerance_us: int | None = None,
    ) -> dict[str, Any]:
        return _invoke(
            signal_research_handlers.handle_correlate_candidate_field,
            session_id=session_id,
            can_id=can_id,
            start_bit=start_bit,
            length=length,
            reference_series=reference_series,
            signed=signed,
            tolerance_us=tolerance_us,
        )

    return server


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    transport: str = "stdio",
    path: str = "/mcp",
) -> None:
    """Start the MCP server.

    ``stdio`` is for desktop MCP clients. ``streamable-http`` exposes the same
    tool registry at ``http://<host>:<port><path>`` for tunnel-backed connectors.
    """
    from canresearch.cansub.live_capture import get_live_capture_registry
    from canresearch.core.capture_liveness import reconcile_orphaned_captures

    reconcile_orphaned_captures(
        registry=get_live_capture_registry(),
        reason="service_restart",
        startup=True,
    )
    server = create_server()
    if transport == "stdio":
        server.run(transport="stdio")
        return
    if transport == "streamable-http":
        server.run(
            transport="streamable-http",
            host=host,
            port=port,
            streamable_http_path=path,
        )
        return
    raise ValueError(f"Unsupported MCP transport: {transport}")
