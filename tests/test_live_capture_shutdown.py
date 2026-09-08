"""Regression tests for live capture stop / WebSocket release."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from canresearch.cansub.live_capture import LiveCaptureRegistry
from canresearch.cansub.ws_client import CansubRxResult
from canresearch.core.sessions import SessionStatus, get_session
from canresearch.storage.database import initialize


@pytest.fixture
def live_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    empty_config = tmp_path / "config.toml"
    empty_config.write_text('[cansub]\nhost = "host.local"\n', encoding="utf-8")

    monkeypatch.setattr("canresearch.config.default_config_path", lambda: empty_config)
    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.cansub.live_capture.session_frames_path", _frames_path)
    initialize(db_path)
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def _blocking_zero_frame_receive(*, stop_check):
    """Simulate a connected WebSocket that receives no frames until stop."""

    def fake_receive(host, channel, *, duration, stop_check=None, **kwargs):
        _ = duration, kwargs
        deadline = time.monotonic() + 3600.0
        while time.monotonic() < deadline:
            if stop_check is not None and stop_check():
                break
            time.sleep(0.05)
        return CansubRxResult(
            host=host,
            channel=channel,
            connected=True,
            duration_s=0.1,
            frame_count=0,
            exit_reason="stopped",
        )

    return fake_receive


def test_stop_zero_frame_capture_completes_promptly(
    live_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    abort_calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        "canresearch.cansub.live_capture.receive_frames_sync",
        _blocking_zero_frame_receive(stop_check=None),
    )
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)
    monkeypatch.setattr(
        "canresearch.cansub.live_capture.abort_channel_websocket_sync",
        lambda host, channel, **kwargs: abort_calls.append((host, channel)) or True,
    )

    registry = LiveCaptureRegistry()
    started = registry.start("host.local", 1, db_path=live_env["db_path"])
    session_id = started["session_id"]

    t0 = time.monotonic()
    result = registry.stop(session_id, db_path=live_env["db_path"])
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0
    assert result["frame_count"] == 0
    assert registry.list_active_session_ids() == []
    assert not registry.is_channel_active(1)
    assert abort_calls == [("host.local", 1)]

    session = get_session(session_id, db_path=live_env["db_path"])
    assert session.status == SessionStatus.INTERRUPTED
    assert session.stopped_at is not None


def test_subsequent_capture_allowed_after_stop(
    live_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "canresearch.cansub.live_capture.receive_frames_sync",
        _blocking_zero_frame_receive(stop_check=None),
    )
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)
    monkeypatch.setattr(
        "canresearch.cansub.live_capture.abort_channel_websocket_sync",
        lambda *a, **k: True,
    )

    registry = LiveCaptureRegistry()
    first = registry.start("host.local", 1, db_path=live_env["db_path"])
    registry.stop(first["session_id"], db_path=live_env["db_path"])

    second = registry.start("host.local", 1, db_path=live_env["db_path"])
    assert second["session_id"] != first["session_id"]
    registry.stop(second["session_id"], db_path=live_env["db_path"])
    assert registry.list_active_session_ids() == []


def test_failed_startup_releases_registry_entry(
    live_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.cansub.exceptions import CansubWebSocketError

    def fail_receive(*args, **kwargs):
        _ = args, kwargs
        raise CansubWebSocketError("channel unavailable")

    monkeypatch.setattr("canresearch.cansub.live_capture.receive_frames_sync", fail_receive)
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    registry = LiveCaptureRegistry()
    started = registry.start("host.local", 1, db_path=live_env["db_path"])
    session_id = started["session_id"]

    deadline = time.monotonic() + 5.0
    while registry.is_channel_active(1) and time.monotonic() < deadline:
        time.sleep(0.05)

    assert registry.list_active_session_ids() == []
    assert not registry.is_channel_active(1)
    session = get_session(session_id, db_path=live_env["db_path"])
    assert session.status == SessionStatus.FAILED


def test_stop_live_capture_uses_abort_for_channel_reclaim(
    live_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "canresearch.cansub.live_capture.receive_frames_sync",
        _blocking_zero_frame_receive(stop_check=None),
    )
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    release_calls: list[int] = []

    def track_abort(host, channel, **kwargs):
        _ = host, kwargs
        release_calls.append(channel)
        return True

    monkeypatch.setattr(
        "canresearch.cansub.live_capture.abort_channel_websocket_sync",
        track_abort,
    )

    from canresearch.cansub.live_capture import start_live_capture, stop_live_capture

    registry = LiveCaptureRegistry()
    started = start_live_capture(
        "host.local",
        2,
        db_path=live_env["db_path"],
        registry=registry,
    )
    stop_live_capture(
        started["session_id"],
        db_path=live_env["db_path"],
        registry=registry,
    )
    assert release_calls == [2]
