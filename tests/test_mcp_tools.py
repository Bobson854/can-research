"""Tests for read-only MCP tool handlers and registration."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.j1939_name import (
    PGN_ADDRESS_CLAIM,
    build_j1939_name_payload,
    parse_j1939_name_payload,
)
from canresearch.core.j1939_nodes import link_asset_node, scan_session_j1939_nodes
from canresearch.core.j1939_tp import (
    GLOBAL_DESTINATION,
    build_tp_cm_bam,
    build_tp_dt,
    encode_j1939_can_id,
)
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.mcp.errors import McpToolError
from canresearch.mcp.handlers import (
    handle_analyze_session,
    handle_build_session_dbc_preview,
    handle_decode_session,
    handle_get_session,
    handle_inspect_transport,
    handle_list_assets,
    handle_list_session_nodes,
    handle_list_sessions,
    handle_lookup_pgn,
    handle_lookup_spn,
)
from canresearch.mcp.server import (
    LIVE_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    create_server,
    list_tool_names,
)
from canresearch.storage.database import initialize

EXPECTED_TOOLS = frozenset(
    {
        "list_sessions",
        "get_session",
        "analyze_session",
        "decode_session",
        "inspect_transport",
        "list_session_nodes",
        "list_assets",
        "get_asset",
        "list_asset_nodes",
        "lookup_pgn",
        "lookup_spn",
        "build_session_dbc_preview",
        "list_research_candidates",
        "get_research_candidate",
        "list_candidate_evidence",
        "preview_research_dbc",
        "list_session_events",
        "preview_candidate_values",
    }
)

FORBIDDEN_MUTATION_TOOLS = frozenset(
    {
        "asset_add",
        "asset_node_add",
        "asset_node_remove",
        "session_asset_add",
        "session_asset_remove",
        "capture_start",
        "capture_stop",
        "reference_import",
        "dbc_write",
    }
)


def _frame_line(*, can_id: int, data: str, timestamp_us: int = 1_000_000) -> str:
    payload = {
        "timestamp_us": timestamp_us,
        "channel": 1,
        "can_id": can_id,
        "extended": True,
        "fd": False,
        "rtr": False,
        "brs": False,
        "esi": False,
        "tx_ack": False,
        "dlc": 8,
        "data": data,
        "is_error_frame": False,
        "error_type": None,
    }
    return json.dumps(payload, separators=(",", ":"))


def _write_session(root: Path, session_id: str, lines: list[str]) -> Path:
    frames_path = root / "sessions" / session_id / "frames.jsonl"
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frames_path


def _create_completed_session(
    db_path: Path,
    frames_path: Path,
    session_id: str,
    *,
    frame_count: int,
) -> None:
    started = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    stopped = datetime(2026, 3, 1, 12, 0, 10, tzinfo=UTC)
    create_session(
        name="mcp-test",
        host="127.0.0.1",
        channel=1,
        device_id="abcd1234",
        frame_store_path=str(frames_path),
        db_path=db_path,
        session_id=session_id,
    )
    finalize_session(
        session_id,
        status=SessionStatus.COMPLETED,
        frame_count=frame_count,
        stopped_at=stopped,
        db_path=db_path,
    )
    conn = initialize(db_path)
    conn.execute(
        "UPDATE sessions SET started_at = ? WHERE id = ?",
        (started.isoformat(), session_id),
    )
    conn.commit()
    conn.close()


def _insert_eec1_catalogue(db_path: Path) -> None:
    conn = initialize(db_path)
    conn.execute(
        """
        INSERT INTO reference_sources (source_key, source_type, title, origin)
        VALUES ('test-j1939-base', 'test', 'Test J1939 Base', 'j1939_base_2001')
        """
    )
    source_id = conn.execute("SELECT id FROM reference_sources").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgns (pgn, name, acronym, source_id, origin, payload_length)
        VALUES (61444, 'Electronic Engine Controller 1', 'EEC1', ?, 'j1939_base_2001', 8)
        """,
        (source_id,),
    )
    pgn_id = conn.execute("SELECT id FROM reference_pgns WHERE pgn = 61444").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_spns (
            spn, name, resolution, offset, unit, data_type, source_id, origin
        ) VALUES (190, 'EngineSpeed', '0.125 rpm per bit', '0', 'rpm', 'Measured', ?,
                  'j1939_base_2001')
        """,
        (source_id,),
    )
    spn_id = conn.execute("SELECT id FROM reference_spns WHERE spn = 190").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgn_spns (
            pgn_id, spn_id, spn, start_byte, start_bit, bit_length, source_id, raw_position_text
        ) VALUES (?, ?, 190, 4, NULL, 16, ?, '4-5')
        """,
        (pgn_id, spn_id, source_id),
    )
    conn.commit()
    conn.close()


def _address_claim_line(*, source_address: int, identity_number: int = 42) -> str:
    payload = build_j1939_name_payload(
        identity_number=identity_number,
        manufacturer_code=275,
        function=130,
        industry_group=2,
    )
    can_id = encode_j1939_can_id(
        pgn=PGN_ADDRESS_CLAIM,
        source_address=source_address,
        destination_address=GLOBAL_DESTINATION,
    )
    return _frame_line(can_id=can_id, data=payload.hex())


@pytest.fixture
def mcp_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.storage.database.default_db_path", lambda: db_path)
    initialize(db_path)
    return {"db_path": db_path, "root": tmp_path}


EXPECTED_LIVE_TOOLS = frozenset(
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

EXPECTED_SIGNAL_RESEARCH_TOOLS = frozenset(
    {
        "rank_signal_candidates",
        "analyze_can_id_activity",
        "analyze_repeated_action",
        "detect_counters",
        "detect_checksums",
        "correlate_candidate_field",
    }
)


def test_expected_tools_registered() -> None:
    all_tools = frozenset(list_tool_names())
    assert READ_ONLY_TOOL_NAMES == EXPECTED_TOOLS
    assert LIVE_TOOL_NAMES == EXPECTED_LIVE_TOOLS
    assert all_tools == EXPECTED_TOOLS | EXPECTED_LIVE_TOOLS | EXPECTED_SIGNAL_RESEARCH_TOOLS
    assert FORBIDDEN_MUTATION_TOOLS.isdisjoint(all_tools)


def test_async_tool_list_matches() -> None:
    server = create_server()

    async def _list() -> list[str]:
        tools = await server.list_tools()
        return sorted(tool.name for tool in tools)

    assert asyncio.run(_list()) == sorted(list_tool_names())


def test_list_and_get_session(mcp_env) -> None:
    session_id = "mcp001"
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="0000000000000000")],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=1)

    listed = handle_list_sessions(db_path=mcp_env["db_path"])
    assert listed["returned_count"] == 1
    assert listed["sessions"][0]["session_id"] == session_id
    assert listed["sessions"][0]["capture_source"] == "cansub2"

    detail = handle_get_session(session_id, db_path=mcp_env["db_path"])
    assert detail["session"]["frame_count"] == 1
    assert detail["linked_assets"] == []


def test_get_session_not_found(mcp_env) -> None:
    with pytest.raises(McpToolError) as exc:
        handle_get_session("missing", db_path=mcp_env["db_path"])
    assert exc.value.code == "session_not_found"


def test_analyze_session_structure(mcp_env) -> None:
    session_id = "mcpanalyze"
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [
            _address_claim_line(source_address=0x80),
            _frame_line(can_id=0x0CF00480, data="000000401f000000"),
        ],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=2)

    result = handle_analyze_session(session_id, db_path=mcp_env["db_path"], limit=10)
    assert result["frames_examined"] == 2
    assert result["identity"]["address_claim_frames"] >= 1
    assert result["observed_returned_count"] <= 10
    assert "transport" in result


def test_decode_eec1(mcp_env) -> None:
    _insert_eec1_catalogue(mcp_env["db_path"])
    session_id = "mcpdecode"
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=1)

    result = handle_decode_session(session_id, db_path=mcp_env["db_path"], spn=190)
    assert result["returned_count"] == 1
    signal = result["signals"][0]
    assert signal["spn"] == 190
    assert signal["engineering_value"] == 1000.0
    assert signal["unit"] == "rpm"


def test_decode_limit_out_of_range(mcp_env) -> None:
    session_id = "mcplimit"
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="0000000000000000")],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=1)

    with pytest.raises(McpToolError) as exc:
        handle_decode_session(session_id, db_path=mcp_env["db_path"], limit=0)
    assert exc.value.code == "limit_out_of_range"


def test_inspect_transport_bam(mcp_env) -> None:
    session_id = "mcptp"
    payload = bytes.fromhex("0102030405060708090a")
    packet_count = (len(payload) + 6) // 7
    cm_id, cm_data = build_tp_cm_bam(
        total_size=len(payload),
        packet_count=packet_count,
        transported_pgn=65000,
        source_address=0x80,
    )
    lines = [_frame_line(can_id=cm_id, data=cm_data.hex())]
    for seq in range(1, packet_count + 1):
        chunk = payload[(seq - 1) * 7 : seq * 7]
        dt_id, dt_data = build_tp_dt(
            sequence=seq,
            payload_chunk=chunk,
            source_address=0x80,
            destination_address=GLOBAL_DESTINATION,
        )
        lines.append(
            _frame_line(
                can_id=dt_id,
                data=dt_data.hex(),
                timestamp_us=1_000_000 + seq * 1000,
            )
        )
    frames_path = _write_session(mcp_env["root"], session_id, lines)
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=len(lines))

    hidden = handle_inspect_transport(session_id, db_path=mcp_env["db_path"])
    assert hidden["transfers_completed"] >= 1
    assert "payload_hex" not in hidden["completed_messages"][0]

    shown = handle_inspect_transport(
        session_id,
        db_path=mcp_env["db_path"],
        show_payload=True,
    )
    assert "payload_hex" in shown["completed_messages"][0]


def test_list_session_nodes_with_asset_link(mcp_env) -> None:
    session_id = "mcpnodes"
    name_fields = dict(identity_number=99, manufacturer_code=275, function=130, industry_group=2)
    payload = build_j1939_name_payload(**name_fields)
    name_hex = parse_j1939_name_payload(payload).name_hex
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [_address_claim_line(source_address=0x80, identity_number=99)],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=1)
    scan_session_j1939_nodes(session_id, db_path=mcp_env["db_path"], persist=True)
    add_asset(
        asset_key="tractor_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=mcp_env["db_path"],
    )
    link_asset_node("tractor_01", name_hex, db_path=mcp_env["db_path"])

    result = handle_list_session_nodes(session_id, db_path=mcp_env["db_path"])
    assert result["returned_count"] == 1
    assert result["nodes"][0]["asset_key"] == "tractor_01"
    assert result["nodes"][0]["manufacturer_code"] == 275


def test_reference_lookups(mcp_env) -> None:
    _insert_eec1_catalogue(mcp_env["db_path"])
    pgn_result = handle_lookup_pgn(61444, db_path=mcp_env["db_path"])
    assert pgn_result["pgn"] == 61444
    assert pgn_result["mapping_count"] >= 1

    spn_result = handle_lookup_spn(190, db_path=mcp_env["db_path"])
    assert spn_result["spn"] == 190
    assert spn_result["mapping_count"] >= 1

    with pytest.raises(McpToolError) as exc:
        handle_lookup_pgn(99999, db_path=mcp_env["db_path"])
    assert exc.value.code == "invalid_pgn"


def test_dbc_preview_no_file_write(mcp_env, tmp_path: Path) -> None:
    _insert_eec1_catalogue(mcp_env["db_path"])
    session_id = "mcpdbc"
    name_fields = dict(identity_number=7, manufacturer_code=275, function=130, industry_group=2)
    payload = build_j1939_name_payload(**name_fields)
    name_hex = parse_j1939_name_payload(payload).name_hex
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [
            _address_claim_line(source_address=0x80, identity_number=7),
            _frame_line(can_id=0x0CF00480, data="000000401f000000"),
        ],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=2)
    scan_session_j1939_nodes(session_id, db_path=mcp_env["db_path"], persist=True)
    add_asset(
        asset_key="implement_01",
        asset_type="implement",
        display_name="Implement",
        db_path=mcp_env["db_path"],
    )
    link_session_asset(session_id, "implement_01", role="implement", db_path=mcp_env["db_path"])
    link_asset_node("implement_01", name_hex, db_path=mcp_env["db_path"])

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    before = list(output_dir.glob("*.dbc"))

    auto = handle_build_session_dbc_preview(
        session_id,
        "implement_01",
        db_path=mcp_env["db_path"],
        preview_lines=20,
    )
    assert auto["messages"] == 1
    assert auto["source_address_origin"] == "asset_node_resolution"
    assert auto["preview_truncated"] is True
    assert "VERSION" in auto["dbc_preview"]
    assert list(output_dir.glob("*.dbc")) == before

    manual = handle_build_session_dbc_preview(
        session_id,
        "implement_01",
        source_addresses=[0x80],
        db_path=mcp_env["db_path"],
    )
    assert manual["source_addresses"] == [0x80]


def test_dbc_preview_no_source_resolution(mcp_env) -> None:
    _insert_eec1_catalogue(mcp_env["db_path"])
    session_id = "mcpdbcfail"
    frames_path = _write_session(
        mcp_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(mcp_env["db_path"], frames_path, session_id, frame_count=1)
    add_asset(
        asset_key="orphan",
        asset_type="tractor",
        display_name="Orphan",
        db_path=mcp_env["db_path"],
    )
    link_session_asset(session_id, "orphan", role="tractor", db_path=mcp_env["db_path"])

    with pytest.raises(McpToolError) as exc:
        handle_build_session_dbc_preview(
            session_id,
            "orphan",
            db_path=mcp_env["db_path"],
        )
    assert exc.value.code == "no_source_addresses_resolved"


def test_list_assets(mcp_env) -> None:
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=mcp_env["db_path"],
    )
    result = handle_list_assets(db_path=mcp_env["db_path"])
    assert result["returned_count"] == 1
    assert result["assets"][0]["asset_key"] == "jd_6155r_01"
