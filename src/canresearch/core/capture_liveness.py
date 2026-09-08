"""Durable capture liveness, orphan reconciliation, and live-session selection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from canresearch.core.sessions import (
    SessionRecord,
    SessionStatus,
    finalize_session,
    get_session,
    list_sessions_by_status,
)
from canresearch.storage.database import default_db_path, initialize

if TYPE_CHECKING:
    from canresearch.cansub.live_capture import LiveCaptureRegistry

CAPTURE_HEARTBEAT_INTERVAL_S = 5.0
CAPTURE_HEARTBEAT_STALE_S = 30.0

_capture_server_id: str | None = None


def get_capture_server_id() -> str:
    """Return the capture-server instance id for this process."""
    global _capture_server_id
    if _capture_server_id is None:
        _capture_server_id = uuid.uuid4().hex[:16]
    return _capture_server_id


def reset_capture_server_id_for_tests() -> None:
    """Reset the process-local server id (tests only)."""
    global _capture_server_id
    _capture_server_id = None


def bind_capture_session(session_id: str, *, db_path: Path | None = None) -> None:
    """Claim a recording session for this capture-server instance."""
    now = datetime.now(tz=UTC).isoformat()
    server_id = get_capture_server_id()
    conn = initialize(db_path or default_db_path())
    try:
        conn.execute(
            """
            UPDATE sessions
            SET capture_server_id = ?, capture_heartbeat_at = ?
            WHERE id = ?
            """,
            (server_id, now, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def touch_capture_heartbeat(session_id: str, *, db_path: Path | None = None) -> None:
    """Refresh the durable heartbeat for an active capture worker."""
    now = datetime.now(tz=UTC).isoformat()
    conn = initialize(db_path or default_db_path())
    try:
        conn.execute(
            """
            UPDATE sessions
            SET capture_heartbeat_at = ?
            WHERE id = ? AND status = ?
            """,
            (now, session_id, SessionStatus.RECORDING.value),
        )
        conn.commit()
    finally:
        conn.close()


def _heartbeat_age_seconds(record: SessionRecord, *, now: datetime) -> float | None:
    if record.capture_heartbeat_at is None:
        return None
    return (now - record.capture_heartbeat_at).total_seconds()


def is_session_live_anywhere(
    record: SessionRecord,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when any capture worker is heartbeating this session."""
    if record.status != SessionStatus.RECORDING:
        return False
    if record.capture_heartbeat_at is None:
        return False
    current = now or datetime.now(tz=UTC)
    age_s = _heartbeat_age_seconds(record, now=current)
    if age_s is None:
        return False
    return age_s <= CAPTURE_HEARTBEAT_STALE_S


def is_session_live(
    record: SessionRecord,
    *,
    now: datetime | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> bool:
    """Return True when this process owns or observes a live capture worker."""
    if record.status != SessionStatus.RECORDING:
        return False
    if registry is not None and registry.get_active(record.id) is not None:
        return True
    return is_session_live_anywhere(record, now=now)


def list_live_captures(
    *,
    db_path: Path | None = None,
    registry: LiveCaptureRegistry | None = None,
    now: datetime | None = None,
) -> list[SessionRecord]:
    """Return sessions that are durably live, newest first."""
    recording = list_sessions_by_status(SessionStatus.RECORDING, db_path=db_path)
    return [
        record
        for record in recording
        if is_session_live_anywhere(record, now=now)
        or (registry is not None and registry.get_active(record.id) is not None)
    ]


def _reconcile_interrupted_reason(record: SessionRecord, *, startup: bool) -> str:
    """Choose a machine-readable finalize reason for a stale recording row."""
    if record.capture_heartbeat_at is None:
        return "orphaned_capture"
    if startup:
        return "service_restart"
    return "orphaned_capture"


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    reconciled_session_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "reconciled_session_ids": list(self.reconciled_session_ids),
            "count": len(self.reconciled_session_ids),
            "reason": self.reason,
        }


def reconcile_orphaned_captures(
    *,
    db_path: Path | None = None,
    registry: LiveCaptureRegistry | None = None,
    reason: str = "orphaned_capture",
    now: datetime | None = None,
    startup: bool = False,
) -> ReconcileResult:
    """Finalize recording rows whose heartbeat is missing or stale."""
    current = now or datetime.now(tz=UTC)
    recording = list_sessions_by_status(SessionStatus.RECORDING, db_path=db_path)
    reconciled: list[str] = []
    for record in recording:
        if registry is not None and registry.get_active(record.id) is not None:
            continue
        if is_session_live_anywhere(record, now=current):
            continue
        interrupted_reason = _reconcile_interrupted_reason(record, startup=startup)
        finalize_session(
            record.id,
            status=SessionStatus.INTERRUPTED,
            frame_count=record.frame_count or 0,
            stopped_at=current,
            interrupted_reason=interrupted_reason,
            db_path=db_path,
        )
        reconciled.append(record.id)
    batch_reason = "service_restart" if startup else reason
    return ReconcileResult(reconciled_session_ids=tuple(reconciled), reason=batch_reason)


def require_live_session(
    session_id: str,
    *,
    db_path: Path | None = None,
    registry: LiveCaptureRegistry | None = None,
) -> SessionRecord:
    """Return a live session record or raise KeyError with a clear message."""
    record = get_session(session_id, db_path=db_path)
    if not (
        is_session_live_anywhere(record)
        or (registry is not None and registry.get_active(session_id) is not None)
    ):
        msg = (
            f"Session {session_id!r} is not a live capture "
            f"(status={record.status.value})."
        )
        raise KeyError(msg)
    return record
