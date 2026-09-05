"""Background live capture lifecycle for CANsub.2."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from canresearch.cansub.capture import cansub_frame_to_can_frame, default_capture_store
from canresearch.cansub.client import probe_host
from canresearch.cansub.exceptions import CansubConnectionError, CansubWebSocketError
from canresearch.cansub.ws_client import ConnectFn, receive_frames_sync
from canresearch.core.assets import link_session_asset
from canresearch.core.live_errors import LiveResearchError
from canresearch.core.sessions import (
    CaptureStore,
    SessionStatus,
    create_session,
    finalize_session,
    get_session,
    session_frames_path,
)
from canresearch.storage.database import default_db_path, initialize

MAX_CAPTURE_DURATION_S = 86_400.0
STOP_JOIN_TIMEOUT_S = 15.0


@dataclass
class ActiveCapture:
    session_id: str
    channel: int
    host: str
    started_at: datetime
    stop_event: threading.Event = field(default_factory=threading.Event)
    finished_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    latest_timestamp_us: int | None = None
    error: Exception | None = None
    frame_count: int = 0
    duration_s: float = 0.0
    exit_reason: str = "recording"


class LiveCaptureRegistry:
    """Track in-process live capture sessions (one active capture per channel)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_session: dict[str, ActiveCapture] = {}
        self._by_channel: dict[int, str] = {}

    def is_channel_active(self, channel: int) -> bool:
        with self._lock:
            session_id = self._by_channel.get(channel)
            if session_id is None:
                return False
            capture = self._by_session.get(session_id)
            return capture is not None and not capture.finished_event.is_set()

    def get_active(self, session_id: str) -> ActiveCapture | None:
        with self._lock:
            capture = self._by_session.get(session_id)
            if capture is None or capture.finished_event.is_set():
                return None
            return capture

    def latest_timestamp_us(self, session_id: str) -> int | None:
        with self._lock:
            capture = self._by_session.get(session_id)
            return capture.latest_timestamp_us if capture else None

    def list_active_session_ids(self) -> list[str]:
        with self._lock:
            return [
                session_id
                for session_id, capture in self._by_session.items()
                if not capture.finished_event.is_set()
            ]

    def start(
        self,
        host: str,
        channel: int,
        *,
        session_name: str | None = None,
        asset_keys: tuple[str, ...] = (),
        notes: str | None = None,
        timeout: float = 5.0,
        verify_tls: bool = False,
        db_path: Path | None = None,
        store: CaptureStore | None = None,
        connect: ConnectFn | None = None,
    ) -> dict[str, object]:
        with self._lock:
            if channel in self._by_channel:
                active_id = self._by_channel[channel]
                msg = f"Capture already active on channel {channel} (session {active_id})"
                raise LiveResearchError("capture_already_active", msg)

        device_id: str | None = None
        try:
            device_info = probe_host(host, timeout=timeout, verify_tls=verify_tls)
            device_id = device_info.device_id
        except (CansubConnectionError, Exception):
            device_id = None

        session_id = _new_session_id(db_path=db_path)
        frames_path = session_frames_path(session_id)
        session = create_session(
            session_id=session_id,
            name=session_name,
            host=host,
            channel=channel,
            device_id=device_id,
            frame_store_path=str(frames_path),
            db_path=db_path,
        )
        if notes:
            path = db_path or default_db_path()
            conn = initialize(path)
            try:
                conn.execute("UPDATE sessions SET notes = ? WHERE id = ?", (notes, session_id))
                conn.commit()
            finally:
                conn.close()
            session = get_session(session_id, db_path=db_path)

        linked_assets: list[dict[str, str]] = []
        for asset_key in asset_keys:
            record = link_session_asset(
                session_id,
                asset_key,
                role="other",
                db_path=db_path,
            )
            linked_assets.append(
                {"asset_key": record.asset_key, "role": record.role},
            )

        capture = ActiveCapture(
            session_id=session_id,
            channel=channel,
            host=host,
            started_at=session.started_at,
        )

        def worker() -> None:
            capture_store = store or default_capture_store()
            capture_store.open(frames_path)
            final_status = SessionStatus.COMPLETED
            try:
                def on_frame(frame) -> None:
                    capture.latest_timestamp_us = frame.timestamp_us
                    capture_store.append(cansub_frame_to_can_frame(frame))

                rx = receive_frames_sync(
                    host,
                    channel,
                    duration=MAX_CAPTURE_DURATION_S,
                    timeout=timeout,
                    verify_tls=verify_tls,
                    on_frame=on_frame,
                    connect=connect,
                    stop_check=capture.stop_event.is_set,
                )
                capture.duration_s = rx.duration_s
                capture.exit_reason = rx.exit_reason
                if rx.exit_reason == "interrupted":
                    final_status = SessionStatus.INTERRUPTED
            except CansubWebSocketError as exc:
                capture.error = exc
                final_status = SessionStatus.FAILED
            except Exception as exc:
                capture.error = exc
                final_status = SessionStatus.FAILED
            finally:
                capture.frame_count = capture_store.frame_count()
                capture_store.close()
                finalize_session(
                    session_id,
                    status=final_status,
                    frame_count=capture.frame_count,
                    stopped_at=datetime.now(tz=UTC),
                    db_path=db_path,
                )
                capture.finished_event.set()
                with self._lock:
                    self._by_session.pop(session_id, None)
                    if self._by_channel.get(channel) == session_id:
                        self._by_channel.pop(channel, None)

        thread = threading.Thread(target=worker, name=f"live-capture-{session_id}", daemon=True)
        capture.thread = thread
        with self._lock:
            self._by_session[session_id] = capture
            self._by_channel[channel] = session_id
        thread.start()

        return {
            "session_id": session_id,
            "channel": channel,
            "started_at": session.started_at.isoformat(),
            "linked_assets": linked_assets,
            "capture_state": "recording",
        }

    def stop(
        self,
        session_id: str,
        *,
        db_path: Path | None = None,
    ) -> dict[str, object]:
        with self._lock:
            capture = self._by_session.get(session_id)
            if capture is None or capture.finished_event.is_set():
                msg = f"No active capture for session {session_id!r}"
                raise LiveResearchError("capture_not_active", msg)

        capture.stop_event.set()
        if capture.thread is not None:
            capture.thread.join(timeout=STOP_JOIN_TIMEOUT_S)
        if not capture.finished_event.is_set():
            msg = f"Timed out stopping capture for session {session_id!r}"
            raise LiveResearchError("observation_timeout", msg)
        if capture.error is not None:
            raise LiveResearchError("cansub_api_error", str(capture.error))

        session = get_session(session_id, db_path=db_path)
        duration_s: float | None = None
        if session.stopped_at is not None:
            duration_s = (session.stopped_at - session.started_at).total_seconds()
        return {
            "session_id": session_id,
            "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
            "frame_count": session.frame_count or 0,
            "duration_s": duration_s,
            "capture_state": session.status.value,
        }


def _new_session_id(*, db_path: Path | None = None) -> str:
    while True:
        candidate = uuid.uuid4().hex[:12]
        try:
            get_session(candidate, db_path=db_path)
        except KeyError:
            return candidate


_default_registry = LiveCaptureRegistry()


def get_live_capture_registry() -> LiveCaptureRegistry:
    return _default_registry


def start_live_capture(
    host: str,
    channel: int,
    *,
    session_name: str | None = None,
    asset_keys: tuple[str, ...] = (),
    notes: str | None = None,
    timeout: float = 5.0,
    verify_tls: bool = False,
    db_path: Path | None = None,
    store: CaptureStore | None = None,
    connect: ConnectFn | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> dict[str, object]:
    """Start a background live capture on a CANsub channel."""
    reg = registry or get_live_capture_registry()
    return reg.start(
        host,
        channel,
        session_name=session_name,
        asset_keys=asset_keys,
        notes=notes,
        timeout=timeout,
        verify_tls=verify_tls,
        db_path=db_path,
        store=store,
        connect=connect,
    )


def stop_live_capture(
    session_id: str,
    *,
    db_path: Path | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> dict[str, object]:
    """Stop an active background live capture."""
    reg = registry or get_live_capture_registry()
    return reg.stop(session_id, db_path=db_path)
