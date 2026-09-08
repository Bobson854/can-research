"""Passive local capture marker companion — service layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from canresearch.core.session_events import SessionEvent, add_session_event
from canresearch.core.sessions import (
    SessionRecord,
    SessionStatus,
    get_session,
    list_sessions_by_status,
)
from canresearch.storage.database import default_db_path


LOCAL_COMPANION_ORIGIN = "local_companion"

STANDARD_MARKER_LABELS: tuple[str, ...] = (
    "baseline",
    "page_opened",
    "node_selected",
    "save_pressed",
    "save_complete",
    "action",
)


@dataclass(frozen=True, slots=True)
class AttachedSession:
    session_id: str
    name: str | None
    host: str | None
    channel: int | None
    status: SessionStatus

    @classmethod
    def from_record(cls, record: SessionRecord) -> AttachedSession:
        return cls(
            session_id=record.id,
            name=record.name,
            host=record.host,
            channel=record.channel,
            status=record.status,
        )


class MarkerCompanionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        sessions: tuple[AttachedSession, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.sessions = sessions


def local_timestamp_us() -> int:
    """Return capture-host wall time in microseconds (UTC)."""
    return int(datetime.now(tz=UTC).timestamp() * 1_000_000)


def list_recording_sessions(*, db_path: Path | None = None) -> list[SessionRecord]:
    """Return sessions currently marked recording in SQLite."""
    return list_sessions_by_status(SessionStatus.RECORDING, db_path=db_path)


def resolve_attached_session(
    *,
    session_id: str | None = None,
    db_path: Path | None = None,
) -> AttachedSession:
    """Attach to exactly one active recording session or raise."""
    if session_id is not None:
        record = get_session(session_id, db_path=db_path)
        if record.status != SessionStatus.RECORDING:
            msg = (
                f"Session {session_id!r} is not recording "
                f"(status={record.status.value})"
            )
            raise MarkerCompanionError("capture_not_active", msg)
        return AttachedSession.from_record(record)

    recording = list_recording_sessions(db_path=db_path)
    if not recording:
        raise MarkerCompanionError(
            "no_active_capture",
            "No active recording session found. Start live capture first.",
        )
    if len(recording) > 1:
        attached = tuple(AttachedSession.from_record(record) for record in recording)
        ids = ", ".join(item.session_id for item in attached)
        raise MarkerCompanionError(
            "multiple_active_captures",
            f"Multiple recording sessions found ({ids}). Select one explicitly.",
            sessions=attached,
        )
    return AttachedSession.from_record(recording[0])


def record_companion_marker(
    session_id: str,
    label: str,
    *,
    notes: str | None = None,
    timestamp_us: int | None = None,
    db_path: Path | None = None,
) -> SessionEvent:
    """Persist a local companion marker against an active recording session."""
    resolve_attached_session(session_id=session_id, db_path=db_path)
    ts = timestamp_us if timestamp_us is not None else local_timestamp_us()
    return add_session_event(
        session_id,
        label,
        notes=notes,
        timestamp_us=ts,
        origin=LOCAL_COMPANION_ORIGIN,
        db_path=db_path,
    )


def session_event_to_dict(event: SessionEvent) -> dict[str, object]:
    """Serialize a session event for CLI/GUI confirmation."""
    return {
        "id": event.id,
        "session_id": event.session_id,
        "timestamp_us": event.timestamp_us,
        "timestamp": datetime.fromtimestamp(
            event.timestamp_us / 1_000_000,
            tz=UTC,
        ).isoformat(),
        "label": event.label,
        "notes": event.notes,
        "origin": event.origin,
        "created_at": event.created_at.isoformat(),
    }
