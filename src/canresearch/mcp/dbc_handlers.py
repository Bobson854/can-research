"""MCP handlers for DBC library and coverage analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.core.dbc_coverage import analyze_dbc_coverage
from canresearch.core.dbc_knowledge import DbcKnowledgeError, DbcSourceNotFoundError
from canresearch.core.dbc_lookup import (
    lookup_message_by_can_id,
    lookup_message_by_name,
    lookup_signal_by_name,
    lookup_signals_for_can_id,
)
from canresearch.core.dbc_registry import inspect_dbc_source, list_dbc_source_meta, load_dbc_sources
from canresearch.mcp.errors import McpToolError
from canresearch.mcp.limits import (
    DEFAULT_DBC_COVERAGE_ROWS,
    DEFAULT_DBC_INSPECT_MESSAGES,
    DEFAULT_DBC_INSPECT_SIGNALS,
    MAX_DBC_COVERAGE_ROWS,
    MAX_DBC_INSPECT_MESSAGES,
    MAX_DBC_INSPECT_SIGNALS,
    MAX_LIST_DBC_SOURCES,
    clamp_limit,
)


def _meta_dict(meta: Any) -> dict[str, Any]:
    return {
        "key": meta.key,
        "display_name": meta.display_name,
        "path": meta.path,
        "source_type": meta.source_type,
        "asset_key": meta.asset_key,
        "message_count": meta.message_count,
        "signal_count": meta.signal_count,
    }


def _signal_dict(signal: Any) -> dict[str, Any]:
    return {
        "name": signal.name,
        "start_bit": signal.start_bit,
        "bit_length": signal.bit_length,
        "byte_order": "intel" if signal.byte_order == 1 else "motorola",
        "signed": signal.signed,
        "factor": signal.factor,
        "offset": signal.offset,
        "unit": signal.unit,
    }


def _message_dict(message: Any, *, include_signals: bool) -> dict[str, Any]:
    is_extended = message.dbc_frame_id >= 0x80000000 or message.can_id > 0x7FF
    payload: dict[str, Any] = {
        "name": message.name,
        "can_id": message.can_id,
        "can_id_hex": f"0x{message.can_id:08X}" if is_extended else f"0x{message.can_id:03X}",
        "is_extended": is_extended,
        "dlc": message.dlc,
        "pgn": message.pgn or None,
        "source_address": message.source_address,
        "destination_address": message.destination_address,
        "signal_count": len(message.signals),
    }
    if include_signals:
        payload["signals"] = [_signal_dict(signal) for signal in message.signals]
    return payload


def handle_list_dbc_sources(*, asset_key: str | None = None) -> dict[str, Any]:
    try:
        metas = list_dbc_source_meta(asset_key=asset_key)
    except DbcKnowledgeError as exc:
        raise McpToolError("dbc_registry_error", str(exc)) from exc
    limited = metas[:MAX_LIST_DBC_SOURCES]
    return {
        "sources": [_meta_dict(meta) for meta in limited],
        "count": len(limited),
        "truncated": len(metas) > len(limited),
    }


def handle_inspect_dbc(
    *,
    source_key: str,
    message_limit: int | None = None,
    signals_per_message: int | None = None,
) -> dict[str, Any]:
    msg_limit = clamp_limit(message_limit, DEFAULT_DBC_INSPECT_MESSAGES, MAX_DBC_INSPECT_MESSAGES)
    sig_limit = clamp_limit(
        signals_per_message,
        DEFAULT_DBC_INSPECT_SIGNALS,
        MAX_DBC_INSPECT_SIGNALS,
    )
    try:
        loaded = inspect_dbc_source(source_key)
    except DbcSourceNotFoundError as exc:
        raise McpToolError("dbc_source_not_found", str(exc)) from exc
    except DbcKnowledgeError as exc:
        raise McpToolError("dbc_load_error", str(exc)) from exc

    messages = []
    for message in loaded.database.messages[:msg_limit]:
        item = _message_dict(message, include_signals=False)
        item["signals"] = [_signal_dict(signal) for signal in message.signals[:sig_limit]]
        if len(message.signals) > sig_limit:
            item["signals_truncated"] = True
        messages.append(item)

    return {
        "source": _meta_dict(loaded.meta),
        "version": loaded.database.version,
        "nodes": list(loaded.database.nodes),
        "messages": messages,
        "message_count": len(loaded.database.messages),
        "signal_count": loaded.meta.signal_count,
        "messages_truncated": len(loaded.database.messages) > msg_limit,
        "warnings": [
            {"category": warning.category, "message": warning.message, "line": warning.line_number}
            for warning in loaded.warnings[:50]
        ],
    }


def handle_lookup_dbc_message(
    *,
    source_keys: list[str] | None = None,
    asset_key: str | None = None,
    can_id: int | None = None,
    is_extended: bool | None = None,
    message_name: str | None = None,
) -> dict[str, Any]:
    if can_id is None and not message_name:
        raise McpToolError("invalid_request", "Provide can_id or message_name")
    try:
        keys = tuple(source_keys) if source_keys else None
        sources = load_dbc_sources(source_keys=keys, asset_key=asset_key)
    except DbcKnowledgeError as exc:
        raise McpToolError("dbc_source_not_found", str(exc)) from exc

    matches = []
    if can_id is not None:
        extended = is_extended if is_extended is not None else can_id > 0x7FF
        for item in lookup_message_by_can_id(sources, can_id=can_id, is_extended=extended):
            matches.append(
                {
                    "source_key": item.source_key,
                    "message": _message_dict(item.message, include_signals=True),
                }
            )
    if message_name:
        for item in lookup_message_by_name(sources, message_name):
            matches.append(
                {
                    "source_key": item.source_key,
                    "message": _message_dict(item.message, include_signals=True),
                }
            )
    return {"matches": matches[:20], "match_count": len(matches)}


def handle_lookup_dbc_signal(
    *,
    source_keys: list[str] | None = None,
    asset_key: str | None = None,
    signal_name: str | None = None,
    can_id: int | None = None,
    is_extended: bool | None = None,
) -> dict[str, Any]:
    if not signal_name and can_id is None:
        raise McpToolError("invalid_request", "Provide signal_name or can_id")
    try:
        keys = tuple(source_keys) if source_keys else None
        sources = load_dbc_sources(source_keys=keys, asset_key=asset_key)
    except DbcKnowledgeError as exc:
        raise McpToolError("dbc_source_not_found", str(exc)) from exc

    matches = []
    if signal_name:
        for item in lookup_signal_by_name(sources, signal_name):
            matches.append(
                {
                    "source_key": item.source_key,
                    "message_name": item.message.name,
                    "can_id_hex": f"0x{item.message.can_id:08X}",
                    "signal": _signal_dict(item.signal),
                }
            )
    if can_id is not None:
        extended = is_extended if is_extended is not None else can_id > 0x7FF
        for item in lookup_signals_for_can_id(sources, can_id=can_id, is_extended=extended):
            matches.append(
                {
                    "source_key": item.source_key,
                    "message_name": item.message.name,
                    "can_id_hex": f"0x{item.message.can_id:08X}",
                    "signal": _signal_dict(item.signal),
                }
            )
    return {"matches": matches[:50], "match_count": len(matches)}


def handle_analyze_dbc_coverage(
    *,
    session_id: str,
    source_keys: list[str] | None = None,
    asset_key: str | None = None,
    row_limit: int | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    limit = clamp_limit(row_limit, DEFAULT_DBC_COVERAGE_ROWS, MAX_DBC_COVERAGE_ROWS)
    path = Path(db_path) if db_path else None
    try:
        summary = analyze_dbc_coverage(
            session_id,
            source_keys=tuple(source_keys) if source_keys else None,
            asset_key=asset_key,
            db_path=path,
            row_limit=limit,
        )
    except DbcSourceNotFoundError as exc:
        raise McpToolError("dbc_source_not_found", str(exc)) from exc
    except FileNotFoundError as exc:
        raise McpToolError("session_not_found", str(exc)) from exc
    except ValueError as exc:
        raise McpToolError("invalid_request", str(exc)) from exc

    rows = [
        {
            "can_id_hex": (
                f"0x{row.can_id:08X}" if row.is_extended else f"0x{row.can_id:03X}"
            ),
            "is_extended": row.is_extended,
            "frame_count": row.frame_count,
            "max_dlc": row.max_dlc,
            "pgn": row.pgn,
            "source_address": row.source_address,
            "destination_address": row.destination_address,
            "classification": row.classification,
            "reason": row.reason,
            "dbc_source_key": row.dbc_source_key,
            "message_name": row.message_name,
            "signal_count": row.signal_count,
        }
        for row in summary.rows
    ]
    return {
        "session_id": summary.session_id,
        "asset_key": summary.asset_key,
        "dbc_sources": list(summary.dbc_sources),
        "summary": {
            "unique_ids_observed": summary.unique_ids_observed,
            "unique_ids_covered": summary.unique_ids_covered,
            "unique_ids_partially_covered": summary.unique_ids_partially_covered,
            "unique_ids_unknown": summary.unique_ids_unknown,
            "frames_observed": summary.frames_observed,
            "frames_covered": summary.frames_covered,
            "frames_partially_covered": summary.frames_partially_covered,
            "frames_unknown": summary.frames_unknown,
            "unique_id_coverage_pct": summary.unique_id_coverage_pct,
            "frame_coverage_pct": summary.frame_coverage_pct,
        },
        "known_first": {
            "known": list(summary.known_can_ids),
            "partially_covered": list(summary.partially_covered_can_ids),
            "unknown": list(summary.unknown_can_ids),
        },
        "rows": rows,
        "rows_returned": len(rows),
        "rows_truncated": summary.unique_ids_observed > len(rows),
    }
