"""MCP handlers for live CANsub.2 research controls (passive observation only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canresearch.cansub.live_capture import start_live_capture, stop_live_capture
from canresearch.config import ConfigError, resolve_cansub_settings
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.live_research import (
    DEFAULT_COMPARE_WINDOW_S,
    DEFAULT_OBSERVE_DURATION_S,
    DEFAULT_TRAFFIC_ROWS,
    MAX_COMPARE_WINDOW_S,
    MAX_OBSERVE_DURATION_S,
    MAX_TRAFFIC_ROWS,
    compare_experiment_windows,
    get_cansub_channel_status,
    get_cansub_device_status,
    mark_experiment_event,
    observe_live_traffic,
)
from canresearch.mcp.errors import McpToolError, limit_out_of_range
from canresearch.storage.database import default_db_path


def _resolve_db_path(db_path: Path | None) -> Path:
    return db_path or default_db_path()


def _resolve_host_settings(
    host: str | None = None,
    timeout: float | None = None,
) -> tuple[str, float, bool]:
    try:
        return resolve_cansub_settings(host, timeout, None)
    except ConfigError as exc:
        raise McpToolError("cansub_unreachable", str(exc)) from exc


def _live_error(exc: LiveResearchError) -> McpToolError:
    return McpToolError(exc.code, exc.message)


def handle_get_cansub_device_status(
    *,
    host: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Return CANsub.2 device status from the REST API."""
    resolved_host, resolved_timeout, verify_tls = _resolve_host_settings(host, timeout)
    try:
        return get_cansub_device_status(
            resolved_host,
            timeout=resolved_timeout,
            verify_tls=verify_tls,
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_get_cansub_channel_status(
    channel: int,
    *,
    host: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Return read-only CAN channel status."""
    resolved_host, resolved_timeout, verify_tls = _resolve_host_settings(host, timeout)
    try:
        return get_cansub_channel_status(
            resolved_host,
            channel,
            timeout=resolved_timeout,
            verify_tls=verify_tls,
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_start_live_capture(
    channel: int,
    *,
    session_name: str | None = None,
    asset_keys: list[str] | None = None,
    notes: str | None = None,
    host: str | None = None,
    timeout: float | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Start a background live capture on a CANsub channel."""
    resolved_host, resolved_timeout, verify_tls = _resolve_host_settings(host, timeout)
    keys = tuple(asset_keys) if asset_keys else ()
    try:
        return start_live_capture(
            resolved_host,
            channel,
            session_name=session_name,
            asset_keys=keys,
            notes=notes,
            timeout=resolved_timeout,
            verify_tls=verify_tls,
            db_path=_resolve_db_path(db_path),
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_stop_live_capture(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Stop an active background live capture."""
    try:
        return stop_live_capture(session_id, db_path=_resolve_db_path(db_path))
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_observe_live_traffic(
    channel: int,
    *,
    duration_seconds: float | None = None,
    pgn: int | None = None,
    source_address: int | None = None,
    can_id: int | None = None,
    limit: int | None = None,
    host: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Observe live CAN traffic for a bounded duration (aggregated summary)."""
    resolved_host, resolved_timeout, verify_tls = _resolve_host_settings(host, timeout)
    duration = duration_seconds if duration_seconds is not None else DEFAULT_OBSERVE_DURATION_S
    if duration < 0.5 or duration > MAX_OBSERVE_DURATION_S:
        raise McpToolError(
            "limit_out_of_range",
            f"duration_seconds must be between 0.5 and {MAX_OBSERVE_DURATION_S}, got {duration}",
        )
    row_limit = limit if limit is not None else DEFAULT_TRAFFIC_ROWS
    if row_limit <= 0 or row_limit > MAX_TRAFFIC_ROWS:
        raise limit_out_of_range(row_limit, maximum=MAX_TRAFFIC_ROWS)
    try:
        return observe_live_traffic(
            resolved_host,
            channel,
            duration_seconds=duration,
            pgn=pgn,
            source_address=source_address,
            can_id=can_id,
            limit=row_limit,
            timeout=resolved_timeout,
            verify_tls=verify_tls,
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_mark_experiment_event(
    session_id: str,
    label: str,
    *,
    notes: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Mark a physical experiment event during a capture session."""
    try:
        return mark_experiment_event(
            session_id,
            label,
            notes=notes,
            db_path=_resolve_db_path(db_path),
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc


def handle_compare_experiment_windows(
    session_id: str,
    baseline_event: str,
    action_event: str,
    *,
    window_seconds: float | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Compare baseline and action experiment windows in a stored session."""
    window = window_seconds if window_seconds is not None else DEFAULT_COMPARE_WINDOW_S
    if window <= 0 or window > MAX_COMPARE_WINDOW_S:
        raise McpToolError(
            "limit_out_of_range",
            f"window_seconds must be between 0 and {MAX_COMPARE_WINDOW_S}, got {window}",
        )
    try:
        return compare_experiment_windows(
            session_id,
            baseline_event=baseline_event,
            action_event=action_event,
            window_seconds=window,
            db_path=_resolve_db_path(db_path),
        )
    except LiveResearchError as exc:
        raise _live_error(exc) from exc
