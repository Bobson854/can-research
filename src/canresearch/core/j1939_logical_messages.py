"""Logical J1939 message abstraction for single-frame and transport-reassembled traffic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from canresearch.core.j1939 import J1939Identifier, parse_j1939_id
from canresearch.core.sessions import CanFrame

MAX_29BIT_CAN_ID = 0x1FFFFFFF


class TransportMode(StrEnum):
    BAM = "BAM"
    RTS_CTS = "RTS_CTS"


def categorize_j1939_frame(frame: CanFrame) -> str:
    """Return j1939, non_j1939, error, or malformed for one capture frame."""
    if frame.is_error_frame:
        return "error"
    if frame.can_id is None:
        return "malformed"
    if frame.rtr:
        return "non_j1939"
    if not frame.is_extended:
        return "non_j1939"
    if frame.can_id < 0 or frame.can_id > MAX_29BIT_CAN_ID:
        return "malformed"
    return "j1939"


@dataclass(frozen=True, slots=True)
class LogicalJ1939Message:
    """One logical J1939 application message (direct or transport-reassembled)."""

    pgn: int
    source_address: int
    destination_address: int | None
    priority: int
    timestamp_us: int
    payload: bytes
    is_transport: bool
    transport_mode: TransportMode | None = None
    transported_pgn: int | None = None
    packet_count: int | None = None
    payload_length: int | None = None
    started_at_us: int | None = None
    completed_at_us: int | None = None
    source_frame_count: int | None = None
    cm_can_id: int | None = None

    @property
    def application_pgn(self) -> int:
        """PGN used for reference lookup (transported PGN when reassembled)."""
        return self.transported_pgn if self.is_transport else self.pgn


def logical_message_from_frame(frame: CanFrame, parsed: J1939Identifier) -> LogicalJ1939Message:
    """Build a logical message from a single non-transport CAN frame."""
    payload = frame.data
    if frame.dlc is not None and len(payload) > frame.dlc:
        payload = payload[: frame.dlc]
    return LogicalJ1939Message(
        pgn=parsed.pgn,
        source_address=parsed.source_address,
        destination_address=parsed.destination_address,
        priority=parsed.priority,
        timestamp_us=frame.timestamp_us,
        payload=payload,
        is_transport=False,
        payload_length=len(payload),
        source_frame_count=1,
    )


def logical_message_from_can_frame(frame: CanFrame) -> LogicalJ1939Message | None:
    """Parse a capture frame into a logical single-frame message, or None if not J1939."""
    if frame.is_error_frame or frame.can_id is None or frame.rtr or not frame.is_extended:
        return None
    try:
        parsed = parse_j1939_id(frame.can_id)
    except ValueError:
        return None
    return logical_message_from_frame(frame, parsed)
