"""Read-only MCP tool handlers delegating to CAN Research core APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from canresearch.core.analysis import ObservedTraffic, SessionAnalysisSummary, analyze_session
from canresearch.core.assets import (
    get_asset_by_key,
    list_assets,
    list_session_assets,
    list_sessions_for_asset,
)
from canresearch.core.dbc_generation import generate_session_dbc
from canresearch.core.dbc_writer import render_dbc
from canresearch.core.j1939_logical_messages import LogicalJ1939Message
from canresearch.core.j1939_nodes import (
    list_asset_nodes,
    list_session_nodes,
    lookup_asset_keys_for_nodes,
    scan_session_j1939_nodes,
)
from canresearch.core.j1939_tp import TransportResult, reassemble_session_transport
from canresearch.core.session_decode import DecodedSignal, decode_session
from canresearch.core.sessions import SessionRecord, get_session, list_sessions
from canresearch.mcp.errors import McpToolError, limit_out_of_range
from canresearch.mcp.limits import (
    DEFAULT_ANALYZE_OBSERVED,
    DEFAULT_DBC_PREVIEW_LINES,
    DEFAULT_DECODE_LIMIT,
    DEFAULT_LIST_ASSETS,
    DEFAULT_LIST_SESSIONS,
    DEFAULT_TP_COMPLETED,
    MAX_ANALYZE_OBSERVED,
    MAX_DBC_PREVIEW_LINES,
    MAX_DECODE_LIMIT,
    MAX_LIST_ASSETS,
    MAX_LIST_SESSIONS,
    MAX_TP_COMPLETED,
)
from canresearch.references.service import ReferenceService
from canresearch.storage.database import default_db_path, initialize


def _resolve_db_path(db_path: Path | None) -> Path:
    return db_path or default_db_path()


def _normalize_limit(limit: int | None, *, default: int, maximum: int) -> int:
    if limit is None:
        return default
    if limit <= 0:
        raise limit_out_of_range(limit, maximum=maximum)
    return min(limit, maximum)


def _timestamp_iso(timestamp_us: int) -> str:
    return datetime.fromtimestamp(timestamp_us / 1_000_000, tz=UTC).isoformat()


def _capture_source(record: SessionRecord) -> str:
    if record.device_id:
        return "cansub2"
    return "unknown"


def _session_brief(record: SessionRecord) -> dict[str, Any]:
    return {
        "session_id": record.id,
        "name": record.name,
        "created_at": record.started_at.isoformat(),
        "stopped_at": record.stopped_at.isoformat() if record.stopped_at else None,
        "status": record.status.value,
        "frame_count": record.frame_count,
        "capture_source": _capture_source(record),
        "host": record.host,
        "channel": record.channel,
        "device_id": record.device_id,
    }


def _observed_row(item: ObservedTraffic) -> dict[str, Any]:
    return {
        "pgn": item.pgn,
        "can_id": item.can_id,
        "source_address": item.source_address,
        "destination_address": item.destination_address,
        "frame_count": item.frame_count,
        "classification": item.classification,
        "display_name": item.display_name,
        "first_timestamp": _timestamp_iso(item.first_timestamp_us),
        "last_timestamp": _timestamp_iso(item.last_timestamp_us),
    }


def _decoded_row(item: DecodedSignal) -> dict[str, Any]:
    return {
        "timestamp": _timestamp_iso(item.timestamp_us),
        "pgn": item.pgn,
        "spn": item.spn,
        "name": item.spn_name,
        "source_address": item.source_address,
        "destination_address": item.destination_address,
        "raw_value": item.raw_value,
        "engineering_value": item.engineering_value,
        "unit": item.unit,
        "origin": item.origin,
        "status": item.status,
    }


def _name_fields(node_name: Any) -> dict[str, Any]:
    return {
        "name_hex": node_name.name_hex,
        "identity_number": node_name.identity_number,
        "manufacturer_code": node_name.manufacturer_code,
        "function": node_name.function,
        "function_instance": node_name.function_instance,
        "ecu_instance": node_name.ecu_instance,
        "vehicle_system": node_name.vehicle_system,
        "vehicle_system_instance": node_name.vehicle_system_instance,
        "industry_group": node_name.industry_group,
        "arbitrary_address_capable": node_name.arbitrary_address_capable,
    }


def _analysis_summary_dict(
    summary: SessionAnalysisSummary,
    *,
    observed: list[ObservedTraffic],
    observed_total: int,
    observed_limit: int,
) -> dict[str, Any]:
    return {
        "session_id": summary.session_id,
        "session_name": summary.session_name,
        "frames_examined": summary.total_frames,
        "j1939_frames": summary.j1939_frames,
        "non_j1939_frames": summary.non_j1939_frames,
        "error_frames": summary.error_frames,
        "malformed_frames": summary.malformed_frames,
        "duration_s": summary.duration_s,
        "unique_pgns": summary.unique_pgns,
        "unique_source_addresses": summary.unique_source_addresses,
        "known_pgn_count": summary.known_pgn_count,
        "unknown_pgn_count": summary.unknown_pgn_count,
        "observed_traffic": [_observed_row(item) for item in observed],
        "observed_total_count": observed_total,
        "observed_returned_count": len(observed),
        "observed_truncated": observed_total > len(observed),
        "transport": {
            "tp_cm_frames": summary.transport_tp_cm_frames,
            "tp_dt_frames": summary.transport_tp_dt_frames,
            "transfers_started": summary.transport_transfers_started,
            "transfers_completed": summary.transport_transfers_completed,
            "transfers_incomplete": summary.transport_transfers_incomplete,
            "transfers_aborted": summary.transport_transfers_aborted,
            "warning_count": summary.transport_warning_count,
            "completed_pgns": [
                {
                    "transported_pgn": item.transported_pgn,
                    "source_address": item.source_address,
                    "destination_address": item.destination_address,
                    "payload_length": item.payload_length,
                    "transport_mode": item.transport_mode,
                    "packet_count": item.packet_count,
                }
                for item in summary.completed_transport_pgns
            ],
        },
        "identity": {
            "address_claim_frames": summary.identity_address_claim_frames,
            "unique_nodes": summary.identity_unique_nodes,
            "claimed_addresses": list(summary.identity_claimed_addresses),
            "address_conflicts": summary.identity_address_conflicts,
        },
        "observed_limit": observed_limit,
    }


def _transport_message_row(
    message: LogicalJ1939Message,
    *,
    show_payload: bool,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "transported_pgn": message.transported_pgn or message.pgn,
        "source_address": message.source_address,
        "destination_address": message.destination_address,
        "payload_length": message.payload_length or len(message.payload),
        "transport_mode": message.transport_mode.value if message.transport_mode else None,
        "packet_count": message.packet_count,
        "is_transport": message.is_transport,
    }
    if show_payload:
        row["payload_hex"] = message.payload.hex()
    return row


def _transport_dict(
    result: TransportResult,
    *,
    completed: list[LogicalJ1939Message],
    completed_total: int,
    show_payload: bool,
    limit: int,
) -> dict[str, Any]:
    return {
        "tp_cm_frames": result.stats.tp_cm_frames,
        "tp_dt_frames": result.stats.tp_dt_frames,
        "transfers_started": result.stats.transfers_started,
        "transfers_completed": result.stats.transfers_completed,
        "transfers_incomplete": result.stats.transfers_incomplete,
        "transfers_aborted": result.stats.transfers_aborted,
        "warnings": [
            {
                "category": warning.category,
                "message": warning.message,
                "source_address": warning.source_address,
                "transported_pgn": warning.transported_pgn,
            }
            for warning in result.warnings
        ],
        "completed_messages": [
            _transport_message_row(message, show_payload=show_payload) for message in completed
        ],
        "completed_total_count": completed_total,
        "completed_returned_count": len(completed),
        "completed_truncated": completed_total > len(completed),
        "limit": limit,
    }


def handle_list_sessions(
    *,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List stored capture sessions (metadata only, no raw frames)."""
    applied = _normalize_limit(limit, default=DEFAULT_LIST_SESSIONS, maximum=MAX_LIST_SESSIONS)
    records = list_sessions(db_path=_resolve_db_path(db_path), limit=applied)
    return {
        "sessions": [_session_brief(record) for record in records],
        "returned_count": len(records),
        "truncated": len(records) >= applied,
        "limit": applied,
    }


def handle_get_session(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return metadata and linked assets for one session."""
    path = _resolve_db_path(db_path)
    try:
        record = get_session(session_id, db_path=path)
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc

    duration_s: float | None = None
    if record.stopped_at is not None:
        duration_s = (record.stopped_at - record.started_at).total_seconds()

    assets = list_session_assets(session_id, db_path=path)
    return {
        "session": {
            "session_id": record.id,
            "name": record.name,
            "device_id": record.device_id,
            "host": record.host,
            "channel": record.channel,
            "started_at": record.started_at.isoformat(),
            "stopped_at": record.stopped_at.isoformat() if record.stopped_at else None,
            "duration_s": duration_s,
            "status": record.status.value,
            "frame_count": record.frame_count,
            "capture_source": _capture_source(record),
            "notes": record.notes,
        },
        "linked_assets": [
            {
                "asset_key": item.asset_key,
                "display_name": item.display_name,
                "asset_type": item.asset_type,
                "role": item.role,
            }
            for item in assets
        ],
    }


def handle_analyze_session(
    session_id: str,
    *,
    pgn: int | None = None,
    source_address: int | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Summarize stored session traffic at frame/PGN/transport/node level."""
    applied = _normalize_limit(
        limit,
        default=DEFAULT_ANALYZE_OBSERVED,
        maximum=MAX_ANALYZE_OBSERVED,
    )
    try:
        summary = analyze_session(session_id, db_path=_resolve_db_path(db_path), persist=False)
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except FileNotFoundError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc

    observed = list(summary.observed)
    if pgn is not None:
        observed = [item for item in observed if item.pgn == pgn]
    if source_address is not None:
        observed = [item for item in observed if item.source_address == source_address]
    total = len(observed)
    observed = observed[:applied]
    return _analysis_summary_dict(
        summary,
        observed=observed,
        observed_total=total,
        observed_limit=applied,
    )


def handle_decode_session(
    session_id: str,
    *,
    pgn: int | None = None,
    spn: int | None = None,
    source_address: int | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Decode reference-backed SPN values from a stored session."""
    applied = _normalize_limit(limit, default=DEFAULT_DECODE_LIMIT, maximum=MAX_DECODE_LIMIT)
    try:
        summary = decode_session(
            session_id,
            db_path=_resolve_db_path(db_path),
            pgn_filter=pgn,
            spn_filter=spn,
            limit=None if source_address is not None else applied,
        )
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except FileNotFoundError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc

    signals = list(summary.decoded_signals)
    if source_address is not None:
        signals = [item for item in signals if item.source_address == source_address]
    total = len(signals)
    signals = signals[:applied]
    return {
        "session_id": summary.session_id,
        "session_name": summary.session_name,
        "frames_examined": summary.total_frames,
        "j1939_frames": summary.j1939_frames,
        "known_pgn_frames": summary.known_pgn_frames,
        "transport_messages_decoded": summary.transport_messages_decoded,
        "signals": [_decoded_row(item) for item in signals],
        "warnings": [
            {"category": item.category, "message": item.message, "pgn": item.pgn, "spn": item.spn}
            for item in summary.warnings
        ],
        "matched_total_count": total,
        "returned_count": len(signals),
        "truncated": total > len(signals),
        "limit": applied,
    }


def handle_inspect_transport(
    session_id: str,
    *,
    pgn: int | None = None,
    source_address: int | None = None,
    show_payload: bool = False,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Inspect J1939 transport-protocol reassembly for a stored session."""
    applied = _normalize_limit(limit, default=DEFAULT_TP_COMPLETED, maximum=MAX_TP_COMPLETED)
    try:
        result = reassemble_session_transport(session_id, db_path=_resolve_db_path(db_path))
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except FileNotFoundError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc

    completed = list(result.completed_messages)
    if pgn is not None:
        completed = [
            item for item in completed if (item.transported_pgn or item.pgn) == pgn
        ]
    if source_address is not None:
        completed = [item for item in completed if item.source_address == source_address]
    total = len(completed)
    completed = completed[:applied]
    return {
        "session_id": session_id,
        **_transport_dict(
            result,
            completed=completed,
            completed_total=total,
            show_payload=show_payload,
            limit=applied,
        ),
    }


def handle_list_session_nodes(
    session_id: str,
    *,
    source_address: int | None = None,
    manufacturer_code: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List J1939 Address Claim node identities observed in a session."""
    path = _resolve_db_path(db_path)
    try:
        get_session(session_id, db_path=path)
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc

    nodes = list_session_nodes(session_id, db_path=path)
    if not nodes:
        try:
            discovery = scan_session_j1939_nodes(session_id, db_path=path, persist=False)
        except FileNotFoundError as exc:
            raise McpToolError("session_not_found", str(exc)) from exc
        nodes = list(discovery.nodes)

    asset_links = lookup_asset_keys_for_nodes(
        [node.node_id for node in nodes if node.node_id],
        db_path=path,
    )

    rows: list[dict[str, Any]] = []
    for node in nodes:
        if source_address is not None and not any(
            obs.source_address == source_address for obs in node.observations
        ):
            continue
        if manufacturer_code is not None and node.name.manufacturer_code != manufacturer_code:
            continue
        latest_sa = node.latest_source_address
        rows.append(
            {
                **_name_fields(node.name),
                "latest_source_address": latest_sa,
                "cannot_claim": node.cannot_claim,
                "claim_count": node.claim_count,
                "asset_key": asset_links.get(node.node_id) if node.node_id else None,
                "observations": [
                    {
                        "source_address": obs.source_address,
                        "claim_count": obs.claim_count,
                        "cannot_claim": obs.cannot_claim,
                        "first_seen_at": _timestamp_iso(obs.first_seen_at_us),
                        "last_seen_at": _timestamp_iso(obs.last_seen_at_us),
                    }
                    for obs in node.observations
                ],
            }
        )

    return {
        "session_id": session_id,
        "nodes": rows,
        "returned_count": len(rows),
    }


def handle_list_assets(
    *,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List registered assets (read-only)."""
    applied = _normalize_limit(limit, default=DEFAULT_LIST_ASSETS, maximum=MAX_LIST_ASSETS)
    assets = list_assets(db_path=_resolve_db_path(db_path), limit=applied)
    return {
        "assets": [
            {
                "asset_key": item.asset_key,
                "asset_type": item.asset_type,
                "display_name": item.display_name,
                "manufacturer": item.manufacturer,
                "model": item.model,
            }
            for item in assets
        ],
        "returned_count": len(assets),
        "truncated": len(assets) >= applied,
        "limit": applied,
    }


def handle_get_asset(
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return asset metadata, linked J1939 NAMEs, and linked sessions."""
    path = _resolve_db_path(db_path)
    try:
        asset = get_asset_by_key(asset_key, db_path=path)
    except KeyError as exc:
        raise McpToolError("asset_not_found", str(exc)) from exc

    nodes = list_asset_nodes(asset_key, db_path=path)
    sessions = list_sessions_for_asset(asset_key, db_path=path)
    return {
        "asset": {
            "asset_key": asset.asset_key,
            "asset_type": asset.asset_type,
            "display_name": asset.display_name,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "notes": asset.notes,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
        },
        "linked_j1939_names": [_name_fields(node.name) for node in nodes],
        "linked_sessions": [
            {"session_id": item.session_id, "role": item.role} for item in sessions
        ],
    }


def handle_list_asset_nodes(
    asset_key: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List J1939 NAME identities linked to an asset."""
    try:
        nodes = list_asset_nodes(asset_key, db_path=_resolve_db_path(db_path))
    except KeyError as exc:
        raise McpToolError("asset_not_found", str(exc)) from exc
    return {
        "asset_key": asset_key,
        "nodes": [_name_fields(node.name) for node in nodes],
        "returned_count": len(nodes),
    }


def handle_lookup_pgn(
    pgn: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Look up a PGN in the local reference catalogue."""
    conn = initialize(_resolve_db_path(db_path))
    try:
        service = ReferenceService(conn)
        rows = service.lookup_pgn(pgn)
        if not rows:
            raise McpToolError("invalid_pgn", f"PGN {pgn} not found in reference catalogue")
        mappings = service.pgn_spn_mappings(pgn)
    finally:
        conn.close()

    entries = [
        {
            "origin": row["origin"],
            "name": row["name"],
            "acronym": row["acronym"],
            "payload_length": row["payload_length"],
            "source_title": row["source_title"],
        }
        for row in rows
    ]
    spn_rows = [
        {
            "spn": row["spn"],
            "spn_name": row["spn_name"],
            "origin": row["origin"],
            "start_byte": row["start_byte"],
            "start_bit": row["start_bit"],
            "bit_length": row["bit_length"],
            "raw_position_text": row["raw_position_text"],
        }
        for row in mappings
    ]
    return {
        "pgn": pgn,
        "entries": entries,
        "spn_mappings": spn_rows,
        "mapping_count": len(spn_rows),
    }


def handle_lookup_spn(
    spn: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Look up an SPN in the local reference catalogue."""
    conn = initialize(_resolve_db_path(db_path))
    try:
        service = ReferenceService(conn)
        rows = service.lookup_spn(spn)
        if not rows:
            raise McpToolError("invalid_spn", f"SPN {spn} not found in reference catalogue")
        mappings = service.spn_pgn_mappings(spn)
    finally:
        conn.close()

    entries = [
        {
            "origin": row["origin"],
            "name": row["name"],
            "resolution": row["resolution"],
            "offset": row["offset"],
            "unit": row["unit"],
            "data_type": row["data_type"],
            "source_title": row["source_title"],
        }
        for row in rows
    ]
    pgn_rows = [
        {
            "pgn": row["pgn"],
            "pgn_name": row["pgn_name"],
            "acronym": row["acronym"],
            "origin": row["origin"],
            "start_byte": row["start_byte"],
            "start_bit": row["start_bit"],
            "bit_length": row["bit_length"],
            "raw_position_text": row["raw_position_text"],
        }
        for row in mappings
    ]
    return {
        "spn": spn,
        "entries": entries,
        "pgn_mappings": pgn_rows,
        "mapping_count": len(pgn_rows),
    }


def handle_build_session_dbc_preview(
    session_id: str,
    asset_key: str,
    *,
    source_addresses: list[int] | None = None,
    preview_lines: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build an in-memory asset-specific DBC preview (no file write)."""
    applied_lines = _normalize_limit(
        preview_lines,
        default=DEFAULT_DBC_PREVIEW_LINES,
        maximum=MAX_DBC_PREVIEW_LINES,
    )
    path = _resolve_db_path(db_path)
    sa_tuple = tuple(source_addresses) if source_addresses else None
    try:
        summary = generate_session_dbc(
            session_id,
            asset_key=asset_key,
            db_path=path,
            source_addresses=sa_tuple,
        )
    except KeyError as exc:
        message = str(exc)
        if "Session not found" in message:
            raise McpToolError("session_not_found", message) from exc
        raise McpToolError("asset_not_found", message) from exc
    except ValueError as exc:
        message = str(exc)
        if "not linked" in message:
            raise McpToolError("asset_not_linked_to_session", message) from exc
        if "No source addresses" in message or "No J1939 nodes linked" in message:
            raise McpToolError("no_source_addresses_resolved", message) from exc
        raise McpToolError("invalid_request", message) from exc

    dbc_text = render_dbc(summary.database)
    lines = dbc_text.splitlines()
    preview = "\n".join(lines[:applied_lines])
    provenance = summary.provenance
    return {
        "asset_key": summary.asset_key,
        "session_id": summary.session_id,
        "source_address_origin": provenance.source_address_origin if provenance else "manual",
        "source_addresses": list(summary.source_addresses),
        "j1939_names": list(provenance.j1939_names) if provenance else [],
        "messages": summary.messages_generated,
        "signals": summary.signals_generated,
        "signals_skipped": summary.signals_skipped,
        "warnings": [
            {"category": item.category, "message": item.message, "pgn": item.pgn, "spn": item.spn}
            for item in summary.warnings
        ],
        "dbc_preview": preview,
        "dbc_total_lines": len(lines),
        "preview_lines": applied_lines,
        "preview_truncated": len(lines) > applied_lines,
    }


def handle_list_session_events(
    session_id: str,
    *,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return experiment markers for a stored session."""
    from canresearch.core.session_events import list_session_events
    from canresearch.mcp.limits import DEFAULT_LIST_SESSION_EVENTS, MAX_LIST_SESSION_EVENTS

    applied_limit = limit if limit is not None else DEFAULT_LIST_SESSION_EVENTS
    if applied_limit <= 0 or applied_limit > MAX_LIST_SESSION_EVENTS:
        raise limit_out_of_range(applied_limit, maximum=MAX_LIST_SESSION_EVENTS)
    try:
        events = list_session_events(
            session_id,
            limit=applied_limit,
            db_path=_resolve_db_path(db_path),
        )
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except ValueError as exc:
        raise McpToolError("limit_out_of_range", str(exc)) from exc

    return {
        "session_id": session_id,
        "count": len(events),
        "events": [
            {
                "id": event.id,
                "session_id": event.session_id,
                "timestamp_us": event.timestamp_us,
                "label": event.label,
                "notes": event.notes,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


def handle_preview_candidate_values(
    session_id: str,
    can_id: int,
    is_extended: bool,
    start_bit: int,
    bit_length: int,
    byte_order: str,
    signedness: str,
    *,
    factor: float | None = None,
    offset: float | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Preview raw/scaled values for a proposed field in a stored session."""
    from canresearch.core.candidate_preview import (
        DEFAULT_PREVIEW_LIMIT,
        MAX_PREVIEW_LIMIT,
        preview_candidate_field_values,
    )
    from canresearch.core.research_candidates import ResearchCandidateError

    applied_limit = limit if limit is not None else DEFAULT_PREVIEW_LIMIT
    if applied_limit <= 0 or applied_limit > MAX_PREVIEW_LIMIT:
        raise limit_out_of_range(applied_limit, maximum=MAX_PREVIEW_LIMIT)
    try:
        return preview_candidate_field_values(
            session_id,
            can_id=can_id,
            is_extended=is_extended,
            start_bit=start_bit,
            bit_length=bit_length,
            byte_order=byte_order,
            signedness=signedness,
            factor=factor,
            offset=offset,
            limit=applied_limit,
            db_path=_resolve_db_path(db_path),
        )
    except KeyError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except FileNotFoundError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except ResearchCandidateError as exc:
        raise McpToolError(exc.code, exc.message) from exc


def handle_get_instance_info() -> dict[str, Any]:
    """Return configured installation identity and MCP capability summary."""
    import platform

    from canresearch import __version__
    from canresearch.config import load_config
    from canresearch.mcp.server import (
        LIVE_TOOL_NAMES,
        READ_ONLY_TOOL_NAMES,
        SIGNAL_RESEARCH_TOOL_NAMES,
        list_tool_names,
    )
    from canresearch.storage.database import SCHEMA_VERSION

    config = load_config()
    cansub_configured = config.cansub.host is not None
    return {
        "instance_key": config.instance.instance_key,
        "display_name": config.instance.display_name,
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "mcp_tool_count": len(list_tool_names()),
        "capabilities": {
            "read_only_tools": len(READ_ONLY_TOOL_NAMES),
            "live_tools": len(LIVE_TOOL_NAMES),
            "signal_research_tools": len(SIGNAL_RESEARCH_TOOL_NAMES),
            "can_tx": False,
            "candidate_confirmation": False,
        },
        "platform": platform.system(),
        "cansub": {
            "host_configured": cansub_configured,
            "connection_mode": "configured_host" if cansub_configured else "not_set",
        },
    }
