"""Tests for live CANsub research core services."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from canresearch.cansub.live_capture import LiveCaptureRegistry
from canresearch.core.j1939_tp import encode_j1939_can_id
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.live_research import (
    compare_experiment_windows,
    get_cansub_device_status,
    mark_experiment_event,
    observe_live_traffic,
)
from canresearch.core.session_events import add_session_event
from canresearch.core.sessions import create_session
from canresearch.storage.database import SCHEMA_VERSION, initialize
from tests.fixtures.live_frame_source import FakeLiveFrameSource, ScheduledFrame  # noqa: F401


def _write_jsonl(path: Path, frames: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame, separators=(",", ":")))
            handle.write("\n")


def _j1939_frame_line(
    *,
    can_id: int,
    data: str,
    timestamp_us: int,
    channel: int = 1,
) -> dict:
    return {
        "timestamp_us": timestamp_us,
        "channel": channel,
        "can_id": can_id,
        "extended": True,
        "fd": False,
        "rtr": False,
        "brs": False,
        "esi": False,
        "tx_ack": False,
        "dlc": len(bytes.fromhex(data)),
        "data": data,
        "is_error_frame": False,
        "error_type": None,
    }


@pytest.fixture
def live_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.cansub.live_capture.session_frames_path", _frames_path)
    initialize(db_path)
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def test_schema_version_is_v8() -> None:
    assert SCHEMA_VERSION == 8


def test_session_events_table(live_env) -> None:
    conn = initialize(live_env["db_path"])
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "session_events" in tables
    conn.close()


def test_get_device_status_unreachable() -> None:
    with pytest.raises(LiveResearchError) as exc:
        get_cansub_device_status("192.0.2.1", timeout=0.1)
    assert exc.value.code == "cansub_unreachable"


def test_get_device_status_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from canresearch.cansub.client import CansubDeviceInfo

    monkeypatch.setattr(
        "canresearch.core.live_research.probe_host",
        lambda *args, **kwargs: CansubDeviceInfo(
            host="desk.local",
            device_id="dev-1",
            firmware_version="02.04.00",
            api_version="04.00",
            channels=[1, 2],
        ),
    )
    result = get_cansub_device_status("desk.local")
    assert result["device_id"] == "dev-1"
    assert result["channel_count"] == 2
    assert result["connection_state"] == "reachable"


def test_observe_live_traffic_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    from canresearch.cansub.ws_client import CansubRxResult
    from canresearch.cansub.ws_protocol import CansubFrame

    can_id = encode_j1939_can_id(pgn=61444, priority=3, source_address=0)
    scheduled = [
        CansubFrame(
            channel=1,
            timestamp_us=1_000_000,
            can_id=can_id,
            extended=True,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=4,
            data=b"\x01\x02\x03\x04",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        ),
        CansubFrame(
            channel=1,
            timestamp_us=1_100_000,
            can_id=can_id,
            extended=True,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=4,
            data=b"\x01\x02\x03\x04",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        ),
        CansubFrame(
            channel=1,
            timestamp_us=1_200_000,
            can_id=can_id,
            extended=True,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=4,
            data=b"\x01\x02\x03\x05",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        ),
    ]

    def fake_receive(host, channel, *, duration, on_frame=None, **kwargs):
        _ = host, channel, duration, kwargs
        for frame in scheduled:
            if on_frame is not None:
                on_frame(frame)
        return CansubRxResult(
            host="example.test",
            channel=1,
            connected=True,
            duration_s=0.5,
            frame_count=len(scheduled),
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.core.live_research.receive_frames_sync", fake_receive)
    result = observe_live_traffic(
        "example.test",
        1,
        duration_seconds=0.5,
    )
    assert result["frames_seen"] == 3
    assert result["unique_can_ids"] == 1
    assert result["unique_j1939_pgns"] == 1
    assert len(result["traffic"]) == 1
    row = result["traffic"][0]
    assert row["pgn"] == 61444
    assert row["source_address"] == 0
    assert row["count"] == 3
    assert row["data_changes"] == 1
    assert len(row["sample_payloads"]) <= 3


def test_observe_live_traffic_first_last_seen_use_absolute_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.cansub.ws_client import CansubRxResult
    from canresearch.cansub.ws_protocol import TIMESTAMP_EPOCH_US, CansubFrame

    can_id = encode_j1939_can_id(pgn=61444, priority=3, source_address=0)
    start_us = TIMESTAMP_EPOCH_US + 5_000_000
    end_us = TIMESTAMP_EPOCH_US + 7_500_000
    scheduled = [
        CansubFrame(
            channel=1,
            timestamp_us=start_us,
            can_id=can_id,
            extended=True,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=1,
            data=b"\x01",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        ),
        CansubFrame(
            channel=1,
            timestamp_us=end_us,
            can_id=can_id,
            extended=True,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=1,
            data=b"\x02",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        ),
    ]

    def fake_receive(host, channel, *, duration, on_frame=None, **kwargs):
        _ = host, channel, duration, kwargs
        for frame in scheduled:
            if on_frame is not None:
                on_frame(frame)
        return CansubRxResult(
            host="example.test",
            channel=1,
            connected=True,
            duration_s=2.5,
            frame_count=len(scheduled),
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.core.live_research.receive_frames_sync", fake_receive)
    result = observe_live_traffic("example.test", 1, duration_seconds=2.5)
    row = result["traffic"][0]
    assert row["first_seen"] == "2025-01-01T00:00:05+00:00"
    assert row["last_seen"] == "2025-01-01T00:00:07.500000+00:00"
    assert row["first_seen"].startswith("2025-")
    assert row["last_seen"].startswith("2025-")


def test_observe_live_traffic_channel_rx_in_use() -> None:
    registry = LiveCaptureRegistry()
    from canresearch.cansub.live_capture import ActiveCapture

    capture = ActiveCapture(
        session_id="sess001",
        channel=1,
        host="host",
        started_at=__import__("datetime").datetime.now(tz=__import__("datetime").UTC),
    )
    registry._by_channel[1] = "sess001"
    registry._by_session["sess001"] = capture
    with pytest.raises(LiveResearchError) as exc:
        observe_live_traffic("example.test", 1, registry=registry)
    assert exc.value.code == "channel_rx_in_use"


def test_observe_live_traffic_websocket_slot_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.cansub.exceptions import CansubWebSocketError

    def fake_receive(*args, **kwargs):
        _ = args, kwargs
        raise CansubWebSocketError(
            "CAN channel 1 WebSocket on example.test is in use by another client "
            "(CANsub.2 allows one WebSocket per channel). Close webCAN or other listeners "
            "and retry."
        )

    monkeypatch.setattr("canresearch.core.live_research.receive_frames_sync", fake_receive)
    with pytest.raises(LiveResearchError) as exc:
        observe_live_traffic("example.test", 1)
    assert exc.value.code == "channel_rx_in_use"


def test_observe_respects_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from canresearch.cansub.ws_client import CansubRxResult
    from canresearch.cansub.ws_protocol import CansubFrame

    scheduled = [
        CansubFrame(
            channel=1,
            timestamp_us=1_000_000 + index * 1000,
            can_id=0x100 + index,
            extended=False,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=1,
            data=bytes([index]),
            is_error_frame=False,
            error_type=None,
            raw=b"",
        )
        for index in range(10)
    ]

    def fake_receive(host, channel, *, duration, on_frame=None, **kwargs):
        _ = host, channel, duration, kwargs
        for frame in scheduled:
            if on_frame is not None:
                on_frame(frame)
        return CansubRxResult(
            host="example.test",
            channel=1,
            connected=True,
            duration_s=0.5,
            frame_count=len(scheduled),
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.core.live_research.receive_frames_sync", fake_receive)
    result = observe_live_traffic(
        "example.test",
        1,
        duration_seconds=0.5,
        limit=3,
    )
    assert len(result["traffic"]) == 3
    assert result["truncated"] is True


def test_capture_duplicate_start(live_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)
    registry = LiveCaptureRegistry()
    registry._by_channel[1] = "existing"
    with pytest.raises(LiveResearchError) as exc:
        registry.start("host", 1, db_path=live_env["db_path"])
    assert exc.value.code == "capture_already_active"


def test_mark_and_compare_windows(live_env) -> None:
    db_path = live_env["db_path"]
    session_id = "cmp001"
    can_id = 0x18FF748A
    path = live_env["sessions_dir"] / session_id / "frames.jsonl"
    _write_jsonl(
        path,
        [
            _j1939_frame_line(can_id=can_id, data="0102030405060708", timestamp_us=1_000_000),
            _j1939_frame_line(can_id=can_id, data="0102030405060708", timestamp_us=1_500_000),
            _j1939_frame_line(can_id=can_id, data="010203AA05060708", timestamp_us=5_000_000),
            _j1939_frame_line(can_id=can_id, data="010203AA05060708", timestamp_us=5_500_000),
        ],
    )
    create_session(
        session_id=session_id,
        name="compare-test",
        host="example.test",
        channel=1,
        device_id="dev",
        frame_store_path=str(path),
        db_path=db_path,
    )
    add_session_event(session_id, "baseline_start", timestamp_us=1_000_000, db_path=db_path)
    add_session_event(session_id, "scv2_extend", timestamp_us=5_000_000, db_path=db_path)

    result = compare_experiment_windows(
        session_id,
        baseline_event="baseline_start",
        action_event="scv2_extend",
        window_seconds=3.0,
        db_path=db_path,
    )
    assert result["baseline"]["frames"] == 2
    assert result["action"]["frames"] == 2
    top = result["top_changes"][0]
    assert top["can_id"] == "0x18FF748A"
    assert top["baseline_count"] == 2
    assert top["action_count"] == 2
    assert 3 in top["changed_byte_indices"]
    assert top["change_score"] > 0


def test_compare_event_not_found(live_env) -> None:
    session_id = "cmp002"
    path = live_env["sessions_dir"] / session_id / "frames.jsonl"
    _write_jsonl(path, [_j1939_frame_line(can_id=0x100, data="01", timestamp_us=1)])
    create_session(
        session_id=session_id,
        name=None,
        host="example.test",
        channel=1,
        device_id="dev",
        frame_store_path=str(path),
        db_path=live_env["db_path"],
    )
    with pytest.raises(LiveResearchError) as exc:
        compare_experiment_windows(
            session_id,
            baseline_event="missing",
            action_event="also_missing",
            db_path=live_env["db_path"],
        )
    assert exc.value.code == "event_not_found"


def test_mark_event_uses_capture_timestamp(
    live_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = LiveCaptureRegistry()
    session_id = "evt001"
    from datetime import UTC, datetime

    from canresearch.cansub.live_capture import ActiveCapture

    registry._by_session[session_id] = ActiveCapture(
        session_id=session_id,
        channel=1,
        host="host",
        started_at=datetime.now(tz=UTC),
    )
    monkeypatch.setattr(registry, "latest_timestamp_us", lambda sid: 9_000_000)

    create_session(
        session_id=session_id,
        name=None,
        host="example.test",
        channel=1,
        device_id="dev",
        frame_store_path=str(live_env["sessions_dir"] / session_id / "frames.jsonl"),
        db_path=live_env["db_path"],
    )
    event = mark_experiment_event(
        session_id,
        "baseline_start",
        db_path=live_env["db_path"],
        registry=registry,
    )
    assert event["timestamp_us"] == 9_000_000
