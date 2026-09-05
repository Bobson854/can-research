"""Tests for offline J1939 SPN session decoding."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from canresearch.cli import main
from canresearch.core.session_decode import SessionDecoder, decode_session
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.storage.database import initialize


def _frame_line(
    *,
    can_id: int,
    data: str,
    timestamp_us: int = 1_000_000,
    extended: bool = True,
) -> str:
    payload = {
        "timestamp_us": timestamp_us,
        "channel": 1,
        "can_id": can_id,
        "extended": extended,
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
    name: str = "decode-test",
) -> None:
    started = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    stopped = datetime(2026, 3, 1, 12, 0, 10, tzinfo=UTC)
    create_session(
        name=name,
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


def _insert_decode_catalogue(
    db_path: Path,
    *,
    pgn: int,
    spn: int,
    start_byte: int,
    start_bit: int | None,
    bit_length: int,
    resolution: str,
    offset: str = "0",
    unit: str | None = None,
    data_type: str = "Measured",
    spn_name: str = "TestSPN",
    pgn_name: str = "TestPGN",
    acronym: str | None = None,
) -> None:
    conn = initialize(db_path)
    row = conn.execute(
        "SELECT id FROM reference_sources WHERE source_key = 'test-j1939-base'"
    ).fetchone()
    if row:
        source_id = int(row["id"])
    else:
        conn.execute(
            """
            INSERT INTO reference_sources (source_key, source_type, title, origin)
            VALUES ('test-j1939-base', 'test', 'Test J1939 Base', 'j1939_base_2001')
            """
        )
        source_id = int(conn.execute("SELECT id FROM reference_sources").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO reference_pgns (pgn, name, acronym, source_id, origin, payload_length)
        VALUES (?, ?, ?, ?, 'j1939_base_2001', 8)
        """,
        (pgn, pgn_name, acronym, source_id),
    )
    pgn_id = conn.execute("SELECT id FROM reference_pgns WHERE pgn = ?", (pgn,)).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_spns (
            spn, name, resolution, offset, unit, data_type, source_id, origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'j1939_base_2001')
        """,
        (spn, spn_name, resolution, offset, unit, data_type, source_id),
    )
    spn_id = conn.execute("SELECT id FROM reference_spns WHERE spn = ?", (spn,)).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgn_spns (
            pgn_id, spn_id, spn, start_byte, start_bit, bit_length, source_id, raw_position_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pgn_id,
            spn_id,
            spn,
            start_byte,
            start_bit,
            bit_length,
            source_id,
            (
                f"{start_byte}-{start_byte + (bit_length // 8) - 1}"
                if start_bit is None
                else f"{start_byte}.{start_bit}"
            ),
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def decode_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.core.session_decode.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.analysis.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: db_path)
    initialize(db_path)
    return {"db_path": db_path, "root": tmp_path}


def test_decode_eec1_engine_speed(decode_env) -> None:
    _insert_decode_catalogue(
        decode_env["db_path"],
        pgn=61444,
        spn=190,
        start_byte=4,
        start_bit=None,
        bit_length=16,
        resolution="0.125 rpm per bit",
        unit="rpm",
        spn_name="EngineSpeed",
        pgn_name="ElectronicEngineController1",
        acronym="EEC1",
    )
    session_id = "eec1sess"
    can_id = 0x0CF00400
    payload = "000000401f000000"
    lines = [_frame_line(can_id=can_id, data=payload)]
    frames_path = _write_session(decode_env["root"], session_id, lines)
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    summary = decode_session(session_id, db_path=decode_env["db_path"])
    assert summary.known_pgn_frames == 1
    assert summary.decoded_signal_count == 1
    signal = summary.decoded_signals[0]
    assert signal.spn == 190
    assert signal.raw_value == 8000
    assert signal.engineering_value == pytest.approx(1000.0)
    assert signal.unit == "rpm"


def test_decode_one_byte_scaled_value(decode_env) -> None:
    _insert_decode_catalogue(
        decode_env["db_path"],
        pgn=65089,
        spn=105,
        start_byte=1,
        start_bit=None,
        bit_length=8,
        resolution="1 deg C per bit",
        offset="-40",
        unit="deg C",
        spn_name="CoolantTemperature",
    )
    session_id = "tempsess"
    can_id = 0x18FE4100
    payload = "6400000000000000"
    lines = [_frame_line(can_id=can_id, data=payload)]
    frames_path = _write_session(decode_env["root"], session_id, lines)
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    summary = decode_session(session_id, db_path=decode_env["db_path"])
    assert summary.decoded_signal_count == 1
    signal = summary.decoded_signals[0]
    assert signal.raw_value == 0x64
    assert signal.engineering_value == pytest.approx(60.0)


def test_unknown_pgn_skipped(decode_env) -> None:
    session_id = "unknownsess"
    frames_path = _write_session(
        decode_env["root"],
        session_id,
        [_frame_line(can_id=0x18FDE800, data="0000000000000000")],
    )
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    summary = decode_session(session_id, db_path=decode_env["db_path"])
    assert summary.unknown_pgn_frames == 1
    assert summary.decoded_signal_count == 0


def test_malformed_mapping_warning(decode_env) -> None:
    conn = initialize(decode_env["db_path"])
    conn.execute(
        """
        INSERT INTO reference_sources (source_key, source_type, title, origin)
        VALUES ('test-j1939-base', 'test', 'Test J1939 Base', 'j1939_base_2001')
        """
    )
    source_id = conn.execute("SELECT id FROM reference_sources").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgns (pgn, name, source_id, origin)
        VALUES (65000, 'BrokenPGN', ?, 'j1939_base_2001')
        """,
        (source_id,),
    )
    pgn_id = conn.execute("SELECT id FROM reference_pgns").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_spns (spn, name, source_id, origin)
        VALUES (999, 'BrokenSPN', ?, 'j1939_base_2001')
        """,
        (source_id,),
    )
    spn_id = conn.execute("SELECT id FROM reference_spns").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgn_spns (pgn_id, spn_id, spn, source_id)
        VALUES (?, ?, 999, ?)
        """,
        (pgn_id, spn_id, source_id),
    )
    conn.commit()
    conn.close()

    session_id = "brokensess"
    frames_path = _write_session(
        decode_env["root"],
        session_id,
        [_frame_line(can_id=0x18FDE800, data="0000000000000000")],
    )
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    summary = decode_session(session_id, db_path=decode_env["db_path"])
    assert summary.decoded_signal_count == 0
    assert any(w.category == "incomplete_mapping" for w in summary.warnings)


def test_standard_frame_not_decoded(decode_env) -> None:
    session_id = "stdsess"
    frames_path = _write_session(
        decode_env["root"],
        session_id,
        [_frame_line(can_id=0x123, data="0000000000000000", extended=False)],
    )
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    summary = decode_session(session_id, db_path=decode_env["db_path"])
    assert summary.j1939_frames == 0
    assert summary.decoded_signal_count == 0


def test_edge101_proprietary_session_zero_decodes(decode_env) -> None:
    session_id = "edge101"
    ids = [0x18173201, 0x18667017, 0x18667117, 0x18667217, 0x18667317]
    lines = [
        _frame_line(can_id=can_id, data="0000000000000000", timestamp_us=index * 1_000_000)
        for index, can_id in enumerate(ids)
    ]
    frames_path = _write_session(decode_env["root"], session_id, lines)
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=len(ids))

    summary = SessionDecoder(decode_env["db_path"]).decode(session_id)
    assert summary.total_frames == 5
    assert summary.j1939_frames == 5
    assert summary.known_pgn_frames == 0
    assert summary.unknown_pgn_frames == 5
    assert summary.decoded_signal_count == 0


def test_cli_session_decode(decode_env, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_decode_catalogue(
        decode_env["db_path"],
        pgn=61444,
        spn=190,
        start_byte=4,
        start_bit=None,
        bit_length=16,
        resolution="0.125 rpm per bit",
        unit="rpm",
        spn_name="EngineSpeed",
    )
    session_id = "clidecode"
    frames_path = _write_session(
        decode_env["root"],
        session_id,
        [_frame_line(can_id=0x0CF00400, data="000000401f000000")],
    )
    _create_completed_session(decode_env["db_path"], frames_path, session_id, frame_count=1)

    monkeypatch.setattr(
        "canresearch.core.session_decode.default_db_path",
        lambda: decode_env["db_path"],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["session", "decode", session_id])
    assert result.exit_code == 0, result.output
    assert "Decoded signals:" in result.output
    assert "190" in result.output
    assert "1000" in result.output
