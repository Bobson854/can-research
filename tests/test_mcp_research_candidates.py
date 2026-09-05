"""MCP tests for read-only research candidate tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.research_candidates import (
    Signedness,
    confirm_candidate,
    create_research_candidate,
    mark_candidate_reviewed,
)
from canresearch.core.sessions import create_session
from canresearch.mcp.errors import McpToolError
from canresearch.mcp.research_candidate_handlers import (
    handle_get_research_candidate,
    handle_list_candidate_evidence,
    handle_list_research_candidates,
    handle_preview_research_dbc,
)
from canresearch.mcp.server import READ_ONLY_TOOL_NAMES, list_tool_names
from canresearch.storage.database import initialize

EXPECTED_CANDIDATE_TOOLS = frozenset(
    {
        "list_research_candidates",
        "get_research_candidate",
        "list_candidate_evidence",
        "preview_research_dbc",
    }
)


@pytest.fixture
def mcp_candidate_env(tmp_path: Path) -> dict[str, Path | str]:
    db_path = tmp_path / "test.db"
    frames_path = tmp_path / "frames.jsonl"
    frames_path.write_text("", encoding="utf-8")
    initialize(db_path)
    session_id = "mcp-cand-session"
    asset_key = "weedit_quadro_01"
    create_session(
        session_id=session_id,
        name="mcp-candidate",
        host="test.local",
        channel=1,
        device_id="test",
        frame_store_path=str(frames_path),
        db_path=db_path,
    )
    add_asset(
        asset_key=asset_key,
        asset_type="implement",
        display_name="Weedit Quadro",
        db_path=db_path,
    )
    link_session_asset(session_id, asset_key, role="implement", db_path=db_path)
    return {"db_path": db_path, "session_id": session_id, "asset_key": asset_key}


def test_candidate_tools_registered() -> None:
    assert frozenset(READ_ONLY_TOOL_NAMES) >= EXPECTED_CANDIDATE_TOOLS
    assert frozenset(list_tool_names()) >= EXPECTED_CANDIDATE_TOOLS
    forbidden = {
        "create_research_candidate",
        "confirm_research_candidate",
        "reject_research_candidate",
        "mark_candidate_reviewed",
    }
    assert forbidden.isdisjoint(list_tool_names())


def test_list_and_get_candidate(mcp_candidate_env: dict[str, Path | str]) -> None:
    created = create_research_candidate(
        asset_key=mcp_candidate_env["asset_key"],
        session_id=mcp_candidate_env["session_id"],
        can_id=0x18FF748A,
        start_bit=16,
        bit_length=16,
        byte_order="intel",
        db_path=mcp_candidate_env["db_path"],
    )
    listed = handle_list_research_candidates(
        asset_key=mcp_candidate_env["asset_key"],
        db_path=mcp_candidate_env["db_path"],
    )
    assert listed["count"] == 1
    got = handle_get_research_candidate(created.id, db_path=mcp_candidate_env["db_path"])
    assert got["candidate"]["id"] == created.id


def test_list_evidence(mcp_candidate_env: dict[str, Path | str]) -> None:
    created = create_research_candidate(
        asset_key=mcp_candidate_env["asset_key"],
        session_id=mcp_candidate_env["session_id"],
        can_id=0x18FF748A,
        start_bit=16,
        bit_length=16,
        byte_order="intel",
        db_path=mcp_candidate_env["db_path"],
    )
    from canresearch.core.research_candidates import add_candidate_evidence

    add_candidate_evidence(
        created.id,
        evidence_type="manual_note",
        evidence={"text": "note"},
        db_path=mcp_candidate_env["db_path"],
    )
    result = handle_list_candidate_evidence(created.id, db_path=mcp_candidate_env["db_path"])
    assert result["count"] == 1


def test_preview_research_dbc_bounded(mcp_candidate_env: dict[str, Path | str]) -> None:
    created = create_research_candidate(
        asset_key=mcp_candidate_env["asset_key"],
        session_id=mcp_candidate_env["session_id"],
        can_id=0x18FF748A,
        start_bit=16,
        bit_length=16,
        byte_order="intel",
        signedness=Signedness.UNSIGNED.value,
        db_path=mcp_candidate_env["db_path"],
    )
    mark_candidate_reviewed(created.id, db_path=mcp_candidate_env["db_path"])
    confirm_candidate(
        created.id,
        name="Pressure_Test",
        factor=0.1,
        offset=0.0,
        signedness=Signedness.UNSIGNED.value,
        unit="bar",
        db_path=mcp_candidate_env["db_path"],
    )

    preview = handle_preview_research_dbc(
        mcp_candidate_env["asset_key"],
        preview_lines=100,
        db_path=mcp_candidate_env["db_path"],
    )
    assert preview["confirmed_signal_count"] == 1
    assert preview["signal_count"] == 1
    assert "Pressure_Test" in preview["dbc_preview"]
    assert "..." not in preview["dbc_preview"]

    with pytest.raises(McpToolError) as exc:
        handle_preview_research_dbc(
            mcp_candidate_env["asset_key"],
            preview_lines=9999,
            db_path=mcp_candidate_env["db_path"],
        )
    assert exc.value.code == "limit_out_of_range"
