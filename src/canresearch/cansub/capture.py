"""Live capture from CANsub.2 hardware."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from canresearch.cansub.client import probe_host
from canresearch.cansub.exceptions import CansubWebSocketError
from canresearch.cansub.ws_client import ConnectFn, receive_frames_sync
from canresearch.cansub.ws_protocol import CansubFrame
from canresearch.core.jsonl_capture_store import JsonlCaptureStore
from canresearch.core.sessions import (
    CanFrame,
    CaptureStore,
    SessionRecord,
    SessionStatus,
    create_session,
    finalize_session,
    get_session,
    session_frames_path,
)


@dataclass(frozen=True, slots=True)
class CaptureResult:
    """Outcome of a capture session run."""

    session: SessionRecord
    duration_s: float
    exit_reason: str


def default_capture_store() -> CaptureStore:
    """Return the default capture store implementation."""
    return JsonlCaptureStore()


def cansub_frame_to_can_frame(frame: CansubFrame) -> CanFrame:
    """Convert a parsed CANsub WebSocket frame to a capture record."""
    return CanFrame(
        timestamp_us=frame.timestamp_us,
        channel=frame.channel,
        can_id=frame.can_id,
        is_extended=frame.extended,
        fd=frame.fd,
        rtr=frame.rtr,
        brs=frame.brs,
        esi=frame.esi,
        tx_ack=frame.tx_ack,
        dlc=frame.dlc,
        data=frame.data,
        is_error_frame=frame.is_error_frame,
        error_type=frame.error_type,
    )


def run_capture(
    host: str,
    channel: int,
    *,
    duration: float = 5.0,
    max_frames: int | None = None,
    name: str | None = None,
    timeout: float = 5.0,
    verify_tls: bool = False,
    store: CaptureStore | None = None,
    db_path: Path | None = None,
    connect: ConnectFn | None = None,
    interrupted: bool = False,
) -> CaptureResult:
    """Create a session, receive frames, and persist them to a file-backed store."""
    from canresearch.core.timing_preflight import enforce_channel_timing_preflight

    enforce_channel_timing_preflight(
        host,
        channel,
        timeout=timeout,
        verify_tls=verify_tls,
    )

    if duration <= 0:
        msg = "Duration must be positive"
        raise ValueError(msg)

    device_id: str | None = None
    try:
        device_info = probe_host(host, timeout=timeout, verify_tls=verify_tls)
        device_id = device_info.device_id
    except Exception:
        device_id = None

    session_id = _new_session_id(db_path=db_path)
    frames_path = session_frames_path(session_id)
    capture_store = store or default_capture_store()
    session = create_session(
        session_id=session_id,
        name=name,
        host=host,
        channel=channel,
        device_id=device_id,
        frame_store_path=str(frames_path),
        db_path=db_path,
    )

    capture_store.open(frames_path)
    exit_reason = "duration elapsed"
    duration_s = 0.0
    final_status = SessionStatus.COMPLETED

    try:
        if interrupted:
            raise KeyboardInterrupt

        def on_frame(frame: CansubFrame) -> None:
            capture_store.append(cansub_frame_to_can_frame(frame))

        rx_result = receive_frames_sync(
            host,
            channel,
            duration=duration,
            max_frames=max_frames,
            timeout=timeout,
            verify_tls=verify_tls,
            on_frame=on_frame,
            connect=connect,
        )
        exit_reason = rx_result.exit_reason
        duration_s = rx_result.duration_s
        if exit_reason == "interrupted":
            final_status = SessionStatus.INTERRUPTED
    except KeyboardInterrupt:
        exit_reason = "interrupted"
        final_status = SessionStatus.INTERRUPTED
    except CansubWebSocketError:
        final_status = SessionStatus.FAILED
        raise
    except Exception:
        final_status = SessionStatus.FAILED
        raise
    finally:
        frame_count = capture_store.frame_count()
        capture_store.close()
        stopped_at = datetime.now(tz=UTC)
        session = finalize_session(
            session.id,
            status=final_status,
            frame_count=frame_count,
            stopped_at=stopped_at,
            db_path=db_path,
        )

    return CaptureResult(session=session, duration_s=duration_s, exit_reason=exit_reason)


def _new_session_id(*, db_path: Path | None = None) -> str:
    while True:
        candidate = uuid.uuid4().hex[:12]
        try:
            get_session(candidate, db_path=db_path)
        except KeyError:
            return candidate


def start_capture(
    device_id: str,
    session_name: str | None = None,
    store: CaptureStore | None = None,
    output_dir: Path | None = None,
) -> str:
    """Legacy entry point retained for compatibility."""
    _ = device_id, session_name, store, output_dir
    raise NotImplementedError("Use run_capture() with host and channel instead")


def stop_capture() -> None:
    """Stop the active capture session."""
    raise NotImplementedError("Capture sessions stop automatically after duration or Ctrl+C")
