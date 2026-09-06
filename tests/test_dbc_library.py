"""Tests for DBC library, registry, lookup, and coverage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from canresearch.core.dbc_coverage import analyze_dbc_coverage
from canresearch.core.dbc_knowledge import DbcLoadError, DbcSourceNotFoundError
from canresearch.core.dbc_lookup import lookup_message_by_can_id, lookup_signal_by_name
from canresearch.core.dbc_model import DbcDatabase, DbcMessage, DbcSignal
from canresearch.core.dbc_position import encode_dbc_extended_id
from canresearch.core.dbc_reader import decode_dbc_frame_id, read_dbc_file
from canresearch.core.dbc_registry import list_dbc_source_meta, load_dbc_source, register_dbc_source
from canresearch.core.dbc_writer import write_dbc
from canresearch.core.sessions import SessionStatus, create_session, finalize_session
from canresearch.mcp.dbc_handlers import handle_analyze_dbc_coverage, handle_list_dbc_sources
from canresearch.storage.database import initialize


def _sample_database() -> DbcDatabase:
    return DbcDatabase(
        version="test",
        nodes=("Vector__XXX",),
        messages=(
            DbcMessage(
                name="EEC1_SA00",
                can_id=0x0CF00400,
                dbc_frame_id=encode_dbc_extended_id(0x0CF00400),
                dlc=8,
                transmitter="Vector__XXX",
                pgn=61444,
                source_address=0,
                destination_address=None,
                origin="test",
                signals=(
                    DbcSignal(
                        name="EngineSpeed",
                        start_bit=24,
                        bit_length=16,
                        byte_order=1,
                        signed=False,
                        factor=0.125,
                        offset=0,
                        minimum=0,
                        maximum=8031.875,
                        unit="rpm",
                        pgn=61444,
                        spn=190,
                        origin="test",
                    ),
                ),
            ),
            DbcMessage(
                name="ProprietaryMsg",
                can_id=0x18667217,
                dbc_frame_id=encode_dbc_extended_id(0x18667217),
                dlc=8,
                transmitter="Vector__XXX",
                pgn=0,
                source_address=0,
                destination_address=None,
                origin="test",
                signals=(
                    DbcSignal(
                        name="FanSpeed",
                        start_bit=32,
                        bit_length=16,
                        byte_order=1,
                        signed=False,
                        factor=1.0,
                        offset=0,
                        minimum=0,
                        maximum=65535,
                        unit="rpm",
                        pgn=0,
                        spn=0,
                        origin="test",
                    ),
                ),
            ),
        ),
    )


def _frame_line(*, can_id: int, extended: bool = True, dlc: int = 8) -> str:
    payload = {
        "timestamp_us": 1_000_000,
        "channel": 1,
        "can_id": can_id,
        "extended": extended,
        "fd": False,
        "rtr": False,
        "brs": False,
        "esi": False,
        "tx_ack": False,
        "dlc": dlc,
        "data": "0000000000000000",
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
    frame_count: int,
) -> None:
    stopped = datetime(2026, 3, 1, 12, 0, 10, tzinfo=UTC)
    create_session(
        name="dbc-lib-test",
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


def test_decode_dbc_frame_id_extended_and_standard() -> None:
    can_id, ext = decode_dbc_frame_id(0x8CF00400)
    assert ext is True
    assert can_id == 0x0CF00400
    can_id, ext = decode_dbc_frame_id(0x123)
    assert ext is False
    assert can_id == 0x123


def test_read_and_roundtrip_dbc(tmp_path: Path) -> None:
    source = tmp_path / "sample.dbc"
    write_dbc(_sample_database(), source)
    database, warnings = read_dbc_file(source)
    assert len(database.messages) == 2
    assert database.messages[0].name == "EEC1_SA00"
    assert len(database.messages[0].signals) == 1
    assert warnings == ()


def test_malformed_dbc_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.dbc"
    path.write_text(
        ' SG_ orphan : 0|8@1+ (1,0) [0|0] "" Vector__XXX\n',
        encoding="utf-8",
    )
    with pytest.raises(DbcLoadError):
        read_dbc_file(path)


def test_register_list_and_load_dbc_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)
    source = tmp_path / "external.dbc"
    write_dbc(_sample_database(), source)
    entry = register_dbc_source(key="bench_dbc", path=source, display_name="Bench DBC")
    assert entry.key == "bench_dbc"
    metas = list_dbc_source_meta()
    assert len(metas) == 1
    loaded = load_dbc_source("bench_dbc")
    assert loaded.meta.message_count == 2
    assert loaded.meta.signal_count == 2


def test_lookup_message_and_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)
    source = tmp_path / "external.dbc"
    write_dbc(_sample_database(), source)
    register_dbc_source(key="lookup_test", path=source)
    loaded = load_dbc_source("lookup_test")
    by_id = lookup_message_by_can_id((loaded,), can_id=0x18667217, is_extended=True)
    assert len(by_id) == 1
    assert by_id[0].message.name == "ProprietaryMsg"
    by_signal = lookup_signal_by_name((loaded,), "EngineSpeed")
    assert len(by_signal) == 1
    assert by_signal[0].signal.unit == "rpm"


def test_session_dbc_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "references" / "canresearch.db"
    initialize(db_path)
    monkeypatch.setattr("canresearch.config.resolve_data_dir", lambda: data_dir)
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)

    session_id = "covsess01"
    frames = [
        _frame_line(can_id=0x0CF00400),
        _frame_line(can_id=0x0CF00400),
        _frame_line(can_id=0x18667217),
        _frame_line(can_id=0x18FFFF00),
    ]
    frames_path = _write_session(data_dir, session_id, frames)
    _create_completed_session(db_path, frames_path, session_id, frame_count=4)

    source = tmp_path / "lib.dbc"
    write_dbc(_sample_database(), source)
    register_dbc_source(key="cov_dbc", path=source)

    summary = analyze_dbc_coverage(session_id, db_path=db_path)
    assert summary.unique_ids_observed == 3
    assert summary.unique_ids_covered == 2
    assert summary.unique_ids_unknown == 1
    assert summary.frames_observed == 4
    assert summary.frames_covered == 3
    assert summary.frames_unknown == 1
    assert "0x18667217" in summary.known_can_ids
    assert "0x18FFFF00" in summary.unknown_can_ids


def test_coverage_partial_payload_exceeds_dlc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "references" / "canresearch.db"
    initialize(db_path)
    monkeypatch.setattr("canresearch.config.resolve_data_dir", lambda: data_dir)
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)

    session_id = "covsess02"
    frames = [_frame_line(can_id=0x18667217, dlc=64)]
    frames_path = _write_session(data_dir, session_id, frames)
    _create_completed_session(db_path, frames_path, session_id, frame_count=1)

    source = tmp_path / "lib.dbc"
    write_dbc(_sample_database(), source)
    register_dbc_source(key="cov_dbc2", path=source)

    summary = analyze_dbc_coverage(session_id, db_path=db_path)
    row = summary.rows[0]
    assert row.classification == "partially_covered"
    assert row.reason == "payload_exceeds_message_dlc"


def test_mcp_list_and_coverage_handlers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "references" / "canresearch.db"
    initialize(db_path)
    monkeypatch.setattr("canresearch.config.resolve_data_dir", lambda: data_dir)
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)

    session_id = "mcpsess01"
    frames = [_frame_line(can_id=0x18667217)]
    frames_path = _write_session(data_dir, session_id, frames)
    _create_completed_session(db_path, frames_path, session_id, frame_count=1)

    source = tmp_path / "lib.dbc"
    write_dbc(_sample_database(), source)
    register_dbc_source(key="mcp_dbc", path=source)

    listed = handle_list_dbc_sources()
    assert listed["count"] == 1
    coverage = handle_analyze_dbc_coverage(session_id=session_id)
    assert coverage["summary"]["unique_ids_covered"] == 1
    assert "known_first" in coverage


def test_missing_dbc_source_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("canresearch.core.dbc_registry.resolve_data_dir", lambda: data_dir)
    with pytest.raises(DbcSourceNotFoundError):
        load_dbc_source("missing")
