"""Tests for J1939 Address Claim discovery, persistence, and asset linkage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from canresearch.cli import main
from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.dbc_generation import generate_session_dbc
from canresearch.core.j1939_name import (
    PGN_ADDRESS_CLAIM,
    build_j1939_name_payload,
    parse_j1939_name_payload,
)
from canresearch.core.j1939_nodes import (
    discover_j1939_nodes,
    link_asset_node,
    list_asset_nodes,
    persist_session_nodes,
    resolve_source_addresses_for_asset,
    scan_session_j1939_nodes,
    unlink_asset_node,
)
from canresearch.core.j1939_tp import GLOBAL_DESTINATION, encode_j1939_can_id
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.storage.database import initialize


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


def _address_claim_line(
    *,
    source_address: int,
    identity_number: int = 456789,
    manufacturer_code: int = 123,
    function: int = 130,
    industry_group: int = 2,
    timestamp_us: int = 1_000_000,
) -> str:
    payload = build_j1939_name_payload(
        identity_number=identity_number,
        manufacturer_code=manufacturer_code,
        function=function,
        industry_group=industry_group,
    )
    can_id = encode_j1939_can_id(
        pgn=PGN_ADDRESS_CLAIM,
        source_address=source_address,
        destination_address=GLOBAL_DESTINATION,
    )
    return _frame_line(can_id=can_id, data=payload.hex(), timestamp_us=timestamp_us)


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
        name="nodes-test",
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


@pytest.fixture
def node_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.core.j1939_nodes.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.dbc_generation.default_db_path", lambda: db_path)
    initialize(db_path)
    return {"db_path": db_path, "root": tmp_path}


def _name_hex(**fields: int) -> str:
    payload = build_j1939_name_payload(**fields)
    return parse_j1939_name_payload(payload).name_hex


def _add_asset(db_path: Path, asset_key: str, asset_type: str, display_name: str) -> None:
    add_asset(
        asset_key=asset_key,
        asset_type=asset_type,
        display_name=display_name,
        db_path=db_path,
    )


def test_discover_single_address_claim(node_env) -> None:
    session_id = "oneclaim"
    lines = [
        _address_claim_line(source_address=0x80),
        _frame_line(can_id=0x0CF00480, data="0000000000000000"),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=False)
    assert result.stats.address_claim_frames == 1
    assert result.stats.unique_names == 1
    assert len(result.nodes) == 1
    assert result.nodes[0].latest_source_address == 0x80
    assert result.nodes[0].claim_count == 1


def test_repeated_claim_increments_count(node_env) -> None:
    session_id = "repeat"
    lines = [
        _address_claim_line(source_address=0x80, timestamp_us=1_000_000),
        _address_claim_line(source_address=0x80, timestamp_us=2_000_000),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    first = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    second = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    assert first.nodes[0].claim_count == 2
    assert second.nodes[0].claim_count == 4
    assert len(first.nodes[0].observations) == 1


def test_same_name_different_source_addresses(node_env) -> None:
    session_id = "sa_change"
    fields = dict(identity_number=100, manufacturer_code=200, function=130, industry_group=2)
    lines = [
        _address_claim_line(source_address=0x80, timestamp_us=1_000_000, **fields),
        _address_claim_line(source_address=0x90, timestamp_us=2_000_000, **fields),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    assert len(result.nodes) == 1
    assert len(result.nodes[0].observations) == 2
    assert result.nodes[0].latest_source_address == 0x90


def test_two_names_same_session(node_env) -> None:
    session_id = "twonodes"
    lines = [
        _address_claim_line(source_address=0x80, identity_number=1, manufacturer_code=10),
        _address_claim_line(source_address=0x81, identity_number=2, manufacturer_code=20),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=False)
    assert result.stats.unique_names == 2
    assert result.stats.unique_source_addresses == 2


def test_source_address_conflict_warning(node_env) -> None:
    session_id = "conflict"
    lines = [
        _address_claim_line(source_address=0x80, identity_number=1, manufacturer_code=10),
        _address_claim_line(source_address=0x80, identity_number=2, manufacturer_code=20),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=False)
    assert result.stats.address_conflicts == 1
    assert any(w.category == "source_address_conflict" for w in result.warnings)
    assert len(result.nodes) == 2


def test_cannot_claim_address(node_env) -> None:
    session_id = "cannot"
    lines = [_address_claim_line(source_address=0xFE)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    assert result.nodes[0].cannot_claim is True
    assert result.nodes[0].latest_source_address is None


def test_unrelated_traffic_ignored(node_env) -> None:
    session_id = "other"
    lines = [_frame_line(can_id=0x0CF00400, data="0000000000000000")]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)

    result = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=False)
    assert result.stats.address_claim_frames == 0
    assert result.nodes == ()


def test_persist_idempotent(node_env) -> None:
    session_id = "persist"
    lines = [_address_claim_line(source_address=0x80)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)

    first = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    second = scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    assert first.nodes[0].node_id == second.nodes[0].node_id
    conn = initialize(node_env["db_path"])
    count = conn.execute("SELECT COUNT(*) FROM j1939_nodes").fetchone()[0]
    conn.close()
    assert count == 1


def test_asset_node_link_and_list(node_env) -> None:
    session_id = "link"
    name_fields = dict(identity_number=42, manufacturer_code=275, function=130, industry_group=2)
    lines = [_address_claim_line(source_address=0x80, **name_fields)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)

    add_asset(
        asset_key="weedit_quadro_01",
        asset_type="implement",
        display_name="Weedit Quadro",
        db_path=node_env["db_path"],
    )
    name_hex = _name_hex(**name_fields)
    link_asset_node("weedit_quadro_01", name_hex, db_path=node_env["db_path"])
    nodes = list_asset_nodes("weedit_quadro_01", db_path=node_env["db_path"])
    assert len(nodes) == 1
    assert nodes[0].name.name_hex == name_hex


def test_duplicate_link_rejected(node_env) -> None:
    session_id = "duplink"
    name_fields = dict(identity_number=7, manufacturer_code=11, function=0, industry_group=2)
    lines = [_address_claim_line(source_address=0x80, **name_fields)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    name_hex = _name_hex(**name_fields)

    add_asset(
        asset_key="asset_a",
        asset_type="tractor",
        display_name="A",
        db_path=node_env["db_path"],
    )
    link_asset_node("asset_a", name_hex, db_path=node_env["db_path"])
    with pytest.raises(ValueError, match="already linked"):
        link_asset_node("asset_a", name_hex, db_path=node_env["db_path"])


def test_node_already_linked_to_other_asset(node_env) -> None:
    session_id = "otherasset"
    name_fields = dict(identity_number=8, manufacturer_code=12, function=0, industry_group=2)
    lines = [_address_claim_line(source_address=0x80, **name_fields)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    name_hex = _name_hex(**name_fields)

    _add_asset(node_env["db_path"], "asset_a", "tractor", "A")
    _add_asset(node_env["db_path"], "asset_b", "implement", "B")
    link_asset_node("asset_a", name_hex, db_path=node_env["db_path"])
    with pytest.raises(ValueError, match="already linked to another asset"):
        link_asset_node("asset_b", name_hex, db_path=node_env["db_path"])


def test_multiple_nodes_one_asset(node_env) -> None:
    session_id = "multi"
    fields_a = dict(identity_number=1, manufacturer_code=10, function=130, industry_group=2)
    fields_b = dict(identity_number=2, manufacturer_code=20, function=130, industry_group=2)
    lines = [
        _address_claim_line(source_address=0x00, **fields_a),
        _address_claim_line(source_address=0x80, **fields_b),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)

    _add_asset(node_env["db_path"], "jd_6155r_01", "tractor", "Tractor")
    link_asset_node("jd_6155r_01", _name_hex(**fields_a), db_path=node_env["db_path"])
    link_asset_node("jd_6155r_01", _name_hex(**fields_b), db_path=node_env["db_path"])
    resolved = resolve_source_addresses_for_asset(
        session_id,
        "jd_6155r_01",
        db_path=node_env["db_path"],
    )
    assert resolved.source_addresses == (0x00, 0x80)
    assert resolved.origin == "asset_node_resolution"
    assert len(resolved.j1939_names) == 2


def test_auto_sa_resolution_for_dbc(node_env, monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "autodbc"
    name_fields = dict(identity_number=99, manufacturer_code=275, function=130, industry_group=2)
    lines = [
        _address_claim_line(source_address=0x80, **name_fields),
        _frame_line(can_id=0x0CF00480, data="000000401f000000"),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    conn = initialize(node_env["db_path"])
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

    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    add_asset(
        asset_key="weedit_quadro_01",
        asset_type="implement",
        display_name="Implement",
        db_path=node_env["db_path"],
    )
    link_session_asset(
        session_id,
        "weedit_quadro_01",
        role="implement",
        db_path=node_env["db_path"],
    )
    link_asset_node(
        "weedit_quadro_01",
        _name_hex(**name_fields),
        db_path=node_env["db_path"],
    )

    summary = generate_session_dbc(
        session_id,
        asset_key="weedit_quadro_01",
        db_path=node_env["db_path"],
    )
    assert summary.messages_generated == 1
    assert summary.provenance is not None
    assert summary.provenance.source_address_origin == "asset_node_resolution"
    assert summary.provenance.source_addresses == (0x80,)


def test_manual_source_address_overrides_auto(node_env) -> None:
    session_id = "manual"
    name_fields = dict(identity_number=50, manufacturer_code=100, function=130, industry_group=2)
    lines = [
        _address_claim_line(source_address=0x80, **name_fields),
        _address_claim_line(source_address=0x81, identity_number=51, manufacturer_code=101),
        _frame_line(can_id=0x0CF00481, data="000000401f000000"),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=3)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)

    _add_asset(node_env["db_path"], "tractor", "tractor", "T")
    link_session_asset(session_id, "tractor", role="tractor", db_path=node_env["db_path"])
    link_asset_node("tractor", _name_hex(**name_fields), db_path=node_env["db_path"])

    conn = initialize(node_env["db_path"])
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
        VALUES (61444, 'EEC1', 'EEC1', ?, 'j1939_base_2001', 8)
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

    summary = generate_session_dbc(
        session_id,
        asset_key="tractor",
        source_addresses=(0x81,),
        db_path=node_env["db_path"],
    )
    assert summary.provenance is not None
    assert summary.provenance.source_address_origin == "manual"
    assert summary.provenance.source_addresses == (0x81,)


def test_no_resolution_fails_cleanly(node_env) -> None:
    session_id = "nores"
    lines = [_frame_line(can_id=0x0CF00400, data="0000000000000000")]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)

    _add_asset(node_env["db_path"], "orphan", "tractor", "Orphan")
    link_session_asset(session_id, "orphan", role="tractor", db_path=node_env["db_path"])

    with pytest.raises(ValueError, match="No J1939 nodes linked"):
        generate_session_dbc(session_id, asset_key="orphan", db_path=node_env["db_path"])


def test_cli_session_nodes(node_env, monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "clinodes"
    lines = [
        _address_claim_line(source_address=0x80, manufacturer_code=275, function=0),
        _address_claim_line(
            source_address=0x81,
            identity_number=2,
            manufacturer_code=123,
            function=130,
        ),
    ]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=2)

    monkeypatch.setattr("canresearch.core.j1939_nodes.default_db_path", lambda: node_env["db_path"])
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: node_env["db_path"])

    runner = CliRunner()
    result = runner.invoke(main, ["session", "nodes", session_id])
    assert result.exit_code == 0, result.output
    assert f"Session: {session_id}" in result.output
    assert "Observed J1939 nodes: 2" in result.output
    assert "275" in result.output
    assert "130" in result.output


def test_cli_asset_node_commands(node_env, monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "cliassetnode"
    name_fields = dict(identity_number=3, manufacturer_code=456, function=130, industry_group=2)
    lines = [_address_claim_line(source_address=0x81, **name_fields)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)

    monkeypatch.setattr("canresearch.core.j1939_nodes.default_db_path", lambda: node_env["db_path"])
    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: node_env["db_path"])
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: node_env["db_path"])

    _add_asset(node_env["db_path"], "jd_6155r_01", "tractor", "Tractor")
    name_hex = _name_hex(**name_fields)

    runner = CliRunner()
    scan = runner.invoke(main, ["session", "nodes", session_id])
    assert scan.exit_code == 0, scan.output

    add = runner.invoke(main, ["asset", "node", "add", "jd_6155r_01", name_hex])
    assert add.exit_code == 0, add.output

    listing = runner.invoke(main, ["asset", "node", "list", "jd_6155r_01"])
    assert listing.exit_code == 0, listing.output
    assert name_hex.upper() in listing.output.upper()

    remove = runner.invoke(main, ["asset", "node", "remove", "jd_6155r_01", name_hex])
    assert remove.exit_code == 0, remove.output

    empty = runner.invoke(main, ["asset", "node", "list", "jd_6155r_01"])
    assert "No J1939 nodes linked" in empty.output


def test_discover_in_memory_without_db(node_env) -> None:
    from canresearch.core.jsonl_capture_store import iter_frames_from_path

    session_id = "mem"
    lines = [_address_claim_line(source_address=0x80)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)
    result = discover_j1939_nodes(iter_frames_from_path(frames_path), session_id=session_id)
    persisted = persist_session_nodes(result, db_path=node_env["db_path"])
    assert persisted.nodes[0].node_id


def test_unlink_asset_node(node_env) -> None:
    session_id = "unlink"
    name_fields = dict(identity_number=4, manufacturer_code=1, function=0, industry_group=2)
    lines = [_address_claim_line(source_address=0x80, **name_fields)]
    frames_path = _write_session(node_env["root"], session_id, lines)
    _create_completed_session(node_env["db_path"], frames_path, session_id, frame_count=1)
    scan_session_j1939_nodes(session_id, db_path=node_env["db_path"], persist=True)
    name_hex = _name_hex(**name_fields)

    add_asset(asset_key="x", asset_type="tractor", display_name="X", db_path=node_env["db_path"])
    link_asset_node("x", name_hex, db_path=node_env["db_path"])
    unlink_asset_node("x", name_hex, db_path=node_env["db_path"])
    assert list_asset_nodes("x", db_path=node_env["db_path"]) == []
