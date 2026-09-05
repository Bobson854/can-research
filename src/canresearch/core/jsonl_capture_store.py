"""JSON Lines file-backed capture store."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

from canresearch.core.sessions import CanFrame, CaptureStore


class JsonlCaptureStore(CaptureStore):
    """Append-only JSONL store for captured CAN frames."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._handle: TextIO | None = None
        self._count = 0

    def open(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._handle = path.open("a", encoding="utf-8")
        self._count = 0

    def append(self, frame: CanFrame) -> None:
        if self._handle is None:
            msg = "Capture store is not open"
            raise RuntimeError(msg)
        self._handle.write(json.dumps(_frame_to_json(frame), separators=(",", ":")))
        self._handle.write("\n")
        self._handle.flush()
        self._count += 1

    def iter_frames(self) -> Iterator[CanFrame]:
        if self._path is None:
            return iter(())
        return iter_frames_from_path(self._path)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None

    def frame_count(self) -> int:
        return self._count


def _frame_to_json(frame: CanFrame) -> dict[str, Any]:
    return {
        "timestamp_us": frame.timestamp_us,
        "channel": frame.channel,
        "can_id": frame.can_id,
        "extended": frame.is_extended,
        "fd": frame.fd,
        "rtr": frame.rtr,
        "brs": frame.brs,
        "esi": frame.esi,
        "tx_ack": frame.tx_ack,
        "dlc": frame.dlc,
        "data": frame.data.hex(),
        "is_error_frame": frame.is_error_frame,
        "error_type": frame.error_type,
    }


def iter_frames_from_path(path: Path) -> Iterator[CanFrame]:
    """Iterate frames from a JSONL capture file."""
    if not path.exists():
        return iter(())
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield _frame_from_json(json.loads(line))


def _frame_from_json(payload: dict[str, Any]) -> CanFrame:
    data_hex = payload.get("data", "")
    data = bytes.fromhex(data_hex) if isinstance(data_hex, str) and data_hex else b""
    can_id = payload.get("can_id")
    return CanFrame(
        timestamp_us=int(payload["timestamp_us"]),
        channel=int(payload.get("channel", 0)),
        can_id=int(can_id) if can_id is not None else None,
        is_extended=bool(payload.get("extended", False)),
        fd=bool(payload.get("fd", False)),
        rtr=bool(payload.get("rtr", False)),
        brs=bool(payload.get("brs", False)),
        esi=bool(payload.get("esi", False)),
        tx_ack=bool(payload.get("tx_ack", False)),
        dlc=payload.get("dlc"),
        data=data,
        is_error_frame=bool(payload.get("is_error_frame", False)),
        error_type=payload.get("error_type"),
    )
