"""Tests for offline J1939 session analysis."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from canresearch.cli import main
from canresearch.core.analysis import (
    SessionAnalyzer,
    analyze_session,
    classify_pgn,
)
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.references.service import ReferenceService
from canresearch.storage.database import initialize


def _frame_line(
    *,
    can_id: int | None,
    extended: bool = True,
    timestamp_us: int = 1_000_000,
    rtr: bool = False,
    is_error: bool = False,
) -> str:
    payload = {
        "timestamp_us": timestamp_us,
        "channel": 1,
        "can_id": can_id,
        "extended": extended,
        "fd": False,
        "rtr": rtr,
        "brs": False,
        "esi": False,
        "tx_ack": False,
        "dlc": 8,
        "data": "0000000000000000",
        "is_error_frame": is_error,
        "error_type": "bus_error" if is_error else None,
    }
    return json.dumps(payload, separators=(",", ":"))


def _write_session(
    tmp_path: Path,
    session_id: str,
    lines: list[str],
    *,
    name: str = "test-session",
) -> Path:
    frames_path = tmp_path / "sessions" / session_id / "frames.jsonl"
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frames_path


def _create_completed_session(
    db_path: Path,
    frames_path: Path,
    session_id: str,
    *,
    frame_count: int,
    name: str = "test-session",
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


def _insert_reference_pgn(
    db_path: Path,
    *,
    pgn: int,
    origin: str,
    name: str,
    acronym: str | None = None,
    source_key: str | None = None,
) -> None:
    conn = initialize(db_path)
    service = ReferenceService(conn)
    key = source_key or f"source-{origin}-{pgn}"
    source_id = service.ensure_source(
        source_key=key,
        source_type="test",
        title=f"Test {origin}",
        revision="1",
        coverage_date="2001",
        origin=origin,
    )
    conn.execute(
        """
        INSERT INTO reference_pgns (
            pgn, name, acronym, source_id, origin
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (pgn, name, acronym, source_id, origin),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def analysis_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    initialize(db_path)
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def test_pdu1_parse_and_destination(analysis_env) -> None:
    session_id = "pdu1sess"
    can_id = 0x18EAFF21
    root = analysis_env["sessions_dir"].parent
    frames_path = _write_session(root, session_id, [_frame_line(can_id=can_id)])
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.j1939_frames == 1
    assert len(summary.observed) == 1
    item = summary.observed[0]
    assert item.pgn == 0xEA00
    assert item.source_address == 0x21
    assert item.destination_address == 0xFF
    assert item.is_pdu1 is True


def test_pdu2_no_destination(analysis_env) -> None:
    session_id = "pdu2sess"
    can_id = 0x0CFEF100
    root = analysis_env["sessions_dir"].parent
    frames_path = _write_session(root, session_id, [_frame_line(can_id=can_id)])
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    item = summary.observed[0]
    assert item.pgn == 0xFEF1
    assert item.destination_address is None
    assert item.is_pdu1 is False


def test_aggregate_by_pgn_and_source(analysis_env) -> None:
    session_id = "aggsess"
    can_id = 0x0CF00400
    lines = [
        _frame_line(can_id=can_id, timestamp_us=1_000_000),
        _frame_line(can_id=can_id, timestamp_us=2_000_000),
        _frame_line(can_id=can_id, timestamp_us=3_000_000),
    ]
    frames_path = _write_session(analysis_env["sessions_dir"].parent, session_id, lines)
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=3)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.j1939_frames == 3
    assert len(summary.observed) == 1
    assert summary.observed[0].frame_count == 3
    assert summary.observed[0].first_timestamp_us == 1_000_000
    assert summary.observed[0].last_timestamp_us == 3_000_000


def test_pdu1_separate_destination_buckets(analysis_env) -> None:
    session_id = "pdu1da"
    lines = [
        _frame_line(can_id=0x18EAFF21),
        _frame_line(can_id=0x18EAFE21),
    ]
    frames_path = _write_session(analysis_env["sessions_dir"].parent, session_id, lines)
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=2)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert len(summary.observed) == 2
    destinations = {item.destination_address for item in summary.observed}
    assert destinations == {0xFF, 0xFE}


def test_standard_frame_counted_non_j1939(analysis_env) -> None:
    session_id = "stdsess"
    lines = [
        _frame_line(can_id=0x123, extended=False),
        _frame_line(can_id=0x18EAFF21),
    ]
    frames_path = _write_session(analysis_env["sessions_dir"].parent, session_id, lines)
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=2)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.total_frames == 2
    assert summary.non_j1939_frames == 1
    assert summary.j1939_frames == 1


def test_malformed_and_error_frames(analysis_env) -> None:
    session_id = "badsess"
    lines = [
        _frame_line(can_id=None),
        _frame_line(can_id=0x20000000),
        _frame_line(can_id=0x18EAFF21, is_error=True),
        _frame_line(can_id=0x18EAFF21),
    ]
    frames_path = _write_session(analysis_env["sessions_dir"].parent, session_id, lines)
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=4)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.total_frames == 4
    assert summary.malformed_frames == 2
    assert summary.error_frames == 1
    assert summary.j1939_frames == 1


def test_known_j1939_base_lookup(analysis_env) -> None:
    session_id = "knownsess"
    can_id = 0x0CF00400  # EEC1 PGN 61444, SA 0
    _insert_reference_pgn(
        analysis_env["db_path"],
        pgn=61444,
        origin="j1939_base_2001",
        name="Electronic Engine Controller 1",
        acronym="EEC1",
    )
    frames_path = _write_session(
        analysis_env["sessions_dir"].parent,
        session_id,
        [_frame_line(can_id=can_id)],
    )
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    item = summary.observed[0]
    assert item.pgn == 61444
    assert item.classification == "j1939_base_2001"
    assert item.display_name == "EEC1"
    assert summary.known_pgn_count == 1
    assert summary.unknown_pgn_count == 0


def test_additive_source_lookup(analysis_env) -> None:
    session_id = "addsess"
    pgn = 65000
    can_id = 0x18FDE800
    _insert_reference_pgn(
        analysis_env["db_path"],
        pgn=pgn,
        origin="j1939_addition",
        name="Added PGN",
        source_key="add-source",
    )
    frames_path = _write_session(
        analysis_env["sessions_dir"].parent,
        session_id,
        [_frame_line(can_id=can_id)],
    )
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.observed[0].classification == "j1939_addition"


def test_unknown_pgn(analysis_env) -> None:
    session_id = "unknownsess"
    can_id = 0x18FDE800
    frames_path = _write_session(
        analysis_env["sessions_dir"].parent,
        session_id,
        [_frame_line(can_id=can_id)],
    )
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    summary = analyze_session(session_id, db_path=analysis_env["db_path"])
    assert summary.observed[0].classification == "unknown"
    assert summary.unknown_pgn_count == 1


def test_origin_precedence_prefers_base(analysis_env) -> None:
    pgn = 61444
    _insert_reference_pgn(
        analysis_env["db_path"],
        pgn=pgn,
        origin="j1939_base_2001",
        name="Base Name",
        acronym="EEC1",
        source_key="base-src",
    )
    _insert_reference_pgn(
        analysis_env["db_path"],
        pgn=pgn,
        origin="j1939_addition",
        name="Addition Name",
        source_key="add-src",
    )
    conn = initialize(analysis_env["db_path"])
    classification, display_name, matches = classify_pgn(pgn, ReferenceService(conn))
    conn.close()
    assert classification == "j1939_base_2001"
    assert display_name == "EEC1"
    assert len(matches) == 2


def test_persist_observed_pgns_idempotent(analysis_env) -> None:
    session_id = "persist01"
    lines = [
        _frame_line(can_id=0x18EAFF21, timestamp_us=1_000_000),
        _frame_line(can_id=0x18EAFF21, timestamp_us=2_000_000),
    ]
    frames_path = _write_session(analysis_env["sessions_dir"].parent, session_id, lines)
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=2)

    analyze_session(session_id, db_path=analysis_env["db_path"])
    analyze_session(session_id, db_path=analysis_env["db_path"])

    conn = initialize(analysis_env["db_path"])
    rows = conn.execute(
        "SELECT frame_count FROM observed_pgns WHERE session_id = ?",
        (session_id,),
    ).fetchall()
    status = conn.execute("SELECT status FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["frame_count"] == 2
    assert status["status"] == SessionStatus.ANALYZED.value


def test_cli_session_analyze(analysis_env, monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "clisess01"
    _insert_reference_pgn(
        analysis_env["db_path"],
        pgn=61444,
        origin="j1939_base_2001",
        name="Electronic Engine Controller 1",
        acronym="EEC1",
    )
    frames_path = _write_session(
        analysis_env["sessions_dir"].parent,
        session_id,
        [_frame_line(can_id=0x0CF00400)],
    )
    _create_completed_session(analysis_env["db_path"], frames_path, session_id, frame_count=1)

    monkeypatch.setattr(
        "canresearch.core.analysis.default_db_path",
        lambda: analysis_env["db_path"],
    )
    monkeypatch.setattr(
        "canresearch.core.sessions.default_db_path",
        lambda: analysis_env["db_path"],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["session", "analyze", session_id])
    assert result.exit_code == 0, result.output
    assert "J1939 frames:" in result.output
    assert "61444" in result.output
    assert "EEC1" in result.output


def test_edge101_style_ids_parse(analysis_env) -> None:
    session_id = "edge101"
    root = analysis_env["sessions_dir"].parent
    ids = [0x18173201, 0x18667017, 0x18667117, 0x18667217, 0x18667317]
    lines = [
        _frame_line(can_id=can_id, timestamp_us=index * 1_000_000)
        for index, can_id in enumerate(ids)
    ]
    frames_path = _write_session(root, session_id, lines)
    _create_completed_session(
        analysis_env["db_path"],
        frames_path,
        session_id,
        frame_count=len(ids),
    )

    summary = SessionAnalyzer(analysis_env["db_path"]).analyze(session_id, persist=False)
    assert summary.j1939_frames == 5
    assert summary.unique_pgns == 2
    pgns = {item.pgn for item in summary.observed}
    assert 5888 in pgns  # PDU1 PF=0x17
    assert 26112 in pgns  # PDU1 PF=0x66 group
