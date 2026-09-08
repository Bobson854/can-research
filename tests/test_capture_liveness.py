"""Tests for capture liveness, reconciliation, and orphan handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from canresearch.cansub.live_capture import LiveCaptureRegistry
from canresearch.cansub.ws_client import CansubRxResult
from canresearch.core.capture_liveness import (
    CAPTURE_HEARTBEAT_STALE_S,
    bind_capture_session,
    is_session_live_anywhere,
    list_live_captures,
    reconcile_orphaned_captures,
    reset_capture_server_id_for_tests,
    touch_capture_heartbeat,
)
from canresearch.core.sessions import SessionStatus, create_session, get_session
from canresearch.storage.database import SCHEMA_VERSION, initialize


@pytest.fixture
def liveness_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    db_path = tmp_path / "test.sqlite"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    def _frames_path(session_id: str) -> Path:
        return sessions_dir / session_id / "frames.jsonl"

    monkeypatch.setattr("canresearch.core.sessions.default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr("canresearch.core.sessions.session_frames_path", _frames_path)
    monkeypatch.setattr("canresearch.cansub.live_capture.session_frames_path", _frames_path)
    initialize(db_path)
    reset_capture_server_id_for_tests()
    return {"db_path": db_path, "sessions_dir": sessions_dir}


def _create_recording_row(env: dict[str, Path], session_id: str) -> None:
    create_session(
        session_id=session_id,
        name=None,
        host="host.local",
        channel=1,
        device_id="dev",
        frame_store_path=str(env["sessions_dir"] / session_id / "frames.jsonl"),
        db_path=env["db_path"],
    )


def _set_liveness(
    env: dict[str, Path],
    session_id: str,
    *,
    server_id: str | None,
    heartbeat_at: datetime | None,
) -> None:
    conn = initialize(env["db_path"])
    try:
        conn.execute(
            """
            UPDATE sessions
            SET capture_server_id = ?, capture_heartbeat_at = ?
            WHERE id = ?
            """,
            (
                server_id,
                heartbeat_at.isoformat() if heartbeat_at is not None else None,
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_schema_version_is_v11() -> None:
    assert SCHEMA_VERSION == 11


def test_reconcile_missing_heartbeat_on_startup(liveness_env) -> None:
    _create_recording_row(liveness_env, "stale001")
    reset_capture_server_id_for_tests()
    result = reconcile_orphaned_captures(
        db_path=liveness_env["db_path"],
        startup=True,
    )
    assert result.reconciled_session_ids == ("stale001",)
    record = get_session("stale001", db_path=liveness_env["db_path"])
    assert record.status == SessionStatus.INTERRUPTED
    assert record.stopped_at is not None
    assert record.interrupted_reason == "orphaned_capture"


def test_startup_preserves_fresh_heartbeat_from_other_server(liveness_env) -> None:
    _create_recording_row(liveness_env, "live-other")
    other_server = "aaaaaaaaaaaaaaaa"
    fresh = datetime.now(tz=UTC)
    _set_liveness(
        liveness_env,
        "live-other",
        server_id=other_server,
        heartbeat_at=fresh,
    )
    reset_capture_server_id_for_tests()

    result = reconcile_orphaned_captures(
        db_path=liveness_env["db_path"],
        startup=True,
    )

    assert result.reconciled_session_ids == ()
    record = get_session("live-other", db_path=liveness_env["db_path"])
    assert record.status == SessionStatus.RECORDING
    assert is_session_live_anywhere(record, now=fresh)


def test_startup_reconciles_stale_heartbeat_from_other_server(liveness_env) -> None:
    _create_recording_row(liveness_env, "stale-other")
    stale = datetime.now(tz=UTC) - timedelta(seconds=CAPTURE_HEARTBEAT_STALE_S + 5)
    _set_liveness(
        liveness_env,
        "stale-other",
        server_id="bbbbbbbbbbbbbbbb",
        heartbeat_at=stale,
    )
    reset_capture_server_id_for_tests()
    current = datetime.now(tz=UTC)

    result = reconcile_orphaned_captures(
        db_path=liveness_env["db_path"],
        startup=True,
        now=current,
    )

    assert result.reconciled_session_ids == ("stale-other",)
    record = get_session("stale-other", db_path=liveness_env["db_path"])
    assert record.status == SessionStatus.INTERRUPTED
    assert record.interrupted_reason == "service_restart"


def test_manual_reconcile_uses_orphaned_capture_reason(liveness_env) -> None:
    _create_recording_row(liveness_env, "stale-manual")
    stale = datetime.now(tz=UTC) - timedelta(seconds=CAPTURE_HEARTBEAT_STALE_S + 1)
    _set_liveness(
        liveness_env,
        "stale-manual",
        server_id="cccccccccccccccc",
        heartbeat_at=stale,
    )

    result = reconcile_orphaned_captures(db_path=liveness_env["db_path"])

    assert result.reconciled_session_ids == ("stale-manual",)
    record = get_session("stale-manual", db_path=liveness_env["db_path"])
    assert record.interrupted_reason == "orphaned_capture"


def test_reconcile_is_idempotent(liveness_env) -> None:
    _create_recording_row(liveness_env, "stale002")
    first = reconcile_orphaned_captures(
        db_path=liveness_env["db_path"],
        startup=True,
    )
    second = reconcile_orphaned_captures(
        db_path=liveness_env["db_path"],
        startup=True,
    )
    assert first.reconciled_session_ids == ("stale002",)
    assert second.reconciled_session_ids == ()


def test_heartbeating_capture_is_live(liveness_env) -> None:
    _create_recording_row(liveness_env, "live001")
    bind_capture_session("live001", db_path=liveness_env["db_path"])
    touch_capture_heartbeat("live001", db_path=liveness_env["db_path"])
    record = get_session("live001", db_path=liveness_env["db_path"])
    assert is_session_live_anywhere(record)
    assert list_live_captures(db_path=liveness_env["db_path"]) == [record]


def test_zero_frame_live_capture_remains_selectable(
    liveness_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    def fake_receive(host, channel, *, duration, stop_check=None, **kwargs):
        _ = host, channel, duration, kwargs
        import time

        while True:
            touch_capture_heartbeat("live002", db_path=liveness_env["db_path"])
            if stop_check is not None and stop_check():
                break
            time.sleep(0.05)
        return CansubRxResult(
            host="host.local",
            channel=1,
            connected=True,
            duration_s=0.1,
            frame_count=0,
            exit_reason="stopped",
        )

    monkeypatch.setattr("canresearch.cansub.live_capture.receive_frames_sync", fake_receive)
    monkeypatch.setattr(
        "canresearch.cansub.live_capture.abort_channel_websocket_sync",
        lambda *a, **k: True,
    )

    registry = LiveCaptureRegistry()
    started = registry.start("host.local", 1, db_path=liveness_env["db_path"])
    session_id = started["session_id"]
    record = get_session(session_id, db_path=liveness_env["db_path"])
    assert record.frame_count == 0
    assert is_session_live_anywhere(record)
    registry.stop(session_id, db_path=liveness_env["db_path"])


def test_worker_failure_finalizes_and_releases_registry(
    liveness_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from canresearch.cansub.exceptions import CansubWebSocketError

    monkeypatch.setattr("canresearch.cansub.live_capture.probe_host", lambda *a, **k: None)

    def fail_receive(*args, **kwargs):
        _ = args, kwargs
        raise CansubWebSocketError("websocket failed")

    monkeypatch.setattr("canresearch.cansub.live_capture.receive_frames_sync", fail_receive)

    registry = LiveCaptureRegistry()
    started = registry.start("host.local", 1, db_path=liveness_env["db_path"])
    session_id = started["session_id"]
    deadline = datetime.now(tz=UTC) + timedelta(seconds=5)
    while registry.is_channel_active(1) and datetime.now(tz=UTC) < deadline:
        pass
    record = get_session(session_id, db_path=liveness_env["db_path"])
    assert record.status == SessionStatus.FAILED
    assert record.interrupted_reason == "websocket_error"
    assert registry.list_active_session_ids() == []


def test_marker_companion_excludes_stale_rows(liveness_env) -> None:
    from canresearch.core.marker_companion import MarkerCompanionError, resolve_attached_session

    _create_recording_row(liveness_env, "stale003")
    create_session(
        session_id="live003",
        name="live",
        host="host.local",
        channel=2,
        device_id="dev",
        frame_store_path=str(liveness_env["sessions_dir"] / "live003" / "frames.jsonl"),
        db_path=liveness_env["db_path"],
    )
    bind_capture_session("live003", db_path=liveness_env["db_path"])
    touch_capture_heartbeat("live003", db_path=liveness_env["db_path"])

    attached = resolve_attached_session(db_path=liveness_env["db_path"])
    assert attached.session_id == "live003"

    with pytest.raises(MarkerCompanionError) as exc:
        resolve_attached_session(session_id="stale003", db_path=liveness_env["db_path"])
    assert exc.value.code == "capture_not_active"
    assert "not live" in exc.value.message
