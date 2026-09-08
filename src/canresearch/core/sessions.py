"""Capture session metadata and pluggable raw-frame storage."""

from __future__ import annotations

import sqlite3
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from canresearch.storage.database import default_db_path, initialize


class SessionStatus(StrEnum):
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    STOPPED = "stopped"
    ANALYZED = "analyzed"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Session metadata stored in SQLite."""

    id: str
    name: str | None
    device_id: str | None
    host: str | None
    channel: int | None
    started_at: datetime
    stopped_at: datetime | None
    status: SessionStatus
    frame_store_path: str | None
    frame_count: int | None
    notes: str | None
    capture_server_id: str | None = None
    capture_heartbeat_at: datetime | None = None
    interrupted_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CanFrame:
    """Single captured CAN frame (in-memory / file representation)."""

    timestamp_us: int
    channel: int
    can_id: int | None
    is_extended: bool
    fd: bool
    rtr: bool
    brs: bool
    esi: bool
    tx_ack: bool
    dlc: int | None
    data: bytes
    is_error_frame: bool
    error_type: str | None


class CaptureStore(ABC):
    """Abstract storage for raw capture frames."""

    @abstractmethod
    def open(self, path: Path) -> None:
        """Open or create a capture store at the given path."""

    @abstractmethod
    def append(self, frame: CanFrame) -> None:
        """Append a single frame."""

    @abstractmethod
    def iter_frames(self) -> Iterator[CanFrame]:
        """Iterate all stored frames."""

    @abstractmethod
    def close(self) -> None:
        """Flush and close the store."""

    @abstractmethod
    def frame_count(self) -> int:
        """Return the number of frames stored."""


class NullCaptureStore(CaptureStore):
    """No-op capture store for scaffolding and tests."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._frames: list[CanFrame] = []

    def open(self, path: Path) -> None:
        self._path = path

    def append(self, frame: CanFrame) -> None:
        self._frames.append(frame)

    def iter_frames(self) -> Iterator[CanFrame]:
        return iter(self._frames)

    def close(self) -> None:
        pass

    def frame_count(self) -> int:
        return len(self._frames)


def default_sessions_dir() -> Path:
    """Directory for file-backed capture session stores."""
    from canresearch.config import resolve_data_dir

    return resolve_data_dir() / "sessions"


def session_frames_path(session_id: str) -> Path:
    """Default JSONL frame store path for a session."""
    return default_sessions_dir() / session_id / "frames.jsonl"


def resolve_session_frames_path(record: SessionRecord) -> Path:
    """Resolve the frame store path for a session record."""
    if record.frame_store_path:
        return Path(record.frame_store_path)
    return session_frames_path(record.id)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _row_to_record(row: sqlite3.Row) -> SessionRecord:
    keys = row.keys()
    return SessionRecord(
        id=row["id"],
        name=row["name"],
        device_id=row["device_id"],
        host=row["host"],
        channel=row["channel"],
        started_at=_parse_datetime(row["started_at"]) or _utc_now(),
        stopped_at=_parse_datetime(row["stopped_at"]),
        status=SessionStatus(row["status"]),
        frame_store_path=row["frame_store_path"],
        frame_count=row["frame_count"],
        notes=row["notes"],
        capture_server_id=row["capture_server_id"] if "capture_server_id" in keys else None,
        capture_heartbeat_at=_parse_datetime(row["capture_heartbeat_at"])
        if "capture_heartbeat_at" in keys
        else None,
        interrupted_reason=row["interrupted_reason"] if "interrupted_reason" in keys else None,
    )


def create_session(
    *,
    name: str | None,
    host: str,
    channel: int,
    device_id: str | None,
    frame_store_path: str,
    db_path: Path | None = None,
    session_id: str | None = None,
) -> SessionRecord:
    """Create a new session row in recording state."""
    session_key = session_id or uuid.uuid4().hex[:12]
    started_at = _utc_now()
    conn = initialize(db_path or default_db_path())
    try:
        conn.execute(
            """
            INSERT INTO sessions (
                id, name, device_id, host, channel, started_at, status,
                frame_store_path, frame_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_key,
                name,
                device_id,
                host,
                channel,
                started_at.isoformat(),
                SessionStatus.RECORDING.value,
                frame_store_path,
                0,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_key,)).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Failed to create session {session_key}"
        raise RuntimeError(msg)
    return _row_to_record(row)


def finalize_session(
    session_id: str,
    *,
    status: SessionStatus,
    frame_count: int,
    stopped_at: datetime | None = None,
    notes: str | None = None,
    interrupted_reason: str | None = None,
    db_path: Path | None = None,
) -> SessionRecord:
    """Update session metadata when capture ends."""
    ended = stopped_at or _utc_now()
    conn = initialize(db_path or default_db_path())
    try:
        conn.execute(
            """
            UPDATE sessions
            SET stopped_at = ?, status = ?, frame_count = ?,
                notes = COALESCE(?, notes),
                interrupted_reason = COALESCE(?, interrupted_reason)
            WHERE id = ?
            """,
            (
                ended.isoformat(),
                status.value,
                frame_count,
                notes,
                interrupted_reason,
                session_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Session not found: {session_id}"
        raise KeyError(msg)
    return _row_to_record(row)


def get_session(session_id: str, *, db_path: Path | None = None) -> SessionRecord:
    conn = initialize(db_path or default_db_path())
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Session not found: {session_id}"
        raise KeyError(msg)
    return _row_to_record(row)


def list_sessions(*, db_path: Path | None = None, limit: int = 50) -> list[SessionRecord]:
    conn = initialize(db_path or default_db_path())
    try:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_record(row) for row in rows]


def list_sessions_by_status(
    status: SessionStatus,
    *,
    db_path: Path | None = None,
) -> list[SessionRecord]:
    """Return sessions with a given status, newest first."""
    conn = initialize(db_path or default_db_path())
    try:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE status = ?
            ORDER BY started_at DESC, id ASC
            """,
            (status.value,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_record(row) for row in rows]


def summarize_session(session_id: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Produce a summary for a capture session."""
    record = get_session(session_id, db_path=db_path)
    duration_s: float | None = None
    if record.stopped_at is not None:
        duration_s = (record.stopped_at - record.started_at).total_seconds()
    return {
        "id": record.id,
        "name": record.name,
        "device_id": record.device_id,
        "host": record.host,
        "channel": record.channel,
        "started_at": record.started_at,
        "stopped_at": record.stopped_at,
        "duration_s": duration_s,
        "status": record.status.value,
        "frame_count": record.frame_count,
        "frame_store_path": record.frame_store_path,
        "notes": record.notes,
    }
