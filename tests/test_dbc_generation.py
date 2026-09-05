"""Tests for session-backed DBC generation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from canresearch.cli import main
from canresearch.core.assets import add_asset, link_session_asset
from canresearch.core.dbc_generation import generate_session_dbc
from canresearch.core.dbc_position import decode_intel_dbc_signal
from canresearch.core.dbc_writer import render_dbc
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.core.spn_bits import extract_raw_value
from canresearch.storage.database import initialize


def _frame_line(*, can_id: int, data: str) -> str:
    payload = {
        "timestamp_us": 1_000_000,
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
        name="dbc-test",
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


@pytest.fixture
def dbc_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.core.dbc_generation.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.analysis.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.assets.default_db_path", lambda: db_path)
    initialize(db_path)
    return {"db_path": db_path, "root": tmp_path}


def _register_test_asset(db_path: Path, session_id: str, asset_key: str = "test_asset") -> None:
    add_asset(
        asset_key=asset_key,
        asset_type="controller",
        display_name="Test Asset",
        db_path=db_path,
    )
    link_session_asset(session_id, asset_key, role="controller", db_path=db_path)


def test_generate_eec1_message_and_decode_equivalence(dbc_env) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "eec1dbc"
    can_id = 0x0CF00400
    payload = "000000401f000000"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=can_id, data=payload)],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    _register_test_asset(dbc_env["db_path"], session_id)

    summary = generate_session_dbc(
        session_id,
        asset_key="test_asset",
        db_path=dbc_env["db_path"],
    )
    assert summary.messages_generated == 1
    assert summary.signals_generated == 1

    message = summary.database.messages[0]
    signal = message.signals[0]
    assert message.can_id == can_id
    assert message.dbc_frame_id == 0x8CF00400
    assert signal.start_bit == 24
    assert signal.bit_length == 16
    assert signal.factor == 0.125
    assert signal.unit == "rpm"

    payload_bytes = bytes.fromhex(payload)
    j1939_raw = extract_raw_value(
        payload_bytes,
        start_byte=4,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
        signed=False,
    )
    dbc_raw = decode_intel_dbc_signal(
        payload_bytes,
        start_bit=signal.start_bit,
        bit_length=signal.bit_length,
        signed=signal.signed,
    )
    assert j1939_raw == dbc_raw == 8000


def test_unknown_pgn_not_generated(dbc_env) -> None:
    session_id = "unknownpgn"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=0x18FDE800, data="0000000000000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    _register_test_asset(dbc_env["db_path"], session_id)

    summary = generate_session_dbc(
        session_id,
        asset_key="test_asset",
        db_path=dbc_env["db_path"],
    )
    assert summary.messages_generated == 0
    assert summary.signals_generated == 0


def test_edge101_proprietary_session_generates_nothing(dbc_env) -> None:
    session_id = "edge101"
    ids = [0x18173201, 0x18667017, 0x18667117, 0x18667217, 0x18667317]
    lines = [_frame_line(can_id=can_id, data="0000000000000000") for can_id in ids]
    frames_path = _write_session(dbc_env["root"], session_id, lines)
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=len(ids))
    _register_test_asset(dbc_env["db_path"], session_id, asset_key="edge101_bench_01")

    summary = generate_session_dbc(
        session_id,
        asset_key="edge101_bench_01",
        db_path=dbc_env["db_path"],
    )
    assert summary.observed_j1939_pgns == 2
    assert summary.reference_backed_pgns == 0
    assert summary.messages_generated == 0
    assert summary.signals_generated == 0
    assert summary.asset_key == "edge101_bench_01"
    assert summary.provenance is not None
    assert summary.provenance.dbc_type == "reference_standard"


def test_deterministic_output(dbc_env) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "detdbc"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    _register_test_asset(dbc_env["db_path"], session_id)

    first = render_dbc(
        generate_session_dbc(
            session_id,
            asset_key="test_asset",
            db_path=dbc_env["db_path"],
        ).database
    )
    second = render_dbc(
        generate_session_dbc(
            session_id,
            asset_key="test_asset",
            db_path=dbc_env["db_path"],
        ).database
    )
    assert first == second
    assert 'CM_ "Asset: test_asset"' in first


def test_signal_overlap_skips_second_mapping(dbc_env) -> None:
    conn = initialize(dbc_env["db_path"])
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
        VALUES (65000, 'Example', 'EXA', ?, 'j1939_base_2001', 8)
        """,
        (source_id,),
    )
    pgn_id = conn.execute("SELECT id FROM reference_pgns").fetchone()["id"]
    for spn, start_byte, start_bit, bit_length in ((100, 4, None, 16), (101, 4, None, 16)):
        conn.execute(
            """
            INSERT INTO reference_spns (
                spn, name, resolution, offset, unit, data_type, source_id, origin
            ) VALUES (?, ?, '1 unit/bit, 0 offset', '0', 'unit', 'Measured', ?, 'j1939_base_2001')
            """,
            (spn, f"Signal{spn}", source_id),
        )
        row = conn.execute("SELECT id FROM reference_spns WHERE spn = ?", (spn,)).fetchone()
        spn_id = row["id"]
        conn.execute(
            """
            INSERT INTO reference_pgn_spns (
                pgn_id, spn_id, spn, start_byte, start_bit, bit_length, source_id, raw_position_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '4-5')
            """,
            (pgn_id, spn_id, spn, start_byte, start_bit, bit_length, source_id),
        )
    conn.commit()
    conn.close()

    session_id = "overlap"
    can_id = 0x18FDE800
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=can_id, data="0000000000000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    _register_test_asset(dbc_env["db_path"], session_id)

    summary = generate_session_dbc(
        session_id,
        asset_key="test_asset",
        db_path=dbc_env["db_path"],
    )
    assert summary.messages_generated == 1
    assert summary.signals_generated == 1
    assert summary.signals_skipped == 1
    assert summary.warning_counts.get("signal_overlap") == 1


def test_cli_session_dbc(dbc_env, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "clidbc"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    _register_test_asset(dbc_env["db_path"], session_id)
    output = dbc_env["root"] / "machine.dbc"

    monkeypatch.setattr(
        "canresearch.core.dbc_generation.default_db_path",
        lambda: dbc_env["db_path"],
    )
    monkeypatch.setattr(
        "canresearch.core.assets.default_db_path",
        lambda: dbc_env["db_path"],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["session", "dbc", session_id, "--asset", "test_asset", "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    assert "Asset:                   test_asset" in result.output
    assert "DBC messages generated:" in result.output
    assert "EngineSpeed" in output.read_text(encoding="ascii")
    assert 'CM_ "Asset: test_asset"' in output.read_text(encoding="ascii")


def test_dbc_requires_linked_asset(dbc_env) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "nolink"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    add_asset(
        asset_key="orphan_asset",
        asset_type="tractor",
        display_name="Unlinked Tractor",
        db_path=dbc_env["db_path"],
    )

    with pytest.raises(ValueError, match="not linked"):
        generate_session_dbc(
            session_id,
            asset_key="orphan_asset",
            db_path=dbc_env["db_path"],
        )


def test_source_address_filter(dbc_env) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "safilter"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [
            _frame_line(can_id=0x0CF00400, data="000000401f000000"),
            _frame_line(can_id=0x0CF00480, data="000000401f000000"),
        ],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=2)
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=dbc_env["db_path"],
    )
    add_asset(
        asset_key="weedit_quadro_01",
        asset_type="implement",
        display_name="Implement",
        db_path=dbc_env["db_path"],
    )
    link_session_asset(session_id, "jd_6155r_01", role="tractor", db_path=dbc_env["db_path"])
    link_session_asset(session_id, "weedit_quadro_01", role="implement", db_path=dbc_env["db_path"])

    tractor = generate_session_dbc(
        session_id,
        asset_key="jd_6155r_01",
        source_addresses=(0x00,),
        db_path=dbc_env["db_path"],
    )
    implement = generate_session_dbc(
        session_id,
        asset_key="weedit_quadro_01",
        source_addresses=(0x80,),
        db_path=dbc_env["db_path"],
    )
    assert tractor.messages_generated == 1
    assert implement.messages_generated == 1
    assert tractor.database.messages[0].source_address == 0x00
    assert implement.database.messages[0].source_address == 0x80
    assert tractor.provenance.source_addresses == (0x00,)
    assert implement.provenance.source_addresses == (0x80,)

    with pytest.raises(ValueError, match="not observed"):
        generate_session_dbc(
            session_id,
            asset_key="jd_6155r_01",
            source_addresses=(0x99,),
            db_path=dbc_env["db_path"],
        )


def test_default_output_filename(dbc_env, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_eec1_catalogue(dbc_env["db_path"])
    session_id = "defaultname"
    frames_path = _write_session(
        dbc_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(dbc_env["db_path"], frames_path, session_id, frame_count=1)
    add_asset(
        asset_key="jd_6155r_01",
        asset_type="tractor",
        display_name="Tractor",
        db_path=dbc_env["db_path"],
    )
    link_session_asset(session_id, "jd_6155r_01", role="tractor", db_path=dbc_env["db_path"])

    monkeypatch.setattr(
        "canresearch.core.dbc_generation.default_db_path",
        lambda: dbc_env["db_path"],
    )
    monkeypatch.setattr(
        "canresearch.core.assets.default_db_path",
        lambda: dbc_env["db_path"],
    )
    monkeypatch.chdir(dbc_env["root"])

    runner = CliRunner()
    result = runner.invoke(main, ["session", "dbc", session_id, "--asset", "jd_6155r_01"])
    assert result.exit_code == 0, result.output
    output = dbc_env["root"] / "jd_6155r_01_standard.dbc"
    assert output.exists()
    assert "Written:" in result.output
