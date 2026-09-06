"""Tests for live MCP tool registration and handlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from canresearch.mcp.errors import McpToolError
from canresearch.mcp.live_handlers import (
    handle_compare_experiment_windows,
    handle_get_cansub_device_status,
    handle_mark_experiment_event,
    handle_observe_live_traffic,
    handle_start_live_capture,
    handle_stop_live_capture,
)
from canresearch.mcp.server import LIVE_TOOL_NAMES, READ_ONLY_TOOL_NAMES, list_tool_names
from canresearch.storage.database import initialize

LIVE_TOOLS = frozenset(
    {
        "get_cansub_device_status",
        "get_cansub_channel_status",
        "start_live_capture",
        "stop_live_capture",
        "observe_live_traffic",
        "mark_experiment_event",
        "compare_experiment_windows",
    }
)

FORBIDDEN_TX_TOOLS = frozenset(
    {
        "send_can_frame",
        "transmit_j1939",
        "request_pgn",
        "write_channel",
        "inject_frame",
    }
)


def test_all_live_tools_registered() -> None:
    names = set(list_tool_names())
    assert names >= LIVE_TOOLS
    assert LIVE_TOOL_NAMES == LIVE_TOOLS


def test_read_only_tools_unchanged() -> None:
    assert len(READ_ONLY_TOOL_NAMES) == 24
    assert "list_sessions" in READ_ONLY_TOOL_NAMES
    assert "start_live_capture" not in READ_ONLY_TOOL_NAMES


def test_no_tx_tools_registered() -> None:
    names = set(list_tool_names())
    assert names.isdisjoint(FORBIDDEN_TX_TOOLS)


def test_device_status_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from canresearch.core.live_errors import LiveResearchError

    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.get_cansub_device_status",
        lambda *a, **k: (_ for _ in ()).throw(
            LiveResearchError("cansub_unreachable", "host down")
        ),
    )
    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.resolve_cansub_settings",
        lambda *a, **k: ("host", 5.0, False),
    )
    with pytest.raises(McpToolError) as exc:
        handle_get_cansub_device_status()
    assert exc.value.code == "cansub_unreachable"


def test_observe_limit_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.resolve_cansub_settings",
        lambda *a, **k: ("host", 5.0, False),
    )
    with pytest.raises(McpToolError) as exc:
        handle_observe_live_traffic(1, duration_seconds=100.0)
    assert exc.value.code == "limit_out_of_range"


def test_mark_event_invalid_session(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    initialize(db_path)
    with pytest.raises(McpToolError) as exc:
        handle_mark_experiment_event("missing", "baseline", db_path=db_path)
    assert exc.value.code == "capture_session_not_found"


def test_compare_windows_via_handler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.sqlite"
    initialize(db_path)
    from canresearch.core.session_events import add_session_event
    from canresearch.core.sessions import create_session

    session_id = "mcpcmp01"
    frames_path = tmp_path / "frames.jsonl"
    frame = {
        "timestamp_us": 1_000_000,
        "channel": 1,
        "can_id": 0x18FF748A,
        "extended": True,
        "fd": False,
        "rtr": False,
        "brs": False,
        "esi": False,
        "tx_ack": False,
        "dlc": 8,
        "data": "0102030405060708",
        "is_error_frame": False,
        "error_type": None,
    }
    frames_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")
    create_session(
        session_id=session_id,
        name=None,
        host="example.test",
        channel=1,
        device_id="dev",
        frame_store_path=str(frames_path),
        db_path=db_path,
    )
    add_session_event(session_id, "baseline_start", timestamp_us=1_000_000, db_path=db_path)
    add_session_event(session_id, "action", timestamp_us=1_000_000, db_path=db_path)

    result = handle_compare_experiment_windows(
        session_id,
        "baseline_start",
        "action",
        db_path=db_path,
    )
    assert result["session_id"] == session_id
    assert "top_changes" in result


def test_start_capture_duplicate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from canresearch.core.live_errors import LiveResearchError

    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.resolve_cansub_settings",
        lambda *a, **k: ("host", 5.0, False),
    )
    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.start_live_capture",
        lambda *a, **k: (_ for _ in ()).throw(
            LiveResearchError("capture_already_active", "busy")
        ),
    )
    with pytest.raises(McpToolError) as exc:
        handle_start_live_capture(1, db_path=tmp_path / "db.sqlite")
    assert exc.value.code == "capture_already_active"


def test_stop_capture_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    from canresearch.core.live_errors import LiveResearchError

    monkeypatch.setattr(
        "canresearch.mcp.live_handlers.stop_live_capture",
        lambda *a, **k: (_ for _ in ()).throw(
            LiveResearchError("capture_not_active", "none")
        ),
    )
    with pytest.raises(McpToolError) as exc:
        handle_stop_live_capture("sess001")
    assert exc.value.code == "capture_not_active"
