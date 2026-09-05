"""MCP registration tests for signal research tools."""

from __future__ import annotations

import pytest

from canresearch.mcp.errors import McpToolError
from canresearch.mcp.server import SIGNAL_RESEARCH_TOOL_NAMES, list_tool_names
from canresearch.mcp.signal_research_handlers import handle_rank_signal_candidates

EXPECTED = frozenset(
    {
        "rank_signal_candidates",
        "analyze_can_id_activity",
        "analyze_repeated_action",
        "detect_counters",
        "detect_checksums",
        "correlate_candidate_field",
    }
)

FORBIDDEN = frozenset(
    {
        "confirm_signal",
        "write_research_dbc",
        "add_dbc_signal",
        "send_can_frame",
    }
)


def test_signal_research_tools_registered() -> None:
    names = set(list_tool_names())
    assert SIGNAL_RESEARCH_TOOL_NAMES == EXPECTED
    assert names >= EXPECTED
    assert names.isdisjoint(FORBIDDEN)


def test_rank_handler_session_not_found(tmp_path) -> None:
    from canresearch.storage.database import initialize

    db = tmp_path / "db.sqlite"
    initialize(db)
    with pytest.raises(McpToolError) as exc:
        handle_rank_signal_candidates(
            "missing",
            "baseline",
            "action",
            db_path=db,
        )
    assert exc.value.code in {"capture_session_not_found", "event_not_found"}
