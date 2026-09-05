"""Shared frame loading and payload helpers for session research."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from canresearch.core.j1939 import parse_j1939_id
from canresearch.core.jsonl_capture_store import iter_frames_from_path
from canresearch.core.session_events import get_session_event_by_label
from canresearch.core.sessions import CanFrame, get_session, resolve_session_frames_path

MAX_FRAMES_PER_CAN_ID = 10_000


def normalize_payload(data: bytes, dlc: int | None) -> bytes:
    length = dlc if dlc is not None else len(data)
    length = min(max(length, 0), 8)
    trimmed = data[:length]
    return trimmed.ljust(8, b"\x00")


def effective_payload_length(dlc: int | None, data: bytes) -> int:
    if dlc is not None:
        return min(max(dlc, 0), 8)
    return min(len(data), 8)


def format_can_id(can_id: int) -> str:
    return f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}"


def parse_can_id_fields(can_id: int, *, is_extended: bool) -> dict[str, int | None]:
    if not is_extended:
        return {"pgn": None, "source_address": None, "destination_address": None}
    try:
        parsed = parse_j1939_id(can_id)
    except ValueError:
        return {"pgn": None, "source_address": None, "destination_address": None}
    return {
        "pgn": parsed.pgn,
        "source_address": parsed.source_address,
        "destination_address": parsed.destination_address,
    }


def load_session_frames(session_id: str, *, db_path: Path | None = None) -> list[CanFrame]:
    record = get_session(session_id, db_path=db_path)
    path = resolve_session_frames_path(record)
    if not path.exists():
        msg = f"Frame store not found: {path}"
        raise FileNotFoundError(msg)
    return list(iter_frames_from_path(path))


def resolve_event_window_us(
    session_id: str,
    event_label: str,
    *,
    window_seconds: float,
    db_path: Path | None = None,
) -> tuple[int, int]:
    marker = get_session_event_by_label(session_id, event_label, db_path=db_path)
    window_us = int(window_seconds * 1_000_000)
    return marker.timestamp_us, marker.timestamp_us + window_us


def sample_deterministic(items: Sequence, max_count: int) -> list:
    """Evenly spaced deterministic subsample (never random)."""
    if max_count <= 0 or len(items) <= max_count:
        return list(items)
    if max_count == 1:
        return [items[0]]
    step = (len(items) - 1) / (max_count - 1)
    indices = {round(index * step) for index in range(max_count)}
    return [items[i] for i in sorted(indices)]


@dataclass(frozen=True, slots=True)
class PayloadSeries:
    can_id: int
    timestamps_us: tuple[int, ...]
    payloads: tuple[bytes, ...]
    pgn: int | None
    source_address: int | None
    destination_address: int | None
    truncated: bool = False


def collect_payload_series(
    frames: Iterable[CanFrame],
    can_id: int,
    *,
    start_us: int | None = None,
    end_us: int | None = None,
    source_address: int | None = None,
    pgn: int | None = None,
    max_frames: int = MAX_FRAMES_PER_CAN_ID,
) -> PayloadSeries:
    timestamps: list[int] = []
    payloads: list[bytes] = []
    fields = {"pgn": None, "source_address": None, "destination_address": None}

    for frame in frames:
        if frame.is_error_frame or frame.can_id != can_id:
            continue
        if start_us is not None and frame.timestamp_us < start_us:
            continue
        if end_us is not None and frame.timestamp_us >= end_us:
            continue
        if fields["pgn"] is None:
            parsed = parse_can_id_fields(can_id, is_extended=frame.is_extended)
            fields.update(parsed)
        if source_address is not None and fields["source_address"] != source_address:
            continue
        if pgn is not None and fields["pgn"] != pgn:
            continue
        timestamps.append(frame.timestamp_us)
        payloads.append(normalize_payload(frame.data, frame.dlc))

    truncated = len(payloads) > max_frames
    if truncated:
        sampled = sample_deterministic(list(zip(timestamps, payloads, strict=True)), max_frames)
        timestamps = [item[0] for item in sampled]
        payloads = [item[1] for item in sampled]

    return PayloadSeries(
        can_id=can_id,
        timestamps_us=tuple(timestamps),
        payloads=tuple(payloads),
        pgn=fields["pgn"],
        source_address=fields["source_address"],
        destination_address=fields["destination_address"],
        truncated=truncated,
    )


def filter_frames_by_sa(
    frames: Iterable[CanFrame],
    source_addresses: set[int],
) -> list[CanFrame]:
    result: list[CanFrame] = []
    for frame in frames:
        if frame.is_error_frame or frame.can_id is None:
            continue
        fields = parse_can_id_fields(frame.can_id, is_extended=frame.is_extended)
        sa = fields["source_address"]
        if sa is not None and sa in source_addresses:
            result.append(frame)
    return result
