"""Tests for capture sessions and JSONL frame storage."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from canresearch.cansub.capture import cansub_frame_to_can_frame, run_capture
from canresearch.cansub.exceptions import CansubWebSocketError
from canresearch.cansub.ws_client import CansubRxResult
from canresearch.cansub.ws_protocol import CansubFrame
from canresearch.cli import main
from canresearch.core.jsonl_capture_store import JsonlCaptureStore
from canresearch.core.sessions import (
    SessionStatus,
    create_session,
    list_sessions,
    summarize_session,
)
from canresearch.storage.database import SCHEMA_VERSION, initialize

SINGLE_FRAME = bytes.fromhex("7E 00 00 00 00 00 00 01 00 01 00 42 2D 3E 52 7E")
MULTI_FRAME = bytes.fromhex(
    "7E 00 00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 01 00 02 02 "
    "00 00 00 00 00 00 01 00 03 03 00 00 00 00 00 00 01 00 04 04 D1 2C 1F D9 7E"
)


class FakeWebSocket:
    def __init__(self, messages: list[bytes | Exception]) -> None:
        self._messages = list(messages)

    async def recv(self) -> bytes:
        if not self._messages:
            await asyncio.sleep(3600)
        item = self._messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self, code: int = 1000, reason: str = "") -> None:
        _ = code, reason


def _fake_connect(messages: list[bytes | Exception]):
    @asynccontextmanager
    async def connect(_url: str, **kwargs: Any):
        _ = kwargs
        yield FakeWebSocket(messages)

    return connect


def _fake_device_info(*args, **kwargs):
    _ = args, kwargs
    return type("Info", (), {"device_id": "abcd1234"})()


@pytest.fixture
def capture_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.cansub.capture.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.cansub.capture.probe_host", _fake_device_info)
    initialize(db_path)
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def test_create_session(capture_env) -> None:
    record = create_session(
        name="test",
        host="example.test",
        channel=1,
        device_id="abcd1234",
        frame_store_path="data/sessions/x/frames.jsonl",
        db_path=capture_env["db_path"],
        session_id="sess001",
    )
    assert record.id == "sess001"
    assert record.status == SessionStatus.RECORDING
    assert record.host == "example.test"
    assert record.channel == 1


def test_jsonl_store_roundtrip(tmp_path: Path) -> None:
    store = JsonlCaptureStore()
    path = tmp_path / "frames.jsonl"
    frame = cansub_frame_to_can_frame(
        CansubFrame(
            channel=1,
            timestamp_us=123,
            can_id=0x123,
            extended=False,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=2,
            data=b"\x01\x02",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        )
    )
    store.open(path)
    store.append(frame)
    store.close()

    reader = JsonlCaptureStore()
    reader._path = path
    loaded = list(reader.iter_frames())
    assert len(loaded) == 1
    assert loaded[0].can_id == 0x123
    assert loaded[0].data == b"\x01\x02"


def _read_jsonl(path: Path):
    store = JsonlCaptureStore()
    store._path = path
    return store.iter_frames()


def test_zero_frame_capture(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "canresearch.cansub.capture.receive_frames_sync",
        lambda *args, **kwargs: CansubRxResult(
            host="example.test",
            channel=1,
            connected=True,
            duration_s=0.2,
            frame_count=0,
            exit_reason="duration elapsed",
        ),
    )
    result = run_capture(
        "example.test",
        1,
        duration=0.2,
        name="idle",
        db_path=capture_env["db_path"],
    )
    assert result.session.status == SessionStatus.COMPLETED
    assert result.session.frame_count == 0
    assert Path(result.session.frame_store_path).exists()


def test_one_frame_capture(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rx(host, channel, **kwargs):
        on_frame = kwargs["on_frame"]

        def feed() -> None:
            from canresearch.cansub.ws_protocol import HdlcFrameParser

            for frame in HdlcFrameParser().parse_frames(SINGLE_FRAME, channel=channel):
                on_frame(frame)

        feed()
        return CansubRxResult(
            host=host,
            channel=channel,
            connected=True,
            duration_s=0.1,
            frame_count=1,
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.cansub.capture.receive_frames_sync", fake_rx)
    result = run_capture("example.test", 1, duration=0.2, db_path=capture_env["db_path"])
    assert result.session.frame_count == 1
    frames = list(_read_jsonl(Path(result.session.frame_store_path)))
    assert frames[0].can_id == 0x001


def test_multiple_frame_capture(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rx(host, channel, **kwargs):
        on_frame = kwargs["on_frame"]
        from canresearch.cansub.ws_protocol import HdlcFrameParser

        for frame in HdlcFrameParser().parse_frames(MULTI_FRAME, channel=channel):
            on_frame(frame)
        return CansubRxResult(
            host=host,
            channel=channel,
            connected=True,
            duration_s=0.1,
            frame_count=4,
            exit_reason="duration elapsed",
        )

    monkeypatch.setattr("canresearch.cansub.capture.receive_frames_sync", fake_rx)
    result = run_capture("example.test", 1, duration=0.2, db_path=capture_env["db_path"])
    assert result.session.frame_count == 4


def test_max_frames_capture(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rx(host, channel, **kwargs):
        on_frame = kwargs["on_frame"]
        from canresearch.cansub.ws_protocol import HdlcFrameParser

        frames = HdlcFrameParser().parse_frames(MULTI_FRAME, channel=channel)
        for frame in frames[:2]:
            on_frame(frame)
        return CansubRxResult(
            host=host,
            channel=channel,
            connected=True,
            duration_s=0.1,
            frame_count=2,
            exit_reason="max frames reached",
        )

    monkeypatch.setattr("canresearch.cansub.capture.receive_frames_sync", fake_rx)
    result = run_capture(
        "example.test",
        1,
        duration=5.0,
        max_frames=2,
        db_path=capture_env["db_path"],
    )
    assert result.session.frame_count == 2
    assert result.exit_reason == "max frames reached"


def test_connection_failure_marks_failed(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rx(*args, **kwargs):
        _ = args, kwargs
        raise CansubWebSocketError("connection refused")

    monkeypatch.setattr("canresearch.cansub.capture.receive_frames_sync", fake_rx)
    with pytest.raises(CansubWebSocketError):
        run_capture("example.test", 1, duration=0.2, db_path=capture_env["db_path"])
    sessions = list_sessions(db_path=capture_env["db_path"], limit=1)
    assert sessions[0].status == SessionStatus.FAILED


def test_interrupt_capture(capture_env) -> None:
    result = run_capture(
        "example.test",
        1,
        duration=5.0,
        db_path=capture_env["db_path"],
        interrupted=True,
    )
    assert result.session.status == SessionStatus.INTERRUPTED
    assert result.exit_reason == "interrupted"


def test_repeated_captures_separate_stores(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "canresearch.cansub.capture.receive_frames_sync",
        lambda *args, **kwargs: CansubRxResult(
            host="example.test",
            channel=1,
            connected=True,
            duration_s=0.1,
            frame_count=0,
            exit_reason="duration elapsed",
        ),
    )
    first = run_capture("example.test", 1, duration=0.1, db_path=capture_env["db_path"])
    second = run_capture("example.test", 2, duration=0.1, db_path=capture_env["db_path"])
    assert first.session.id != second.session.id
    assert first.session.frame_store_path != second.session.frame_store_path


def test_session_list_and_summary(capture_env) -> None:
    create_session(
        name="listed",
        host="example.test",
        channel=1,
        device_id=None,
        frame_store_path="data/sessions/x/frames.jsonl",
        db_path=capture_env["db_path"],
        session_id="listed01",
    )
    from canresearch.core.sessions import finalize_session

    finalize_session(
        "listed01",
        status=SessionStatus.COMPLETED,
        frame_count=0,
        db_path=capture_env["db_path"],
    )
    sessions = list_sessions(db_path=capture_env["db_path"])
    assert sessions[0].id == "listed01"
    summary = summarize_session("listed01", db_path=capture_env["db_path"])
    assert summary["status"] == "completed"
    assert summary["frame_count"] == 0


def test_capture_cli_zero_frames(capture_env, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from canresearch.cansub.capture import CaptureResult
    from canresearch.core.sessions import SessionRecord

    record = SessionRecord(
        id="cli001",
        name="desk-idle",
        device_id="abcd1234",
        host="example.test",
        channel=1,
        started_at=datetime.now(tz=UTC),
        stopped_at=datetime.now(tz=UTC),
        status=SessionStatus.COMPLETED,
        frame_store_path=str(capture_env["sessions_dir"] / "cli001" / "frames.jsonl"),
        frame_count=0,
        notes=None,
    )

    def fake_run_capture(*args, **kwargs):
        _ = args, kwargs
        Path(record.frame_store_path).parent.mkdir(parents=True, exist_ok=True)
        Path(record.frame_store_path).write_text("", encoding="utf-8")
        return CaptureResult(session=record, duration_s=5.0, exit_reason="duration elapsed")

    monkeypatch.setattr("canresearch.cansub.capture.run_capture", fake_run_capture)
    monkeypatch.setattr(
        "canresearch.config.default_config_path",
        lambda: capture_env["db_path"].with_suffix(".toml"),
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "capture",
            "start",
            "--channel",
            "1",
            "--host",
            "example.test",
            "--duration",
            "5",
            "--name",
            "desk-idle",
        ],
    )
    assert result.exit_code == 0
    assert "Capture complete" in result.output
    assert "cli001" in result.output
    assert "Frames:      0" in result.output


def test_schema_version_includes_session_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = initialize(db_path)
    assert SCHEMA_VERSION == 10
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    assert {"host", "channel"} <= columns
    conn.close()


def test_jsonl_line_format() -> None:
    frame = cansub_frame_to_can_frame(
        CansubFrame(
            channel=1,
            timestamp_us=0,
            can_id=0x7FF,
            extended=False,
            fd=False,
            rtr=False,
            brs=False,
            esi=False,
            tx_ack=False,
            dlc=1,
            data=b"\x00",
            is_error_frame=False,
            error_type=None,
            raw=b"",
        )
    )
    from canresearch.core.jsonl_capture_store import _frame_to_json

    payload = _frame_to_json(frame)
    assert payload["can_id"] == 0x7FF
    assert payload["data"] == "00"
    assert "timestamp_us" in payload
