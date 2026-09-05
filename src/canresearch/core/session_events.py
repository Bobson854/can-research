"""Experiment event markers for capture sessions."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from canresearch.core.sessions import get_session
from canresearch.storage.database import default_db_path, initialize


@dataclass(frozen=True, slots=True)
class SessionEvent:
    id: str
    session_id: str
    timestamp_us: int
    label: str
    notes: str | None
    created_at: datetime


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def add_session_event(
    session_id: str,
    label: str,
    *,
    notes: str | None = None,
    timestamp_us: int | None = None,
    db_path: Path | None = None,
) -> SessionEvent:
    """Persist an experiment marker against a session."""
    cleaned = label.strip()
    if not cleaned:
        msg = "Event label is required"
        raise ValueError(msg)

    get_session(session_id, db_path=db_path)
    ts = (
        timestamp_us
        if timestamp_us is not None
        else int(datetime.now(tz=UTC).timestamp() * 1_000_000)
    )
    event_id = uuid.uuid4().hex[:12]
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        conn.execute(
            """
            INSERT INTO session_events (id, session_id, timestamp_us, label, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, session_id, ts, cleaned, notes, _utc_now_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM session_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Failed to create session event for {session_id}"
        raise RuntimeError(msg)
    return _row_to_event(row)


def list_session_events(
    session_id: str,
    *,
    db_path: Path | None = None,
) -> list[SessionEvent]:
    """Return experiment markers for a session ordered by timestamp."""
    get_session(session_id, db_path=db_path)
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM session_events
            WHERE session_id = ?
            ORDER BY timestamp_us ASC, created_at ASC
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_event(row) for row in rows]


def get_session_event_by_label(
    session_id: str,
    label: str,
    *,
    db_path: Path | None = None,
) -> SessionEvent:
    """Return the most recent event with a given label in a session."""
    path = db_path or default_db_path()
    conn = initialize(path)
    try:
        row = conn.execute(
            """
            SELECT * FROM session_events
            WHERE session_id = ? AND label = ?
            ORDER BY timestamp_us DESC, created_at DESC
            LIMIT 1
            """,
            (session_id, label.strip()),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        msg = f"Event {label!r} not found in session {session_id!r}"
        raise KeyError(msg)
    return _row_to_event(row)


def _row_to_event(row: sqlite3.Row) -> SessionEvent:
    return SessionEvent(
        id=row["id"],
        session_id=row["session_id"],
        timestamp_us=int(row["timestamp_us"]),
        label=row["label"],
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]),
    )
