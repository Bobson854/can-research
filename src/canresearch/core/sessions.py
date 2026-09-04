"""Capture session metadata and pluggable raw-frame storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class SessionStatus(StrEnum):
    RECORDING = "recording"
    STOPPED = "stopped"
    ANALYZED = "analyzed"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Session metadata stored in SQLite."""

    id: str
    name: str | None
    device_id: str | None
    started_at: datetime
    stopped_at: datetime | None
    status: SessionStatus
    frame_store_path: str | None
    frame_count: int | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class CanFrame:
    """Single captured CAN frame (in-memory representation)."""

    timestamp_us: int
    can_id: int
    is_extended: bool
    data: bytes
    channel: int = 0


class CaptureStore(ABC):
    """Abstract storage for raw capture frames.

    Raw frames are intentionally kept out of SQLite. Implementations may use
    binary logs, Parquet, CSV, or other formats once CANsub.2 volume is known.
    """

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


def list_sessions() -> list[SessionRecord]:
    """Return all sessions from the database."""
    raise NotImplementedError("Session listing is not yet implemented")


def summarize_session(session_id: str) -> dict[str, object]:
    """Produce a summary for a capture session."""
    raise NotImplementedError("Session summary is not yet implemented")
