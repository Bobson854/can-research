"""Tests for J1939 transport-protocol reassembly."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from canresearch.core.analysis import analyze_session
from canresearch.core.j1939_tp import (
    DEFAULT_TRANSPORT_TIMEOUT_US,
    GLOBAL_DESTINATION,
    build_tp_cm_abort,
    build_tp_cm_bam,
    build_tp_cm_cts,
    build_tp_cm_eom,
    build_tp_cm_rts,
    build_tp_dt,
    encode_j1939_can_id,
    reassemble_j1939_transport,
)
from canresearch.core.session_decode import decode_session
from canresearch.core.sessions import CanFrame, SessionStatus, create_session, finalize_session
from canresearch.core.spn_bits import extract_raw_value
from canresearch.storage.database import initialize


def _frame(
    can_id: int,
    data: bytes,
    *,
    timestamp_us: int = 1_000_000,
) -> CanFrame:
    return CanFrame(
        timestamp_us=timestamp_us,
        channel=1,
        can_id=can_id,
        is_extended=True,
        fd=False,
        rtr=False,
        brs=False,
        esi=False,
        tx_ack=False,
        dlc=8,
        data=data,
        is_error_frame=False,
        error_type=None,
    )


def _bam_frames(
    *,
    source_address: int,
    transported_pgn: int,
    payload: bytes,
    timestamp_us: int = 1_000_000,
    step_us: int = 10_000,
) -> list[CanFrame]:
    packet_count = (len(payload) + 6) // 7
    cm_id, cm_data = build_tp_cm_bam(
        total_size=len(payload),
        packet_count=packet_count,
        transported_pgn=transported_pgn,
        source_address=source_address,
    )
    frames = [_frame(cm_id, cm_data, timestamp_us=timestamp_us)]
    ts = timestamp_us + step_us
    for seq in range(1, packet_count + 1):
        chunk = payload[(seq - 1) * 7 : seq * 7]
        dt_id, dt_data = build_tp_dt(
            sequence=seq,
            payload_chunk=chunk,
            source_address=source_address,
            destination_address=GLOBAL_DESTINATION,
        )
        frames.append(_frame(dt_id, dt_data, timestamp_us=ts))
        ts += step_us
    return frames


def _rts_cts_frames(
    *,
    sender: int,
    receiver: int,
    transported_pgn: int,
    payload: bytes,
    timestamp_us: int = 1_000_000,
    step_us: int = 10_000,
    include_eom: bool = True,
    max_packets_per_cts: int = 0xFF,
) -> list[CanFrame]:
    packet_count = (len(payload) + 6) // 7
    frames: list[CanFrame] = []
    ts = timestamp_us
    rts_id, rts_data = build_tp_cm_rts(
        total_size=len(payload),
        packet_count=packet_count,
        transported_pgn=transported_pgn,
        source_address=sender,
        destination_address=receiver,
        max_packets_per_cts=max_packets_per_cts,
    )
    frames.append(_frame(rts_id, rts_data, timestamp_us=ts))
    ts += step_us

    next_seq = 1
    while next_seq <= packet_count:
        window = min(max_packets_per_cts, packet_count - next_seq + 1)
        cts_id, cts_data = build_tp_cm_cts(
            packets_to_send=window,
            next_sequence=next_seq,
            transported_pgn=transported_pgn,
            source_address=receiver,
            destination_address=sender,
        )
        frames.append(_frame(cts_id, cts_data, timestamp_us=ts))
        ts += step_us
        for seq in range(next_seq, next_seq + window):
            chunk = payload[(seq - 1) * 7 : seq * 7]
            dt_id, dt_data = build_tp_dt(
                sequence=seq,
                payload_chunk=chunk,
                source_address=sender,
                destination_address=receiver,
            )
            frames.append(_frame(dt_id, dt_data, timestamp_us=ts))
            ts += step_us
        next_seq += window

    if include_eom:
        eom_id, eom_data = build_tp_cm_eom(
            total_size=len(payload),
            packet_count=packet_count,
            transported_pgn=transported_pgn,
            source_address=receiver,
            destination_address=sender,
        )
        frames.append(_frame(eom_id, eom_data, timestamp_us=ts))
    return frames


def test_bam_two_packet_reassembly() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    result = reassemble_j1939_transport(
        _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload)
    )
    assert result.stats.transfers_completed == 1
    assert len(result.completed_messages) == 1
    message = result.completed_messages[0]
    assert message.payload == payload
    assert message.transported_pgn == 65226
    assert message.transport_mode.value == "BAM"
    assert message.packet_count == 2


def test_bam_final_packet_trimmed() -> None:
    payload = bytes.fromhex("0102030405")
    result = reassemble_j1939_transport(
        _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    )
    assert result.completed_messages[0].payload == payload


def test_bam_with_interleaved_unrelated_frame() -> None:
    payload = bytes.fromhex("0102030405")
    frames = _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    unrelated_id = encode_j1939_can_id(pgn=61444, source_address=0x00, destination_address=0xFF)
    frames.insert(2, _frame(unrelated_id, bytes(8), timestamp_us=1_050_000))
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 1
    assert result.completed_messages[0].payload == payload


def test_two_concurrent_bam_transfers() -> None:
    payload_a = bytes.fromhex("AABBCCDDEEFF010203")
    payload_b = bytes.fromhex("11223344")
    frames_a = _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload_a)
    frames_b = _bam_frames(source_address=0x80, transported_pgn=65259, payload=payload_b)
    interleaved: list[CanFrame] = []
    for left, right in zip(frames_a, frames_b, strict=False):
        interleaved.extend([left, right])
    interleaved.extend(frames_a[len(frames_b) :])
    result = reassemble_j1939_transport(interleaved)
    assert result.stats.transfers_completed == 2
    payloads = {msg.source_address: msg.payload for msg in result.completed_messages}
    assert payloads[0x00] == payload_a
    assert payloads[0x80] == payload_b


def test_missing_packet_incomplete() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload)
    frames = [frame for frame in frames if frame.data[0] != 2]
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 0
    assert result.stats.transfers_incomplete == 1
    assert any(w.category == "incomplete_transport" for w in result.warnings)


def test_wrong_first_sequence_invalidates() -> None:
    payload = bytes.fromhex("0102030405")
    frames = _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    frames[-1] = _frame(
        frames[-1].can_id,
        bytes([2]) + frames[-1].data[1:],
        timestamp_us=frames[-1].timestamp_us,
    )
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 0
    assert any(w.category == "unexpected_sequence" for w in result.warnings)


def test_duplicate_identical_packet_ignored() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload)
    frames.insert(2, frames[1])
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 1
    assert any(w.category == "duplicate_packet" for w in result.warnings)


def test_conflicting_duplicate_invalidates() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload)
    bad = _frame(
        frames[1].can_id,
        bytes([1, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
        timestamp_us=frames[1].timestamp_us + 1,
    )
    frames.insert(2, bad)
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 0
    assert any(w.category == "conflicting_duplicate_packet" for w in result.warnings)


def test_transport_timeout_closes_stale_transfer() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    frames = frames[:2]
    later = _bam_frames(
        source_address=0x00,
        transported_pgn=65100,
        payload=bytes.fromhex("AABBCC"),
        timestamp_us=frames[-1].timestamp_us + DEFAULT_TRANSPORT_TIMEOUT_US + 1,
    )
    result = reassemble_j1939_transport(frames + later)
    assert result.stats.transfers_incomplete == 1
    assert result.stats.transfers_completed == 1
    assert any(w.category == "transport_timeout" for w in result.warnings)
    assert result.completed_messages[0].transported_pgn == 65100


def test_transport_abort() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _bam_frames(source_address=0x00, transported_pgn=65226, payload=payload)
    frames = frames[:2]
    abort_id, abort_data = build_tp_cm_abort(
        reason=2,
        transported_pgn=65226,
        source_address=0x00,
        destination_address=GLOBAL_DESTINATION,
    )
    frames.append(_frame(abort_id, abort_data, timestamp_us=1_050_000))
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 0
    assert result.stats.transfers_aborted == 1
    assert any(w.category == "transport_abort" for w in result.warnings)


def test_rts_cts_complete_with_eom() -> None:
    payload = bytes.fromhex("0102030405060708090A")
    frames = _rts_cts_frames(
        sender=0x00,
        receiver=0x80,
        transported_pgn=65226,
        payload=payload,
    )
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 1
    message = result.completed_messages[0]
    assert message.payload == payload
    assert message.transport_mode.value == "RTS_CTS"
    assert message.destination_address == 0x80


def test_rts_cts_missing_eom_completes_with_warning() -> None:
    payload = bytes.fromhex("0102030405")
    frames = _rts_cts_frames(
        sender=0x00,
        receiver=0x80,
        transported_pgn=65226,
        payload=payload,
        include_eom=False,
    )
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 1
    assert any(w.category == "missing_eom_ack" for w in result.warnings)


def test_rts_cts_multi_window() -> None:
    payload = bytes.fromhex("0102030405060708090A0B0C0D0E")
    frames = _rts_cts_frames(
        sender=0x00,
        receiver=0x80,
        transported_pgn=65226,
        payload=payload,
        max_packets_per_cts=2,
    )
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 1
    assert result.completed_messages[0].payload == payload


def test_invalid_packet_count_rejected() -> None:
    payload = bytes.fromhex("0102030405")
    frames = _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    bad_data = bytearray(frames[0].data)
    bad_data[3] = 99
    frames[0] = _frame(frames[0].can_id, bytes(bad_data), timestamp_us=frames[0].timestamp_us)
    result = reassemble_j1939_transport(frames)
    assert result.stats.transfers_completed == 0
    assert any(w.category == "invalid_packet_count" for w in result.warnings)


def test_deterministic_output() -> None:
    payload = bytes.fromhex("0102030405")
    frames = _bam_frames(source_address=0x00, transported_pgn=65000, payload=payload)
    first = reassemble_j1939_transport(frames)
    second = reassemble_j1939_transport(frames)
    assert first.completed_messages[0].payload == second.completed_messages[0].payload
    assert [w.category for w in first.warnings] == [w.category for w in second.warnings]


def test_extract_beyond_eight_bytes() -> None:
    payload = bytes(8) + bytes([0x00, 0x40])
    raw = extract_raw_value(
        payload,
        start_byte=9,
        start_bit=None,
        bit_length=16,
        byte_order="intel",
        signed=False,
    )
    assert raw == 0x4000


@pytest.fixture
def tp_decode_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.core.session_decode.default_db_path", lambda: db_path)
    monkeypatch.setattr("canresearch.core.analysis.default_db_path", lambda: db_path)
    initialize(db_path)
    return {"db_path": db_path, "root": tmp_path}


def _frame_line(*, can_id: int, data: str, timestamp_us: int = 1_000_000) -> str:
    return json.dumps(
        {
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
        },
        separators=(",", ":"),
    )


def _insert_transport_pgn_catalogue(db_path: Path, *, pgn: int = 65001) -> None:
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
        VALUES (?, 'Transport Test', 'TPT', ?, 'j1939_base_2001', 10)
        """,
        (pgn, source_id),
    )
    pgn_id = conn.execute("SELECT id FROM reference_pgns WHERE pgn = ?", (pgn,)).fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_spns (
            spn, name, resolution, offset, unit, data_type, source_id, origin
        ) VALUES (900, 'LateField', '1 unit/bit, 0 offset', '0', 'unit', 'Measured', ?,
                  'j1939_base_2001')
        """,
        (source_id,),
    )
    spn_id = conn.execute("SELECT id FROM reference_spns WHERE spn = 900").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO reference_pgn_spns (
            pgn_id, spn_id, spn, start_byte, start_bit, bit_length, source_id, raw_position_text
        ) VALUES (?, ?, 900, 9, NULL, 16, ?, '9-10')
        """,
        (pgn_id, spn_id, source_id),
    )
    conn.commit()
    conn.close()


def test_decoder_transport_message_beyond_byte_eight(tp_decode_env) -> None:
    transported_pgn = 65001
    _insert_transport_pgn_catalogue(tp_decode_env["db_path"], pgn=transported_pgn)
    payload = bytes(8) + bytes([0x00, 0x40])
    frames = _bam_frames(source_address=0x00, transported_pgn=transported_pgn, payload=payload)
    session_id = "tpdecode"
    frames_path = tp_decode_env["root"] / "sessions" / session_id / "frames.jsonl"
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _frame_line(can_id=frame.can_id, data=frame.data.hex(), timestamp_us=frame.timestamp_us)
        for frame in frames
    ]
    frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    started = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    stopped = datetime(2026, 3, 1, 12, 0, 10, tzinfo=UTC)
    create_session(
        name="tp-decode",
        host="127.0.0.1",
        channel=1,
        device_id="abcd1234",
        frame_store_path=str(frames_path),
        db_path=tp_decode_env["db_path"],
        session_id=session_id,
    )
    finalize_session(
        session_id,
        status=SessionStatus.COMPLETED,
        frame_count=len(lines),
        stopped_at=stopped,
        db_path=tp_decode_env["db_path"],
    )
    conn = initialize(tp_decode_env["db_path"])
    conn.execute(
        "UPDATE sessions SET started_at = ? WHERE id = ?",
        (started.isoformat(), session_id),
    )
    conn.commit()
    conn.close()

    summary = decode_session(session_id, db_path=tp_decode_env["db_path"])
    assert summary.transport_messages_decoded == 1
    assert summary.decoded_signal_count == 1
    assert summary.decoded_signals[0].spn == 900
    assert summary.decoded_signals[0].raw_value == 0x4000


def test_analysis_raw_counts_unchanged_with_transport_stats(tp_decode_env) -> None:
    transported_pgn = 65001
    payload = bytes.fromhex("0102030405")
    frames = _bam_frames(source_address=0x00, transported_pgn=transported_pgn, payload=payload)
    session_id = "tpanalyze"
    frames_path = tp_decode_env["root"] / "sessions" / session_id / "frames.jsonl"
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _frame_line(can_id=frame.can_id, data=frame.data.hex(), timestamp_us=frame.timestamp_us)
        for frame in frames
    ]
    frames_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    create_session(
        name="tp-analyze",
        host="127.0.0.1",
        channel=1,
        device_id="abcd1234",
        frame_store_path=str(frames_path),
        db_path=tp_decode_env["db_path"],
        session_id=session_id,
    )
    finalize_session(
        session_id,
        status=SessionStatus.COMPLETED,
        frame_count=len(lines),
        db_path=tp_decode_env["db_path"],
    )

    summary = analyze_session(session_id, db_path=tp_decode_env["db_path"], persist=False)
    assert summary.total_frames == len(lines)
    assert summary.j1939_frames == len(lines)
    assert summary.transport_tp_cm_frames == 1
    assert summary.transport_tp_dt_frames == 1
    assert summary.transport_transfers_completed == 1
    assert summary.completed_transport_pgns[0].transported_pgn == transported_pgn
