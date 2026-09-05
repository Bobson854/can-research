"""MCP handlers for proprietary signal research (read-only evidence)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.core.live_errors import LiveResearchError
from canresearch.core.signal_research import (
    DEFAULT_CANDIDATE_IDS,
    MAX_CANDIDATE_IDS,
    analyze_can_id_activity,
    compare_repeated_actions,
    correlate_candidate_field,
    detect_checksums_for_can_id,
    detect_counters_for_can_id,
    rank_candidate_ids,
)
from canresearch.mcp.errors import McpToolError
from canresearch.storage.database import default_db_path


def _resolve_db(db_path: Path | None) -> Path:
    return db_path or default_db_path()


def _to_mcp_error(exc: LiveResearchError) -> McpToolError:
    return McpToolError(exc.code, exc.message)


def handle_rank_signal_candidates(
    session_id: str,
    baseline_event: str,
    action_event: str,
    *,
    window_seconds: float | None = None,
    source_address: int | None = None,
    asset_key: str | None = None,
    can_id: int | None = None,
    pgn: int | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Rank CAN IDs that differ between baseline and action windows."""
    row_limit = limit if limit is not None else DEFAULT_CANDIDATE_IDS
    if row_limit <= 0 or row_limit > MAX_CANDIDATE_IDS:
        raise McpToolError(
            "limit_out_of_range",
            f"limit must be between 1 and {MAX_CANDIDATE_IDS}, got {row_limit}",
        )
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "baseline_event": baseline_event,
        "action_event": action_event,
        "source_address": source_address,
        "asset_key": asset_key,
        "can_id": can_id,
        "pgn": pgn,
        "limit": row_limit,
        "db_path": _resolve_db(db_path),
    }
    if window_seconds is not None:
        kwargs["window_seconds"] = window_seconds
    try:
        return rank_candidate_ids(**kwargs)
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc


def handle_analyze_can_id_activity(
    session_id: str,
    can_id: int,
    *,
    baseline_event: str | None = None,
    action_event: str | None = None,
    window_seconds: float | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Inspect byte/bit activity and field candidates for one CAN ID."""
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "can_id": can_id,
        "db_path": _resolve_db(db_path),
    }
    if baseline_event is not None:
        kwargs["baseline_event"] = baseline_event
    if action_event is not None:
        kwargs["action_event"] = action_event
    if window_seconds is not None:
        kwargs["window_seconds"] = window_seconds
    try:
        return analyze_can_id_activity(**kwargs)
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc
    except FileNotFoundError as exc:
        raise McpToolError("capture_session_not_found", str(exc)) from exc


def handle_analyze_repeated_action(
    session_id: str,
    baseline_events: list[str],
    action_events: list[str],
    *,
    window_seconds: float | None = None,
    can_id: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Compare repeated baseline/action pairs for consistency evidence."""
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "baseline_events": baseline_events,
        "action_events": action_events,
        "db_path": _resolve_db(db_path),
    }
    if window_seconds is not None:
        kwargs["window_seconds"] = window_seconds
    if can_id is not None:
        kwargs["can_id"] = can_id
    try:
        return compare_repeated_actions(**kwargs)
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc


def handle_detect_counters(
    session_id: str,
    can_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Detect bounded counter patterns for one CAN ID."""
    try:
        return detect_counters_for_can_id(session_id, can_id, db_path=_resolve_db(db_path))
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc
    except FileNotFoundError as exc:
        raise McpToolError("capture_session_not_found", str(exc)) from exc


def handle_detect_checksums(
    session_id: str,
    can_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Detect bounded checksum patterns for one CAN ID."""
    try:
        return detect_checksums_for_can_id(session_id, can_id, db_path=_resolve_db(db_path))
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc
    except FileNotFoundError as exc:
        raise McpToolError("capture_session_not_found", str(exc)) from exc


def handle_correlate_candidate_field(
    session_id: str,
    can_id: int,
    start_bit: int,
    length: int,
    reference_series: list[dict[str, Any]],
    *,
    signed: bool = False,
    tolerance_us: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Correlate a candidate field against a timestamped reference series."""
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "can_id": can_id,
        "start_bit": start_bit,
        "length": length,
        "reference_series": reference_series,
        "signed": signed,
        "db_path": _resolve_db(db_path),
    }
    if tolerance_us is not None:
        kwargs["tolerance_us"] = tolerance_us
    try:
        return correlate_candidate_field(**kwargs)
    except LiveResearchError as exc:
        raise _to_mcp_error(exc) from exc
    except FileNotFoundError as exc:
        raise McpToolError("capture_session_not_found", str(exc)) from exc
