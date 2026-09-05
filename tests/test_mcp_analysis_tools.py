"""Tests for list_session_events and preview_candidate_values MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from canresearch.core.candidate_preview import preview_candidate_field_values
from canresearch.core.session_events import add_session_event, list_session_events
from canresearch.core.sessions import create_session
from canresearch.mcp.errors import McpToolError
from canresearch.mcp.handlers import handle_list_session_events, handle_preview_candidate_values
from canresearch.mcp.server import READ_ONLY_TOOL_NAMES, list_tool_names
from canresearch.storage.database import initialize
from tests.fixtures.synthetic_proprietary import (
    PRESSURE_SCALE,
    SYNTHETIC_CAN_ID,
    build_payload,
    write_synthetic_session,
)

NEW_READ_ONLY_TOOLS = frozenset({"list_session_events", "preview_candidate_values"})


@pytest.fixture
def analysis_env(tmp_path: Path) -> dict[str, Path | str]:
    db_path = tmp_path / "test.db"
    frames_path = tmp_path / "frames.jsonl"
    initialize(db_path)
    session_id = "analysis-session"
    create_session(
        session_id=session_id,
        name="analysis",
        host="test.local",
        channel=1,
        device_id="test",
        frame_store_path=str(frames_path),
        db_path=db_path,
    )
    return {"db_path": db_path, "session_id": session_id, "frames_path": frames_path}


def test_new_tools_registered_read_only() -> None:
    assert frozenset(READ_ONLY_TOOL_NAMES) >= NEW_READ_ONLY_TOOLS
    assert frozenset(list_tool_names()) >= NEW_READ_ONLY_TOOLS
    forbidden = {
        "create_research_candidate",
        "confirm_research_candidate",
        "reject_research_candidate",
        "mark_candidate_reviewed",
        "send_can_frame",
    }
    assert forbidden.isdisjoint(list_tool_names())


class TestListSessionEvents:
    def test_empty_list(self, analysis_env: dict[str, Path | str]) -> None:
        result = handle_list_session_events(
            analysis_env["session_id"],
            db_path=analysis_env["db_path"],
        )
        assert result["count"] == 0
        assert result["events"] == []

    def test_multiple_events_sorted(self, analysis_env: dict[str, Path | str]) -> None:
        db = analysis_env["db_path"]
        sid = analysis_env["session_id"]
        add_session_event(sid, "second", timestamp_us=2_000_000, notes="b", db_path=db)
        add_session_event(sid, "first", timestamp_us=1_000_000, notes="a", db_path=db)
        add_session_event(sid, "third", timestamp_us=2_000_000, notes="c", db_path=db)

        events = list_session_events(sid, db_path=db)
        labels = [event.label for event in events]
        assert labels == ["first", "second", "third"]
        assert events[1].notes == "b"
        assert events[2].notes == "c"

    def test_limit_bounds(self, analysis_env: dict[str, Path | str]) -> None:
        db = analysis_env["db_path"]
        sid = analysis_env["session_id"]
        for index in range(5):
            add_session_event(sid, f"evt_{index}", timestamp_us=index * 1_000_000, db_path=db)

        result = handle_list_session_events(sid, limit=2, db_path=db)
        assert result["count"] == 2
        assert [event["label"] for event in result["events"]] == ["evt_0", "evt_1"]

        with pytest.raises(McpToolError) as exc:
            handle_list_session_events(sid, limit=0, db_path=db)
        assert exc.value.code == "limit_out_of_range"

    def test_missing_session(self, analysis_env: dict[str, Path | str]) -> None:
        with pytest.raises(McpToolError) as exc:
            handle_list_session_events("missing", db_path=analysis_env["db_path"])
        assert exc.value.code == "session_not_found"


class TestPreviewCandidateValues:
    @pytest.fixture
    def synth_env(self, tmp_path: Path) -> dict[str, Path | str]:
        db_path = tmp_path / "test.db"
        frames_path = tmp_path / "frames.jsonl"
        initialize(db_path)
        session_id = "synth-preview"
        meta = write_synthetic_session(
            session_id=session_id,
            db_path=db_path,
            frames_path=frames_path,
        )
        return {"db_path": db_path, "session_id": session_id, **meta}

    def test_intel_unsigned_pressure(self, synth_env: dict[str, Path | str]) -> None:
        result = preview_candidate_field_values(
            synth_env["session_id"],
            can_id=SYNTHETIC_CAN_ID,
            is_extended=True,
            start_bit=16,
            bit_length=16,
            byte_order="intel",
            signedness="unsigned",
            factor=PRESSURE_SCALE,
            offset=0.0,
            db_path=synth_env["db_path"],
        )
        assert result["matching_frame_count"] > 0
        assert result["raw_min"] is not None
        assert result["raw_max"] is not None
        assert result["scaled_min"] == pytest.approx(result["raw_min"] * PRESSURE_SCALE)
        assert result["samples"][0]["scaled"] is not None

    def test_signed_extraction(self, analysis_env: dict[str, Path | str]) -> None:
        frames_path = analysis_env["frames_path"]
        payload = build_payload(counter=1, pressure_raw=0, action_on=False)
        payload = bytearray(payload)
        payload[0] = 0xFE
        line = {
            "timestamp_us": 1_000_000,
            "channel": 1,
            "can_id": 0x200,
            "extended": False,
            "fd": False,
            "rtr": False,
            "dlc": 8,
            "data": bytes(payload).hex().upper(),
        }
        frames_path.write_text(json.dumps(line) + "\n", encoding="utf-8")

        result = preview_candidate_field_values(
            analysis_env["session_id"],
            can_id=0x200,
            is_extended=False,
            start_bit=0,
            bit_length=8,
            byte_order="intel",
            signedness="signed",
            db_path=analysis_env["db_path"],
        )
        assert result["raw_min"] == -2

    def test_standard_vs_extended_isolation(self, analysis_env: dict[str, Path | str]) -> None:
        shared = 0x123
        frames_path = analysis_env["frames_path"]
        lines = []
        for index, (extended, byte0) in enumerate([(False, 0x11), (True, 0x22)]):
            lines.append(
                json.dumps(
                    {
                        "timestamp_us": (index + 1) * 1_000_000,
                        "channel": 1,
                        "can_id": shared,
                        "extended": extended,
                        "fd": False,
                        "rtr": False,
                        "dlc": 8,
                        "data": bytes([byte0, 0, 0, 0, 0, 0, 0, 0]).hex().upper(),
                    }
                )
            )
        frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        std = preview_candidate_field_values(
            analysis_env["session_id"],
            can_id=shared,
            is_extended=False,
            start_bit=0,
            bit_length=8,
            byte_order="intel",
            signedness="unsigned",
            db_path=analysis_env["db_path"],
        )
        ext = preview_candidate_field_values(
            analysis_env["session_id"],
            can_id=shared,
            is_extended=True,
            start_bit=0,
            bit_length=8,
            byte_order="intel",
            signedness="unsigned",
            db_path=analysis_env["db_path"],
        )
        assert std["matching_frame_count"] == 1
        assert ext["matching_frame_count"] == 1
        assert std["raw_min"] == 0x11
        assert ext["raw_min"] == 0x22

    def test_invalid_field_bounds(self, analysis_env: dict[str, Path | str]) -> None:
        analysis_env["frames_path"].write_text("", encoding="utf-8")
        with pytest.raises(McpToolError) as exc:
            handle_preview_candidate_values(
                analysis_env["session_id"],
                can_id=0x100,
                is_extended=False,
                start_bit=60,
                bit_length=8,
                byte_order="intel",
                signedness="unsigned",
                db_path=analysis_env["db_path"],
            )
        assert exc.value.code == "invalid_field_definition"

    def test_motorola_whole_bytes(self, analysis_env: dict[str, Path | str]) -> None:
        frames_path = analysis_env["frames_path"]
        data = bytes([0x00, 0x12, 0x34, 0, 0, 0, 0, 0])
        line = {
            "timestamp_us": 1_000_000,
            "channel": 1,
            "can_id": 0x300,
            "extended": False,
            "fd": False,
            "rtr": False,
            "dlc": 8,
            "data": data.hex().upper(),
        }
        frames_path.write_text(json.dumps(line) + "\n", encoding="utf-8")

        result = preview_candidate_field_values(
            analysis_env["session_id"],
            can_id=0x300,
            is_extended=False,
            start_bit=15,
            bit_length=16,
            byte_order="motorola",
            signedness="unsigned",
            db_path=analysis_env["db_path"],
        )
        assert result["raw_min"] == 0x1234

    def test_no_matching_frames(self, analysis_env: dict[str, Path | str]) -> None:
        analysis_env["frames_path"].write_text("", encoding="utf-8")
        result = preview_candidate_field_values(
            analysis_env["session_id"],
            can_id=0x999,
            is_extended=True,
            start_bit=0,
            bit_length=8,
            byte_order="intel",
            signedness="unsigned",
            db_path=analysis_env["db_path"],
        )
        assert result["matching_frame_count"] == 0
        assert result["samples"] == []
        assert result["raw_min"] is None

    def test_preview_limit_and_deterministic(self, synth_env: dict[str, Path | str]) -> None:
        first = preview_candidate_field_values(
            synth_env["session_id"],
            can_id=SYNTHETIC_CAN_ID,
            is_extended=True,
            start_bit=16,
            bit_length=16,
            byte_order="intel",
            signedness="unsigned",
            limit=10,
            db_path=synth_env["db_path"],
        )
        second = preview_candidate_field_values(
            synth_env["session_id"],
            can_id=SYNTHETIC_CAN_ID,
            is_extended=True,
            start_bit=16,
            bit_length=16,
            byte_order="intel",
            signedness="unsigned",
            limit=10,
            db_path=synth_env["db_path"],
        )
        assert first["samples"] == second["samples"]
        assert first["sampled_value_count"] == 10

        with pytest.raises(McpToolError) as exc:
            handle_preview_candidate_values(
                synth_env["session_id"],
                can_id=SYNTHETIC_CAN_ID,
                is_extended=True,
                start_bit=16,
                bit_length=16,
                byte_order="intel",
                signedness="unsigned",
                limit=999,
                db_path=synth_env["db_path"],
            )
        assert exc.value.code == "limit_out_of_range"

    def test_factor_offset_both_required(self, synth_env: dict[str, Path | str]) -> None:
        with pytest.raises(McpToolError) as exc:
            handle_preview_candidate_values(
                synth_env["session_id"],
                can_id=SYNTHETIC_CAN_ID,
                is_extended=True,
                start_bit=16,
                bit_length=16,
                byte_order="intel",
                signedness="unsigned",
                factor=0.1,
                db_path=synth_env["db_path"],
            )
        assert exc.value.code == "invalid_field_definition"
